"""Rank rewritten-query hits, then rank the answer each rewrite produced.

Article rank is reciprocal rank fusion across the queries that retrieved a
URL, blended with keyword relevance and the search engine's own score.
Response rank prefers answers that stay on the original request and cite
the stronger articles. Articles that only support a weak answer are dropped
once enough stronger ones are already in the pool.
"""

from __future__ import annotations

from ..utils.text import collapse_ws, tokenize, truncate

RRF_K = 60


def annotate_query_ranks(articles: list[dict]) -> list[dict]:
    """Record 1-based rank of each hit inside the query that returned it.

    Articles that already carry `query_ranks` (an earlier research round) are
    left as they are. New hits continue the counter for their query.
    """
    counters: dict[str, int] = {}
    for art in articles:
        for query, rank in (art.get("query_ranks") or {}).items():
            try:
                counters[query] = max(counters.get(query, 0), int(rank))
            except (TypeError, ValueError):
                continue
    annotated: list[dict] = []
    for art in articles:
        item = dict(art)
        if item.get("query_ranks"):
            if not item.get("queries"):
                item["queries"] = [query for query in item["query_ranks"] if query]
            annotated.append(item)
            continue
        query = collapse_ws(str(item.get("query") or ""))
        if not query:
            item["query_ranks"] = {}
            item["queries"] = []
            annotated.append(item)
            continue
        counters[query] = counters.get(query, 0) + 1
        item["query_ranks"] = {query: counters[query]}
        item["queries"] = [query]
        annotated.append(item)
    return annotated


def rrf_value(article: dict) -> float:
    ranks = article.get("query_ranks") or {}
    total = 0.0
    for rank in ranks.values():
        try:
            total += 1.0 / (RRF_K + int(rank))
        except (TypeError, ValueError):
            continue
    return total


def overlap_score(keywords: list[str], text: str) -> float:
    """Share of keywords that actually appear in `text` (0..1)."""
    text_l = (text or "").lower()
    tokens = set(tokenize(text_l))
    usable = [str(kw).strip() for kw in keywords if str(kw).strip()]
    if not usable:
        return 0.5
    hits = 0
    for kw in usable:
        kw_l = kw.lower()
        parts = tokenize(kw_l)
        if kw_l in text_l or (parts and all(part in tokens for part in parts)):
            hits += 1
    return hits / len(usable)


def rank_articles(articles: list[dict], keywords: list[str], lookback_days: int) -> list[dict]:
    """Fuse per-query ranks into one list. `lookback_days` is unused; kept for callers."""
    del lookback_days
    from .nodes.selector import relevance, source_quality
    if not articles:
        return []
    raw = [rrf_value(article) for article in articles]
    max_rrf = max(raw) or 1.0
    ranked: list[dict] = []
    for article, rrf in zip(articles, raw):
        rel = relevance(article, keywords)
        qual = source_quality(article)
        retrieval = article.get("retrieval_score")
        retrieval_score = float(retrieval) if isinstance(retrieval, (int, float)) else rel
        fused = 0.40 * (rrf / max_rrf) + 0.30 * rel + 0.15 * retrieval_score + 0.15 * qual
        ranked.append({**article, "rrf": round(rrf, 4), "fusion_score": round(fused, 4)})
    ranked.sort(key=lambda article: article["fusion_score"], reverse=True)
    return ranked


def articles_for_rewrite(articles: list[dict], rewrite: dict, limit: int = 3) -> list[dict]:
    query = (rewrite.get("query") or "").lower()
    matched = []
    for article in articles:
        names = [str(item).lower() for item in (article.get("queries") or [])]
        if query and (query in names or str(article.get("query") or "").lower() == query):
            matched.append(article)
    matched.sort(key=lambda article: (article.get("query_ranks") or {}).get(rewrite.get("query"), 999))
    if matched:
        return matched[:limit]
    return articles[:limit]


def choose_rewrites(rewrites: list[dict], articles: list[dict], limit: int) -> list[dict]:
    """Prefer the paraphrase of the original request, then the rewrites that actually retrieved."""
    limit = max(1, limit)
    chosen: list[dict] = []
    seen: set[str] = set()

    def add(rewrite: dict) -> None:
        key = (rewrite.get("query") or "").lower()
        if not key or key in seen:
            return
        seen.add(key)
        chosen.append(rewrite)

    for rewrite in rewrites:
        if rewrite.get("angle") == "paraphrase":
            add(rewrite)
            break
    rest = sorted(rewrites, key=lambda rewrite: len(articles_for_rewrite(articles, rewrite, limit=20)), reverse=True)
    for rewrite in rest:
        add(rewrite)
        if len(chosen) >= limit:
            break
    return chosen[:limit]


