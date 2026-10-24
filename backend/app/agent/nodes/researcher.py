"""Research: run real searches, and broaden the search if results are thin."""

from __future__ import annotations

from ...config import get_settings
from ...tools.search_news import search_news
from ...utils.dedupe import dedupe_articles
from ...utils.text import collapse_ws
from ..query_rewrite import make_rewrite
from ..ranking import annotate_query_ranks
from .common import ctx_for
from .selector import relevant_candidates


def research_node(state: dict) -> dict:
    ctx = ctx_for(state)
    settings = get_settings()
    plan = state["plan"]
    round_no = int(state.get("research_round") or 0) + 1
    rewrites = plan.get("rewritten_queries") or []
    queries = [rewrite["query"] for rewrite in rewrites if rewrite.get("query")] or plan.get("search_queries") or [state["goal"]]
    sources = list(settings.search_sources)
    if settings.tavily_api_key and "tavily" not in sources:
        sources.insert(0, "tavily")
    ctx.emit(
        "research",
        "started",
        f"Round {round_no}: searching {', '.join(sources)} for {len(queries)} rewritten queries",
        {"queries": queries},
    )
    result = search_news(
        plan.get("topic") or state["goal"],
        queries=queries,
        keywords=plan.get("keywords"),
        lookback_days=int(plan.get("lookback_days") or settings.default_lookback_days),
        sources=sources,
        query_context=state.get("goal") or "",
    )
    for entry in result["log"]:
        status = "warning" if entry["error"] else "info"
        detail = entry["error"] or f"{entry['count']} results{' (cached)' if entry['cached'] else ''}"
        ctx.emit("research", status, f"search_news[{entry['source']}] '{entry['query'][:50]}': {detail}")

    merged, removed = dedupe_articles(annotate_query_ranks((state.get("candidates") or []) + result["articles"]))
    relevant = relevant_candidates(merged, plan.get("keywords") or [])
    log = list(state.get("research_log") or []) + [{**e, "round": round_no} for e in result["log"]]
    ctx.emit(
        "research",
        "completed",
        f"Found {len(merged)} unique articles ({removed} duplicates removed), {len(relevant)} look relevant",
        {"total": len(merged), "relevant": len(relevant)},
    )
    ctx.publish(research_log=log, candidates_count=len(merged))
    return {"candidates": merged, "research_log": log, "research_round": round_no}


def route_after_research(state: dict) -> str:
    settings = get_settings()
    plan = state["plan"]
    relevant = relevant_candidates(state.get("candidates") or [], plan.get("keywords") or [])
    need = int(plan.get("article_count") or 5)
    if len(relevant) < need and int(state.get("research_round") or 0) < settings.max_research_rounds:
        return "broaden"
    return "fuse"


def broaden_node(state: dict) -> dict:
    """Autonomously widen the search: longer window + broader keyword queries."""
    ctx = ctx_for(state)
    plan = dict(state["plan"])
    keywords = plan.get("keywords") or []
    old_queries = plan.get("search_queries") or []
    new_queries = []
    for kw in keywords:
        if kw not in old_queries and kw not in new_queries and len(kw) > 3:
            new_queries.append(kw)
        if len(new_queries) >= 3:
            break
    if not new_queries:
        new_queries = old_queries
    goal = state.get("goal") or ""
    broader = [make_rewrite(goal, query, "broader") for query in new_queries if collapse_ws(query)]
    existing = [rewrite for rewrite in (plan.get("rewritten_queries") or []) if rewrite.get("query")]
    seen = set()
    merged_rewrites = []
    for rewrite in existing + broader:
        key = rewrite["query"].lower()
        if key in seen:
            continue
        seen.add(key)
        merged_rewrites.append(rewrite)
    plan["rewritten_queries"] = merged_rewrites[:6]
    plan["search_queries"] = [rewrite["query"] for rewrite in broader] or old_queries
    plan["lookback_days"] = min(30, int(plan.get("lookback_days") or 7) * 2)
    ctx.emit(
        "research",
        "info",
        f"Too few relevant articles; broadening search to {plan['lookback_days']} days with queries: "
        + ", ".join(new_queries),
    )
    return {"plan": plan}
