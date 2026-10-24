"""Deterministic duplicate detection for articles."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .text import normalize_url, tokenize

_PUBLISHER_SUFFIX_RE = re.compile(r"\s+[-–|]\s+[^-–|]{2,60}$")


def normalize_title(title: str) -> str:
    title = _PUBLISHER_SUFFIX_RE.sub("", title or "")
    return re.sub(r"[^a-z0-9 ]+", "", title.lower()).strip()


def titles_similar(a: str, b: str, ratio: float = 0.82, jaccard: float = 0.6) -> bool:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if SequenceMatcher(None, na, nb).ratio() >= ratio:
        return True
    ta, tb = set(tokenize(na)), set(tokenize(nb))
    if len(ta) >= 4 and len(tb) >= 4:
        return len(ta & tb) / len(ta | tb) >= jaccard
    return False


def _richness(article: dict) -> tuple:
    """Prefer direct publisher URLs, longer content and known dates."""
    return (
        0 if "news.google.com" in (article.get("url") or "") else 1,
        1 if article.get("published_at") else 0,
        len(article.get("content") or "") + len(article.get("excerpt") or ""),
    )


def _merge_query_meta(primary: dict, secondary: dict) -> dict:
    """Keep the richer article and the query hits of both copies.

    Reciprocal rank fusion needs every query that surfaced the story, plus the
    best rank and retrieval score seen for it.
    """
    art = dict(primary)
    queries: list[str] = []
    for source in (primary, secondary):
        for query in list(source.get("queries") or []):
            if query and query not in queries:
                queries.append(query)
        query = source.get("query")
        if query and query not in queries:
            queries.append(query)
    ranks: dict[str, int] = {}
    for source in (primary, secondary):
        for query, rank in (source.get("query_ranks") or {}).items():
            try:
                rank_i = int(rank)
            except (TypeError, ValueError):
                continue
            if query not in ranks or rank_i < ranks[query]:
                ranks[query] = rank_i
    scores = [
        float(source["retrieval_score"])
        for source in (primary, secondary)
        if isinstance(source.get("retrieval_score"), (int, float))
    ]
    if queries:
        art["queries"] = queries
    if ranks:
        art["query_ranks"] = ranks
    if scores:
        art["retrieval_score"] = max(scores)
    return art


def dedupe_articles(articles: list[dict]) -> tuple[list[dict], int]:
    """Remove identical URLs and substantially overlapping stories.

    Returns (unique_articles, removed_count). When two items describe the same
    story the richer one (direct URL, date, more text) is kept.
    """
    kept: list[dict] = []
    seen_urls: dict[str, int] = {}
    removed = 0
    for art in articles:
        key = normalize_url(art.get("url", ""))
        if key and key in seen_urls:
            idx = seen_urls[key]
            if _richness(art) > _richness(kept[idx]):
                kept[idx] = _merge_query_meta(art, kept[idx])
            else:
                kept[idx] = _merge_query_meta(kept[idx], art)
            removed += 1
            continue
        dup_idx = next(
            (i for i, k in enumerate(kept) if titles_similar(k.get("title", ""), art.get("title", ""))), None
        )
        if dup_idx is not None:
            if _richness(art) > _richness(kept[dup_idx]):
                seen_urls[key] = dup_idx
                kept[dup_idx] = _merge_query_meta(art, kept[dup_idx])
            else:
                kept[dup_idx] = _merge_query_meta(kept[dup_idx], art)
            removed += 1
            continue
        seen_urls[key] = len(kept)
        kept.append(art)
    return kept, removed
