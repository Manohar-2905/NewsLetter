"""Self-critique and automatic revision."""

from __future__ import annotations

from ...config import get_settings
from ...services.llm_base import LLMError, LLMQuotaError
from ...tools.review_newsletter import review_newsletter
from ...tools.search_news import fetch_article_content
from ...tools.summarize_article import fallback_summary, summarize_article
from .common import ctx_for, quota_warning, usable_llm

RESUMMARIZE_CODES = {"unsupported_number", "unsupported_claim", "factual_inconsistency", "fabrication", "empty_summary"}
DROP_CODES = {"duplicate_story", "off_topic", "missing_link"}


def critic_node(state: dict) -> dict:
    ctx = ctx_for(state)
    settings = get_settings()
    plan = state["plan"]
    attempt = int(state.get("revision_count") or 0)
    ctx.emit("review", "started", "Reviewing the draft (deterministic checks + AI critic)")

    critic = ctx.critic_llm if ctx.critic_llm is not None else usable_llm(ctx)
    review = review_newsletter(
        state["newsletter"],
        state.get("selected") or [],
        {
            "topic": plan.get("topic") or state["goal"],
            "article_count": plan.get("article_count"),
            "max_articles": settings.max_articles,
            "keywords": plan.get("keywords"),
        },
        llm=critic,
    )
    review["attempt"] = attempt
    history = list(state.get("review_history") or []) + [
        {"attempt": attempt, "status": review["status"], "errors": review["error_count"],
         "warnings": review["warning_count"], "semantic": review["semantic_review"].get("status")}
    ]
    errors = [i["message"] for i in review["issues"] if i["severity"] == "error"]
    ctx.emit(
        "review",
        "completed" if review["passed"] else "warning",
        ("Review passed" if review["passed"] else f"Review found {len(errors)} issue(s): " + "; ".join(errors[:3]))
        + f" ({review['warning_count']} warnings; semantic review: {review['semantic_review'].get('status')})",
        {"review": review},
    )
    ctx.publish(review=review, review_history=history)
    return {"review": review, "review_history": history}


def route_after_review(state: dict) -> str:
    settings = get_settings()
    review = state.get("review") or {}
    if not review.get("passed") and int(state.get("revision_count") or 0) < settings.max_revisions:
        return "revise"
    if (state.get("config") or {}).get("mode") == "hitl" and not state.get("approved"):
        return "human_review"
    return "save"


def revise_node(state: dict) -> dict:
    """Fix what the reviewer flagged: re-summarize, replace or drop articles, then rewrite."""
    ctx = ctx_for(state)
    settings = get_settings()
    plan = state["plan"]
    review = state.get("review") or {}
    errors = [i for i in review.get("issues", []) if i["severity"] == "error"]
    selected = list(state.get("selected") or [])
    summaries = list(state.get("summaries") or [])
    reserve = list(state.get("reserve") or [])
    warnings = list(state.get("warnings") or [])
    attempt = int(state.get("revision_count") or 0) + 1
    ctx.emit("revision", "started", f"Revision {attempt}/{settings.max_revisions}: addressing {len(errors)} issue(s)")

    resummarize: dict[int, list[str]] = {}
    drop: set[int] = set()
    framing_notes: list[str] = []
    for issue in errors:
        idx = issue.get("article_index")
        if idx is not None and 0 <= idx < len(summaries):
            if issue["code"] in DROP_CODES:
                drop.add(idx)
            elif issue["code"] in RESUMMARIZE_CODES or issue["code"] == "quality":
                resummarize.setdefault(idx, []).append(f"{issue['message']} {issue.get('fix', '')}".strip())
        elif issue["code"] not in ("fewer_articles",):
            framing_notes.append(f"- {issue['message']} {issue.get('fix', '')}".strip())

    llm = usable_llm(ctx)
    topic = plan.get("topic") or state["goal"]
    tone = plan.get("tone", "professional")

    def summarize_or_fallback(article, feedback=""):
        nonlocal llm
        if llm is None:
            return fallback_summary(article)
        try:
            return summarize_article(article, llm, topic, tone, feedback=feedback)
        except LLMQuotaError as exc:
            warnings.append(quota_warning(ctx, "revision", exc))
            llm = None
        except (LLMError, ValueError) as exc:
            ctx.emit("revision", "warning", f"Re-summarizing failed ({exc}); using the publisher excerpt.")
        return fallback_summary(article)

    for idx, notes in resummarize.items():
        if idx in drop:
            continue
        ctx.emit("revision", "info", f"summarize_article: rewriting summary {idx + 1} strictly from its source")
        summaries[idx] = summarize_or_fallback(selected[idx], " ".join(notes) +
                                               " Use only facts present in the source text.")

    # Replace dropped articles with reserve candidates when possible.
    for idx in sorted(drop, reverse=True):
        replacement = None
        while reserve and replacement is None:
            cand = reserve.pop(0)
            if all(cand.get("url") != s.get("url") for s in selected):
                replacement = cand
        if replacement is not None:
            replacement = fetch_article_content(replacement, settings)
            ctx.emit("revision", "info", f"Replacing article {idx + 1} with '{replacement['title'][:60]}'")
            selected[idx] = replacement
            summaries[idx] = summarize_or_fallback(replacement)
        elif len(selected) > 1:
            ctx.emit("revision", "info", f"Removing article {idx + 1} (no suitable replacement)")
            selected.pop(idx)
            summaries.pop(idx)

    feedback = "Reviewer feedback:\n" + ("\n".join(framing_notes) if framing_notes else "- Keep framing consistent with the revised summaries.")
    return {
        "selected": selected,
        "summaries": summaries,
        "reserve": reserve,
        "revision_feedback": feedback,
        "revision_count": attempt,
        "warnings": warnings,
    }
