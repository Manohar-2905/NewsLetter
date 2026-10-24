"""Summarization: one grounded summary per selected article."""

from __future__ import annotations

from ...services.llm_base import LLMQuotaError
from ...tools.summarize_article import fallback_summary, summarize_articles
from .common import ctx_for, quota_warning, usable_llm


def summarize_node(state: dict) -> dict:
    ctx = ctx_for(state)
    selected = state.get("selected") or []
    plan = state["plan"]
    warnings = list(state.get("warnings") or [])
    ctx.emit("summarization", "started", f"Summarizing {len(selected)} articles from their source text")

    llm = usable_llm(ctx)
    if llm is None:
        summaries = [fallback_summary(a) for a in selected]
        warnings.append("No model available for summaries; publisher excerpts/headlines are shown instead.")
    else:
        try:
            summaries, extra = summarize_articles(selected, llm, plan.get("topic") or state["goal"], plan.get("tone", "professional"))
            warnings += extra
            for w in extra:
                ctx.emit("summarization", "warning", w)
        except LLMQuotaError as exc:
            warnings.append(quota_warning(ctx, "summarization", exc))
            summaries = [fallback_summary(a) for a in selected]

    limited = sum(1 for s in summaries if s.get("limited_info"))
    ctx.emit(
        "summarization",
        "completed",
        f"Summarized {len(summaries)} articles"
        + (f" ({limited} based on limited information, disclosed in the newsletter)" if limited else ""),
    )
    ctx.publish(summaries=summaries)
    return {"summaries": summaries, "warnings": warnings}
