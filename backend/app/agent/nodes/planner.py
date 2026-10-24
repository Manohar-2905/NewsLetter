"""Planning: turn the user's goal into a structured research plan."""

from __future__ import annotations

from ...config import get_settings
from ...services.llm_base import LLMError, LLMQuotaError
from ...utils.text import collapse_ws, keywords_from_goal, truncate
from ..prompts import PLANNER_SYSTEM
from ..query_rewrite import normalize_rewrites
from .common import ctx_for, quota_warning, usable_llm


def deterministic_plan(goal: str, article_count: int, lookback: int) -> dict:
    keywords = keywords_from_goal(goal)
    topic = " ".join(keywords[:5]) or truncate(goal, 60)
    queries = [topic]
    if len(keywords) > 3:
        queries.append(" ".join(keywords[:3]))
    return {
        "topic": topic,
        "search_queries": queries,
        "keywords": keywords,
        "lookback_days": lookback,
        "article_count": article_count,
        "audience": "general professional readers",
        "angle": f"Recent news about {topic}",
        "quality_criteria": [
            "Articles are directly about the topic",
            "Published within the lookback window",
            "Reputable or primary sources, diverse publishers",
            "Every claim is traceable to a linked source",
        ],
        "planned_by": "deterministic",
    }


def plan_node(state: dict) -> dict:
    ctx = ctx_for(state)
    settings = get_settings()
    cfg = state.get("config") or {}
    goal = state["goal"]
    article_count = int(cfg.get("article_count") or 5)
    lookback = int(cfg.get("lookback_days") or settings.default_lookback_days)
    warnings = list(state.get("warnings") or [])

    ctx.emit("planning", "started", "Understanding the goal and planning research")
    plan = deterministic_plan(goal, article_count, lookback)
    llm = usable_llm(ctx)
    if llm is not None:
        prompt = (
            f"User goal: {goal}\n\n"
            "Create a research plan for a news newsletter. Return JSON with keys:\n"
            '  "topic": short, crisp topic name (max 8 words),\n'
            '  "search_queries": 3-4 concise news search queries (2-6 words each, no operators, no dates). '
            "Rewrite the user request rather than repeating it once: one close paraphrase, one named-entity or product angle, "
            "one impact angle, and one recent-news angle. Keep every constraint the user stated. "
            "Target authoritative primary reporting, technical releases, official statements, and major investigative pieces "
            "that provide accessible, substantive text rather than aggregate clickbait or paywalled portals,\n"
            '  "keywords": 4-8 lowercase discriminating technical terms, named entities, and core identifiers '
            "that an authoritative, on-topic primary source article will contain in its body,\n"
            f'  "lookback_days": integer 1-30 (default {lookback}; use more only if the goal asks for a longer period),\n'
            '  "audience": target reader persona (e.g. senior engineers, security leaders, product directors),\n'
            '  "angle": sharp, analytical editorial angle focusing on industry impact and strategic takeaways,\n'
            '  "quality_criteria": 3-5 strict criteria for high-integrity articles (primary authority, accessible full text, concrete evidence).\n'
        )
        try:
            raw = llm.generate_json(prompt, system=PLANNER_SYSTEM, max_tokens=700)
            if isinstance(raw, dict):
                queries = [collapse_ws(str(q))[:80] for q in raw.get("search_queries") or [] if collapse_ws(str(q))]
                keywords = [collapse_ws(str(k)).lower()[:40] for k in raw.get("keywords") or [] if collapse_ws(str(k))]
                if queries:
                    plan["search_queries"] = queries[:4]
                if keywords:
                    # keep deterministic keywords too: they come straight from the user's words
                    merged = keywords + [k for k in plan["keywords"] if k not in keywords]
                    plan["keywords"] = merged[:10]
                for key in ("topic", "audience", "angle"):
                    if raw.get(key):
                        plan[key] = truncate(collapse_ws(str(raw[key])), 160)
                if isinstance(raw.get("quality_criteria"), list) and raw["quality_criteria"]:
                    plan["quality_criteria"] = [truncate(str(c), 120) for c in raw["quality_criteria"][:5]]
                try:
                    plan["lookback_days"] = max(1, min(30, int(raw.get("lookback_days") or lookback)))
                except (TypeError, ValueError):
                    pass
                if cfg.get("lookback_days"):  # explicit user setting wins
                    plan["lookback_days"] = lookback
                plan["planned_by"] = llm.label
        except LLMQuotaError as exc:
            warnings.append(quota_warning(ctx, "planning", exc))
        except LLMError as exc:
            warnings.append(f"Planner model failed ({exc}); used keyword-based plan.")
            ctx.emit("planning", "warning", f"Model planning failed, using keyword plan: {exc}")

    plan["article_count"] = article_count
    plan["output_format"] = cfg.get("output_format", "html")
    plan["tone"] = cfg.get("tone", "professional")
    plan["rewritten_queries"] = normalize_rewrites(
        goal,
        plan.get("search_queries") or [],
        plan.get("keywords") or [],
        plan.get("topic") or goal,
        limit=settings.max_rewritten_queries,
    )
    plan["search_queries"] = [rewrite["query"] for rewrite in plan["rewritten_queries"]] or [truncate(goal, 80)]
    ctx.emit(
        "planning",
        "completed",
        f"Plan ready: {len(plan['search_queries'])} queries, last {plan['lookback_days']} days, "
        f"target {article_count} articles",
        {"plan": plan},
    )
    ctx.publish(plan=plan)
    return {"plan": plan, "warnings": warnings, "research_round": 0, "candidates": [], "research_log": []}
