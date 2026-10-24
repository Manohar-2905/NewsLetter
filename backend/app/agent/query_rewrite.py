"""Rewrite one user goal into several retrieval queries.

Each rewrite is a short search string plus a prompt. The prompt always
repeats the original user request, so later answers stay inside that scope
even when the search string is a narrower angle.
"""

from __future__ import annotations

from ..utils.text import collapse_ws, keywords_from_goal, truncate

ANGLE_CYCLE = ("paraphrase", "specifics", "impact", "recent")


def make_rewrite(goal: str, query: str, angle: str) -> dict:
    query = collapse_ws(query)[:120]
    angle = collapse_ws(angle) or "paraphrase"
    prompt = (
        f"Original user request:\n{goal.strip()}\n\n"
        f"Rewritten focus ({angle}):\n{query}\n\n"
        "Answer only this rewritten focus. The original user request is the scope: "
        "keep every constraint it states, and do not drift into unrelated topics."
    )
    return {"query": query, "angle": angle, "prompt": prompt}


def _dedupe(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for query in queries:
        text = collapse_ws(query)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def deterministic_queries(goal: str, keywords: list[str], topic: str) -> list[str]:
    """Short, diverse search strings. The full goal is attached later, not here."""
    keywords = [collapse_ws(k) for k in keywords if collapse_ws(k)]
    topic = collapse_ws(topic) or " ".join(keywords[:5]) or truncate(collapse_ws(goal), 80)
    candidates: list[str] = []
    if topic:
        candidates.append(topic)
    if len(keywords) >= 2:
        candidates.append(" ".join(keywords[:3]))
    if keywords:
        candidates.append(f"{keywords[0]} latest news")
        if len(keywords) >= 2:
            candidates.append(f"{keywords[0]} {keywords[1]} impact")
        else:
            candidates.append(f"{topic} implications")
    elif topic:
        candidates.append(f"{topic} implications")
    return _dedupe(candidates)


def _as_pairs(queries: list) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in queries or []:
        angle = ""
        if isinstance(item, dict):
            text = item.get("query") or item.get("text") or ""
            angle = collapse_ws(str(item.get("angle") or ""))
        else:
            text = str(item)
        text = collapse_ws(text)[:120]
        if text:
            pairs.append((text, angle))
    return pairs


def normalize_rewrites(
    goal: str,
    queries: list | None,
    keywords: list[str] | None,
    topic: str,
    limit: int = 4,
) -> list[dict]:
    """Turn planner queries into prompts that still contain the original goal.

    Incoming queries stay first (the planner's wording). Extra angles are added
    until `limit` so retrieval is not a single phrasing of the request.
    """
    goal = collapse_ws(goal)
    if not goal:
        return []
    limit = max(1, limit)
    keywords = keywords or keywords_from_goal(goal)
    pairs = _as_pairs(queries or [])
    if len(pairs) < 2:
        for query in deterministic_queries(goal, keywords, topic):
            if any(query.lower() == existing.lower() for existing, _angle in pairs):
                continue
            pairs.append((query, ""))
            if len(pairs) >= limit:
                break
    else:
        for query in deterministic_queries(goal, keywords, topic):
            if len(pairs) >= limit:
                break
            if any(query.lower() == existing.lower() for existing, _angle in pairs):
                continue
            pairs.append((query, ""))

    rewrites: list[dict] = []
    seen: set[str] = set()
    for index, (query, angle) in enumerate(pairs):
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        rewrites.append(make_rewrite(goal, query, angle or ANGLE_CYCLE[index % len(ANGLE_CYCLE)]))
        if len(rewrites) >= limit:
            break
    if rewrites and rewrites[0]["angle"] not in ANGLE_CYCLE:
        rewrites[0]["angle"] = "paraphrase"
        rewrites[0]["prompt"] = make_rewrite(goal, rewrites[0]["query"], "paraphrase")["prompt"]
    return rewrites