def extractive_responses(bundles: list[dict], keywords: list[str]) -> list[dict]:
    """Grounded fallback: the answer is the retrieved text, not a new claim."""
    responses = []
    for index, bundle in enumerate(bundles):
        rewrite = bundle["rewrite"]
        snippets = []
        for article in bundle["articles"][:3]:
            text = collapse_ws(article.get("excerpt") or article.get("content") or article.get("title") or "")
            if text:
                snippets.append(truncate(text, 280))
        answer = " ".join(snippets)
        responses.append(
            {
                "id": index,
                "query": rewrite.get("query") or "",
                "angle": rewrite.get("angle") or "",
                "prompt": rewrite.get("prompt") or "",
                "answer": answer,
                "relevance": round(overlap_score(keywords, f"{rewrite.get('query', '')} {answer}") * 10, 2),
                "supporting_urls": [article["url"] for article in bundle["articles"] if article.get("url")],
                "origin": "extractive",
            }
        )
    return responses


def apply_model_responses(bundles: list[dict], raw: dict | None, keywords: list[str]) -> list[dict]:
    """Keep a model answer only when it is usable and its URLs were actually retrieved."""
    fallback = extractive_responses(bundles, keywords)
    by_id: dict[int, dict] = {}
    items = raw.get("responses") if isinstance(raw, dict) else None
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            by_id[int(item.get("id"))] = item
        except (TypeError, ValueError):
            continue
    allowed = {article.get("url") for bundle in bundles for article in bundle["articles"] if article.get("url")}
    merged = []
    for index, bundle in enumerate(bundles):
        base = fallback[index]
        item = by_id.get(index)
        if not item:
            merged.append(base)
            continue
        answer = collapse_ws(str(item.get("answer") or ""))
        if len(answer) < 40:
            merged.append(base)
            continue
        urls = [url for url in (item.get("supporting_urls") or []) if url in allowed]
        try:
            relevance = max(0.0, min(10.0, float(item.get("relevance"))))
        except (TypeError, ValueError):
            relevance = base["relevance"]
        merged.append(
            {
                **base,
                "answer": truncate(answer, 900),
                "relevance": round(relevance, 2),
                "supporting_urls": urls or base["supporting_urls"],
                "origin": "model",
            }
        )
    return merged


def rank_responses(responses: list[dict], articles: list[dict], keywords: list[str]) -> list[dict]:
    by_url = {article.get("url"): article for article in articles if article.get("url")}
    ranked = []
    for response in responses:
        urls = response.get("supporting_urls") or []
        support_articles = [by_url[url] for url in urls if url in by_url]
        if support_articles:
            support = sum(float(article.get("fusion_score") or 0) for article in support_articles) / len(support_articles)
        else:
            support = 0.0
        relevance_score = max(0.0, min(10.0, float(response.get("relevance") or 0))) / 10.0
        goal_overlap = overlap_score(keywords, response.get("answer") or "")
        score = 0.55 * relevance_score + 0.25 * support + 0.20 * goal_overlap
        ranked.append({**response, "rank_score": round(score, 4)})
    ranked.sort(key=lambda response: response["rank_score"], reverse=True)
    for index, response in enumerate(ranked, start=1):
        response["rank"] = index
    return ranked


def articles_from_ranked_responses(articles: list[dict], responses: list[dict], need: int) -> tuple[list[dict], int]:
    """Keep articles cited by the strongest answers, then fill to a selection pool.

    A weak answer's articles are left out once `need` stronger articles are
    already chosen. The pool still grows to about twice `need` from the fused
    ranking so the selector can prefer diversity.
    """
    by_url = {article.get("url"): article for article in articles if article.get("url")}
    if not articles:
        return [], 0
    order: list[str] = []
    seen: set[str] = set()
    best = float(responses[0]["rank_score"]) if responses else 0.0

    def is_weak(response: dict) -> bool:
        if int(response.get("rank") or 1) <= 1 or not best:
            return False
        return float(response.get("rank_score") or 0) < best * 0.72

    for response in responses:
        if is_weak(response) and len(seen) >= need:
            continue
        for url in response.get("supporting_urls") or []:
            if url in by_url and url not in seen:
                seen.add(url)
                order.append(url)

    rejected: set[str] = set()
    for response in responses:
        if is_weak(response):
            for url in response.get("supporting_urls") or []:
                if url not in seen:
                    rejected.add(url)

    target = min(len(by_url), max(need * 2, 8))
    for article in articles:
        if len(order) >= target:
            break
        url = article.get("url")
        if not url or url in seen:
            continue
        if url in rejected and len(order) >= need:
            continue
        seen.add(url)
        order.append(url)

    kept = [by_url[url] for url in order if url in by_url]
    if len(kept) < min(need, len(by_url)):
        for article in articles:
            url = article.get("url")
            if url and url not in seen:
                kept.append(article)
                seen.add(url)
            if len(kept) >= min(need, len(by_url)):
                break
    return kept, max(0, len(articles) - len(kept))


def compose_brief(responses: list[dict], limit: int = 3) -> str:
    """Report made only from the highest-ranked rewritten answers."""
    chunks = []
    for response in responses[:limit]:
        answer = collapse_ws(response.get("answer") or "")
        if len(answer) < 20:
            continue
        query = collapse_ws(response.get("query") or "Focus")
        chunks.append(f"{query}: {truncate(answer, 420)}")
    return "\n\n".join(chunks)
