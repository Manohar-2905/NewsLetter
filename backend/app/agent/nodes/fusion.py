"""Rank search hits, answer each rewritten prompt, then keep the best articles.

One model call answers every rewrite. Each prompt already contains the
original user request. If the model is unavailable, the answer is the
retrieved excerpt itself, and ranking still runs.
"""

from __future__ import annotations

from ...config import get_settings
from ...services.llm_base import LLMError, LLMQuotaError
from ...utils.text import truncate
from ..prompts import FUSION_SYSTEM, source_block
from ..query_rewrite import normalize_rewrites
from ..ranking import (
    apply_model_responses,
    articles_for_rewrite,
    articles_from_ranked_responses,
    choose_rewrites,
    compose_brief,
    extractive_responses,
    rank_articles,
    rank_responses,
)
from .common import ctx_for, quota_warning, usable_llm


def _bundles(rewrites: list[dict], articles: list[dict], limit: int) -> list[dict]:
    chosen = choose_rewrites(rewrites, articles, limit)
    return [{"rewrite": rewrite, "articles": articles_for_rewrite(articles, rewrite, limit=3)} for rewrite in chosen]


def _prompt(bundles: list[dict]) -> str:
    blocks = []
    for index, bundle in enumerate(bundles):
        sources = "\n".join(source_block(i, article, max_chars=700) for i, article in enumerate(bundle["articles"]))
        blocks.append(
            f'<prompt id="{index}">\n{bundle["rewrite"]["prompt"]}\n\n'
            f"Sources for this prompt:\n{sources or '(no sources)'}\n</prompt>"
        )
    return (
        "Below are rewritten research prompts. Each one repeats the original user request and one rewritten focus.\n"
        "For each prompt, write a grounded answer in 2-4 sentences using ONLY its <source> blocks. "
        "Score relevance from 0 to 10 for how well those sources answer the original user request. "
        "supporting_urls must be copied from the sources. Do not invent URLs, numbers, names, or dates.\n"
        'Return JSON: {"responses": [{"id": 0, "answer": "...", "relevance": 8, "supporting_urls": ["https://..."]}]}\n\n'
        "Rewritten research prompts:\n\n" + "\n\n".join(blocks)
    )


def _public(response: dict) -> dict:
    return {
        "rank": response.get("rank"),
        "query": response.get("query"),
        "angle": response.get("angle"),
        "prompt": response.get("prompt"),
        "answer": response.get("answer"),
        "relevance": response.get("relevance"),
        "rank_score": response.get("rank_score"),
        "supporting_urls": response.get("supporting_urls") or [],
        "origin": response.get("origin"),
    }


def fuse_node(state: dict) -> dict:
    ctx = ctx_for(state)
    settings = get_settings()
    plan = state.get("plan") or {}
    goal = state.get("goal") or ""
    warnings = list(state.get("warnings") or [])
    articles = list(state.get("candidates") or [])
    rewrites = list(plan.get("rewritten_queries") or [])
    if not rewrites:
        rewrites = normalize_rewrites(
            goal,
            plan.get("search_queries") or [],
            plan.get("keywords") or [],
            plan.get("topic") or goal,
            limit=settings.max_rewritten_queries,
        )

    ctx.emit(
        "ranking",
        "started",
        f"Ranking articles for {len(rewrites)} rewritten queries, then ranking each answer",
        {"queries": [rewrite.get("query") for rewrite in rewrites]},
    )
    if not articles:
        ctx.emit("ranking", "completed", "No articles to rank")
        return {"ranked_responses": [], "research_brief": "", "warnings": warnings}

    ranked = rank_articles(articles, plan.get("keywords") or [], int(plan.get("lookback_days") or 7))
    bundles = _bundles(rewrites, ranked, settings.max_rewritten_queries)
    keywords = plan.get("keywords") or []
    responses = None
    llm = usable_llm(ctx)
    if llm is not None and bundles:
        try:
            raw = llm.generate_json(_prompt(bundles), system=FUSION_SYSTEM, max_tokens=1400)
            responses = apply_model_responses(bundles, raw if isinstance(raw, dict) else None, keywords)
        except LLMQuotaError as exc:
            warnings.append(quota_warning(ctx, "ranking", exc))
        except LLMError as exc:
            ctx.emit("ranking", "warning", f"Answer ranking fell back to retrieved excerpts: {exc}")
    if not responses:
        responses = extractive_responses(bundles, keywords)

    ranked_responses = rank_responses(responses, ranked, keywords)
    need = int(plan.get("article_count") or 5)
    kept, dropped = articles_from_ranked_responses(ranked, ranked_responses, need)
    if not kept:
        kept = ranked
        dropped = 0
    brief = compose_brief(ranked_responses)
    top_queries = ", ".join(truncate(response.get("query") or "", 40) for response in ranked_responses[:3])
    ctx.emit(
        "ranking",
        "completed",
        f"Kept {len(kept)} articles from the top answers ({dropped} weaker matches set aside). "
        f"Highest: {top_queries}",
        {"dropped": dropped, "responses": [_public(response) for response in ranked_responses]},
    )
    return {
        "candidates": kept,
        "ranked_responses": [_public(response) for response in ranked_responses],
        "research_brief": brief,
        "warnings": warnings,
    }
