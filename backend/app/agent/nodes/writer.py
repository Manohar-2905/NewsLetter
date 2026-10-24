"""Writing: generate (or regenerate) the newsletter."""

from __future__ import annotations

from ...services.llm_base import LLMQuotaError
from ...tools.generate_newsletter import generate_newsletter
from .common import ctx_for, quota_warning, usable_llm


def build_disclosures(state: dict) -> list[str]:
    summaries = state.get("summaries") or []
    requested = int((state.get("plan") or {}).get("article_count") or 5)
    notes = []
    if 0 < len(summaries) < requested:
        notes.append(
            f"Only {len(summaries)} sufficiently relevant articles were found (target was {requested}); "
            "we did not pad the newsletter with weaker or invented items."
        )
    limited = [str(i + 1) for i, s in enumerate(summaries) if s.get("limited_info")]
    if limited:
        notes.append(
            f"Article(s) {', '.join(limited)} were summarized from a headline or short excerpt because the full "
            "text was not accessible."
        )
    undated = [str(i + 1) for i, s in enumerate(summaries) if not s.get("published_at")]
    if undated:
        notes.append(f"Publication date not available for article(s) {', '.join(undated)}.")
    if limited:
        notes.append("'Key takeaway' lines are AI interpretations of the reported facts.")
    return notes


def write_node(state: dict) -> dict:
    ctx = ctx_for(state)
    plan = state["plan"]
    cfg = state.get("config") or {}
    revision = int(state.get("revision_count") or 0)
    feedback = state.get("revision_feedback") or ""
    previous = state.get("newsletter") if feedback else None
    warnings = list(state.get("warnings") or [])
    label = "Revising the newsletter" if feedback else "Writing the newsletter"
    ctx.emit("revision" if feedback else "writing", "started", label)

    selected_urls = {article.get("url") for article in (state.get("selected") or []) if article.get("url")}
    ranked = [
        response
        for response in (state.get("ranked_responses") or [])
        if any(url in selected_urls for url in (response.get("supporting_urls") or []))
    ]
    config = {
        "topic": plan.get("topic") or state["goal"],
        "tone": cfg.get("tone", "professional"),
        "output_format": cfg.get("output_format", "html"),
        "disclosures": build_disclosures(state),
        "ranked_responses": ranked,
    }
    llm = usable_llm(ctx)
    try:
        newsletter, extra = generate_newsletter(state.get("summaries") or [], config, llm=llm,
                                                feedback=feedback, previous=previous)
    except LLMQuotaError as exc:
        warnings.append(quota_warning(ctx, "writing", exc))
        newsletter, extra = generate_newsletter(state.get("summaries") or [], config, llm=None)
    warnings += extra
    ctx.emit(
        "revision" if feedback else "writing",
        "completed",
        f"Draft ready: “{newsletter['subject']}”" + (f" (revision {revision})" if feedback else ""),
    )
    ctx.publish(newsletter=_public(newsletter))
    return {"newsletter": newsletter, "warnings": warnings, "revision_feedback": ""}


def _public(nl: dict) -> dict:
    return {
        k: nl.get(k)
        for k in (
            "subject", "title", "date", "format", "html", "markdown", "content",
            "disclosures", "research_brief", "ranked_responses",
        )
    }
