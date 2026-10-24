"""Human-in-the-Loop: pause for approval, then apply editor feedback."""

from __future__ import annotations

import re

from langgraph.types import interrupt

from ...services.llm_base import LLMError, LLMQuotaError
from ...tools.summarize_article import summarize_article
from ..prompts import PLANNER_SYSTEM
from .common import ctx_for, quota_warning, usable_llm

MAX_HUMAN_ROUNDS = 5


def human_review_node(state: dict) -> dict:
    # Nothing with side effects may run before interrupt(): LangGraph re-runs
    # this node from the top when the workflow is resumed.
    decision = interrupt(
        {
            "type": "approval_required",
            "subject": (state.get("newsletter") or {}).get("subject"),
            "review_status": (state.get("review") or {}).get("status"),
            "articles": len(state.get("summaries") or []),
        }
    )
    ctx = ctx_for(state)
    action = (decision or {}).get("action")
    if action == "approve":
        ctx.emit("approval", "completed", "Draft approved by a human reviewer")
        return {"approved": True}

    feedback = str((decision or {}).get("feedback") or "").strip()
    rounds = int(state.get("human_rounds") or 0) + 1
    history = list(state.get("human_feedback_history") or []) + [feedback]
    ctx.emit("approval", "info", f"Changes requested (round {rounds}): {feedback[:160]}")
    updates = apply_human_feedback(state, feedback, ctx)
    updates.update({
        "human_feedback": feedback,
        "human_feedback_history": history,
        "human_rounds": rounds,
        "revision_count": 0,  # give the automatic critic a fresh budget for the new draft
        "approved": False,
    })
    return updates


def route_after_human(state: dict) -> str:
    return "save" if state.get("approved") else "write"


def _deterministic_interpretation(feedback: str, count: int) -> dict:
    remove = []
    for m in re.finditer(r"(?:remove|drop|delete)\s+(?:article|story|item)?\s*#?(\d+)", feedback, re.I):
        n = int(m.group(1))
        if 1 <= n <= count:
            remove.append(n)
    return {"remove_articles": remove, "rewrite_articles": [], "newsletter_instructions": feedback}


def apply_human_feedback(state: dict, feedback: str, ctx) -> dict:
    selected = list(state.get("selected") or [])
    summaries = list(state.get("summaries") or [])
    warnings = list(state.get("warnings") or [])
    plan = state["plan"]
    llm = usable_llm(ctx)
    interpretation = _deterministic_interpretation(feedback, len(summaries))

    if llm is not None:
        listing = "\n".join(f"{i + 1}. {s['headline']} ({s['publisher']})" for i, s in enumerate(summaries))
        prompt = (
            "A human editor reviewed a newsletter draft and left feedback. Translate it into actions.\n"
            f"Articles:\n{listing}\n\nEditor feedback: {feedback}\n\n"
            'Return JSON: {"remove_articles": [article numbers to remove], '
            '"rewrite_articles": [{"article": <number>, "instruction": "..."}], '
            '"newsletter_instructions": "instructions for subject/intro/takeaways/conclusion/tone, or empty"}'
        )
        try:
            raw = llm.generate_json(prompt, system=PLANNER_SYSTEM, max_tokens=600)
            if isinstance(raw, dict):
                interpretation = {
                    "remove_articles": [int(n) for n in raw.get("remove_articles") or [] if str(n).isdigit()],
                    "rewrite_articles": [r for r in raw.get("rewrite_articles") or [] if isinstance(r, dict)],
                    "newsletter_instructions": str(raw.get("newsletter_instructions") or ""),
                }
        except LLMQuotaError as exc:
            warnings.append(quota_warning(ctx, "approval", exc))
            llm = None
        except LLMError as exc:
            ctx.emit("approval", "warning", f"Could not interpret feedback with the model ({exc}); applying it as general guidance.")

    topic = plan.get("topic") or state["goal"]
    for item in interpretation["rewrite_articles"]:
        try:
            idx = int(item.get("article")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(summaries) and llm is not None:
            try:
                summaries[idx] = summarize_article(selected[idx], llm, topic, plan.get("tone", "professional"),
                                                   feedback=str(item.get("instruction", ""))[:400])
                ctx.emit("approval", "info", f"summarize_article: rewrote article {idx + 1} per editor feedback")
            except LLMQuotaError as exc:
                warnings.append(quota_warning(ctx, "approval", exc))
                llm = None
            except (LLMError, ValueError) as exc:
                ctx.emit("approval", "warning", f"Could not rewrite article {idx + 1}: {exc}")

    for n in sorted(set(interpretation["remove_articles"]), reverse=True):
        idx = n - 1
        if 0 <= idx < len(summaries) and len(summaries) > 1:
            selected.pop(idx)
            summaries.pop(idx)
            ctx.emit("approval", "info", f"Removed article {n} per editor feedback")

    instructions = interpretation["newsletter_instructions"] or feedback
    return {
        "selected": selected,
        "summaries": summaries,
        "warnings": warnings,
        "revision_feedback": f"Human editor feedback (highest priority, but never add facts not in the sources):\n{instructions}",
    }
