"""Tool: summarize_article — source-grounded summaries.

`summarize_articles` sends all selected articles in ONE request to save quota;
any article whose summary is missing or invalid is retried individually with
`summarize_article`.
"""

from __future__ import annotations

import logging

from ..agent.prompts import GROUNDING_SYSTEM, source_block
from ..services.llm_base import BaseLLM, LLMError, LLMQuotaError
from ..utils.text import collapse_ws, truncate

logger = logging.getLogger(__name__)

BASIS_LABEL = {
    "full": "full_text",
    "excerpt_only": "excerpt",
}


def _basis(article: dict) -> str:
    return BASIS_LABEL.get(article.get("content_status"), "headline_only")


def _instructions(topic: str, tone: str) -> str:
    return (
        f"Newsletter topic: {topic}\n"
        f"Tone: {tone}\n"
        "You are an expert technical intelligence analyst and editor. "
        "For each given source, generate a high-density, authoritative, and fact-anchored summary.\n\n"
        "EDITORIAL GUIDELINES:\n"
        "1. summary (2 to 4 sentences, 50-95 words):\n"
        "   - Lead with the breakthrough or core event immediately. Never open with meta-chatter like "
        "'This article reports', 'According to', or 'In a recent post'. State what occurred directly.\n"
        "   - Anchor with concrete specifics from the source text: include metrics, CVE identifiers, percentages, "
        "dollar amounts, company/project names, architectural decisions, and key technical details.\n"
        "   - Explain the mechanism: briefly describe HOW it works or WHY it happened based strictly on the text.\n"
        "   - If available_material is 'headline only', provide ONE direct, sharp sentence capturing the core reported event "
        "without echoing redundant introductory phrases.\n"
        "2. key_takeaway (exactly 1 sentence):\n"
        "   - MUST begin with 'Why it matters: '.\n"
        "   - Explain the strategic implication, technical consequence, or broader impact on the industry/topic.\n"
        "   - Focus on analytical reasoning derived from the reported facts without introducing unsupported claims.\n"
    )


def _finalize(article: dict, raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    summary = collapse_ws(str(raw.get("summary", "")))
    takeaway = collapse_ws(str(raw.get("key_takeaway", "")))
    if len(summary) < 20:
        return None
    if takeaway and not takeaway.lower().startswith("why it matters:"):
        takeaway = f"Why it matters: {takeaway}"
    basis = _basis(article)
    return {
        "headline": article.get("title", ""),
        "publisher": article.get("publisher", ""),
        "published_at": article.get("published_at"),
        "url": article.get("url", ""),
        "summary": truncate(summary, 900),
        "key_takeaway": truncate(takeaway, 300) if takeaway else "",
        "based_on": basis,
        "limited_info": basis != "full_text",
    }


def summarize_article(
    article: dict, llm: BaseLLM, topic: str, tone: str = "professional", feedback: str = ""
) -> dict:
    """Summarise a single article. Raises LLMError on provider failure."""
    prompt = (
        _instructions(topic, tone)
        + (f"\nReviewer feedback to fix: {feedback}\n" if feedback else "")
        + '\nReturn JSON: {"summary": "...", "key_takeaway": "..."}\n\n'
        + source_block(0, article)
    )
    raw = llm.generate_json(prompt, system=GROUNDING_SYSTEM, max_tokens=600)
    result = _finalize(article, raw)
    if result is None:
        raise ValueError("summary missing or too short")
    return result


def fallback_summary(article: dict) -> dict:
    """Deterministic, honest summary used when the model cannot summarise."""
    excerpt = article.get("excerpt") or ""
    text = truncate(excerpt, 400) if excerpt else f"Headline only: {article.get('title', '')}."
    return {
        "headline": article.get("title", ""),
        "publisher": article.get("publisher", ""),
        "published_at": article.get("published_at"),
        "url": article.get("url", ""),
        "summary": text,
        "key_takeaway": "",
        "based_on": "excerpt" if excerpt else "headline_only",
        "limited_info": True,
        "note": "AI summary unavailable; showing the publisher's excerpt/headline instead.",
    }


def summarize_articles(
    articles: list[dict], llm: BaseLLM, topic: str, tone: str = "professional"
) -> tuple[list[dict], list[str]]:
    """Summarise many articles with as few calls as possible.

    Returns (summaries in the same order, warnings).
    """
    warnings: list[str] = []
    results: list[dict | None] = [None] * len(articles)
    if not articles:
        return [], warnings

    prompt = (
        _instructions(topic, tone)
        + '\nReturn JSON: {"items": [{"id": <source id>, "summary": "...", "key_takeaway": "..."}]}\n\n'
        + "\n\n".join(source_block(i, a, max_chars=1800) for i, a in enumerate(articles))
    )
    try:
        raw = llm.generate_json(prompt, system=GROUNDING_SYSTEM, max_tokens=min(400 * len(articles) + 200, 4096))
        items = raw.get("items", []) if isinstance(raw, dict) else raw
        for item in items or []:
            try:
                idx = int(item.get("id"))
            except (TypeError, ValueError, AttributeError):
                continue
            if 0 <= idx < len(articles) and results[idx] is None:
                results[idx] = _finalize(articles[idx], item)
    except LLMQuotaError:
        raise
    except LLMError as exc:
        warnings.append(f"Batch summarization failed ({exc}); summarizing articles one by one.")

    for i, art in enumerate(articles):
        if results[i] is not None:
            continue
        try:
            results[i] = summarize_article(art, llm, topic, tone)
        except LLMQuotaError:
            raise
        except (LLMError, ValueError) as exc:
            logger.warning("summarize_article :: failed for %s :: %s", art.get("url"), exc)
            warnings.append(f"Could not summarize '{truncate(art.get('title', ''), 60)}': showing excerpt instead.")
            results[i] = fallback_summary(art)
    return [r for r in results if r is not None], warnings
