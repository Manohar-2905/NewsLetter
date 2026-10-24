"""Tool: search_news — retrieves REAL news articles from free sources.

Sources (all free, no key needed unless noted):
  * google_news : Google News RSS search feed
  * gdelt       : GDELT DOC 2.0 API (public)
  * rss         : public publisher RSS feeds (configurable list)
  * hackernews  : Hacker News Algolia search API (public)
  * tavily      : semantic news search (needs TAVILY_API_KEY). Rewritten queries
                  are sent with the original user request attached.

Nothing here asks an LLM for news. If every source fails, the result is an
empty list plus a log explaining why.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from ..config import Settings, get_settings
from ..utils.cache import FileCache
from ..utils.text import (
    clean_html,
    collapse_ws,
    domain_of,
    iso_or_none,
    is_valid_http_url,
    parse_date,
    sanitize_untrusted,
    tokenize,
    truncate,
)

logger = logging.getLogger(__name__)

USER_AGENT = "NewsletterAgent/1.0 (personal research bot; respects robots.txt)"
GDELT_MIN_INTERVAL = 5.5  # GDELT asks for at most one request every 5 seconds

_gdelt_lock = threading.Lock()
_gdelt_last_call = 0.0
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class SearchError(Exception):
    pass


# ---------------------------------------------------------------------------
# HTTP helper (tests monkeypatch this)
# ---------------------------------------------------------------------------
def http_get(url: str, params: dict | None = None, timeout: int = 10, headers: dict | None = None):
    hdrs = {"User-Agent": USER_AGENT, "Accept-Language": "en"}
    hdrs.update(headers or {})
    return requests.get(url, params=params, timeout=timeout, headers=hdrs)


def _make_article(**kw) -> dict:
    url = kw.get("url", "")
    return {
        "title": collapse_ws(kw.get("title", "")),
        "url": url,
        "publisher": collapse_ws(kw.get("publisher") or domain_of(url) or "Unknown publisher"),
        "domain": kw.get("domain") or domain_of(kw.get("publisher_url") or url),
        "published_at": kw.get("published_at"),
        "excerpt": truncate(kw.get("excerpt") or "", 600),
        "content": "",
        "content_status": "excerpt_only" if kw.get("excerpt") else "title_only",
        "source_api": kw.get("source_api", ""),
        "query": kw.get("query", ""),
    }


def _within_lookback(published_at: str | None, lookback_days: int) -> bool:
    if not published_at:
        return True  # keep, but it is penalised and disclosed later
    dt = parse_date(published_at)
    if dt is None:
        return True
    return dt >= datetime.now(timezone.utc) - timedelta(days=lookback_days + 1)


# ---------------------------------------------------------------------------
# Individual sources
# ---------------------------------------------------------------------------
def search_google_news(query: str, lookback_days: int, settings: Settings) -> list[dict]:
    lang, country = settings.news_language, settings.news_country
    url = (
        f"https://news.google.com/rss/search?q={quote_plus(query)}+when:{lookback_days}d"
        f"&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
    )
    resp = http_get(url, timeout=settings.http_timeout_seconds)
    if resp.status_code != 200:
        raise SearchError(f"Google News RSS returned HTTP {resp.status_code}")
    feed = feedparser.parse(resp.content)
    articles = []
    for entry in feed.entries[: settings.max_candidates_per_query]:
        source = entry.get("source") or {}
        publisher = source.get("title") or ""
        title = entry.get("title", "")
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(f" - {publisher}")]
        excerpt = clean_html(entry.get("summary", ""))
        # Google News summaries usually just repeat the headline + publisher.
        if excerpt.startswith(title[:40]):
            excerpt = ""
        articles.append(
            _make_article(
                title=title,
                url=entry.get("link", ""),
                publisher=publisher,
                publisher_url=source.get("href", ""),
                published_at=iso_or_none(entry.get("published")),
                excerpt=excerpt,
                source_api="google_news",
                query=query,
            )
        )
    return articles


def _gdelt_wait():
    global _gdelt_last_call
    with _gdelt_lock:
        wait = GDELT_MIN_INTERVAL - (time.time() - _gdelt_last_call)
        if wait > 0:
            time.sleep(wait)
        _gdelt_last_call = time.time()


def search_gdelt(query: str, lookback_days: int, settings: Settings) -> list[dict]:
    _gdelt_wait()
    params = {
        "query": f"{query} sourcelang:english",
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(min(settings.max_candidates_per_query, 75)),
        "timespan": f"{min(lookback_days, 90)}d",
        "sort": "hybridrel",
    }
    resp = http_get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=settings.http_timeout_seconds)
    if resp.status_code == 429:
        raise SearchError("GDELT rate limit reached (HTTP 429)")
    if resp.status_code != 200:
        raise SearchError(f"GDELT returned HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        # GDELT answers malformed queries with a plain-text message.
        raise SearchError(f"GDELT could not process the query: {resp.text[:120]}")
    articles = []
    for item in data.get("articles", []) or []:
        url = item.get("url", "")
        if not is_valid_http_url(url):
            continue
        articles.append(
            _make_article(
                title=item.get("title", ""),
                url=url,
                publisher=item.get("domain", ""),
                published_at=iso_or_none(item.get("seendate")),
                excerpt="",
                source_api="gdelt",
                query=query,
            )
        )
    return articles


def search_rss_feeds(keywords: list[str], lookback_days: int, settings: Settings) -> list[dict]:
    """Read configured publisher feeds and keep entries matching the keywords."""
    kw = [k.lower() for k in keywords if k]
    articles, errors = [], []
    for feed_url in settings.rss_feed_list:
        try:
            resp = http_get(feed_url, timeout=settings.http_timeout_seconds)
            if resp.status_code != 200:
                errors.append(f"{domain_of(feed_url)}: HTTP {resp.status_code}")
                continue
            feed = feedparser.parse(resp.content)
        except requests.RequestException as exc:
            errors.append(f"{domain_of(feed_url)}: {exc.__class__.__name__}")
            continue
        publisher = (feed.feed.get("title") if hasattr(feed, "feed") else "") or domain_of(feed_url)
        for entry in feed.entries[:50]:
            title = entry.get("title", "")
            excerpt = clean_html(entry.get("summary", ""))
            haystack = f"{title} {excerpt}".lower()
            if kw and not any(k in haystack for k in kw):
                continue
            link = entry.get("link", "")
            if not is_valid_http_url(link):
                continue
            articles.append(
                _make_article(
                    title=title,
                    url=link,
                    publisher=publisher,
                    published_at=iso_or_none(entry.get("published") or entry.get("updated")),
                    excerpt=excerpt,
                    source_api="rss",
                    query=" ".join(keywords),
                )
            )
    if errors and not articles and len(errors) == len(settings.rss_feed_list):
        raise SearchError("All RSS feeds failed: " + "; ".join(errors[:4]))
    return articles


def search_hackernews(query: str, lookback_days: int, settings: Settings) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(days=lookback_days)).timestamp())
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since},points>20",
        "hitsPerPage": str(min(settings.max_candidates_per_query, 30)),
    }
    resp = http_get("https://hn.algolia.com/api/v1/search", params=params, timeout=settings.http_timeout_seconds)
    if resp.status_code != 200:
        raise SearchError(f"Hacker News API returned HTTP {resp.status_code}")
    articles = []
    for hit in resp.json().get("hits", []):
        url = hit.get("url") or ""
        if not is_valid_http_url(url):
            continue
        articles.append(
            _make_article(
                title=hit.get("title", ""),
                url=url,
                publisher=domain_of(url),
                published_at=iso_or_none(hit.get("created_at")),
                excerpt="",
                source_api="hackernews",
                query=query,
            )
        )
    return articles


def search_tavily(
    query: str,
    lookback_days: int,
    settings: Settings,
    display_query: str | None = None,
) -> list[dict]:
    """Semantic news search. `query` may include the original user request.

    Articles are tagged with `display_query` (the short rewrite) so ranking can
    group hits by rewrite instead of by the expanded Tavily string.
    """
    if not settings.tavily_api_key:
        raise SearchError("TAVILY_API_KEY not set")
    depth = settings.tavily_search_depth if settings.tavily_search_depth in ("basic", "advanced") else "advanced"
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "topic": "news",
            "days": max(1, min(int(lookback_days), 365)),
            "max_results": max(1, min(int(settings.tavily_max_results), 10)),
            "search_depth": depth,
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=max(settings.http_timeout_seconds, 20),
    )
    if resp.status_code in (401, 403):
        raise SearchError("Tavily rejected the API key")
    if resp.status_code == 429 or resp.status_code == 432:
        raise SearchError("Tavily quota/rate limit reached")
    if resp.status_code != 200:
        raise SearchError(f"Tavily returned HTTP {resp.status_code}")
    out = []
    for item in resp.json().get("results", []):
        url = item.get("url", "")
        if not is_valid_http_url(url):
            continue
        article = _make_article(
            title=item.get("title", ""),
            url=url,
            publisher=domain_of(url),
            published_at=iso_or_none(item.get("published_date")),
            excerpt=item.get("content", ""),
            source_api="tavily",
            query=display_query or query,
        )
        score = item.get("score")
        if isinstance(score, (int, float)):
            article["retrieval_score"] = round(float(score), 4)
        out.append(article)
    return out


QUERY_SOURCES = {
    "google_news": search_google_news,
    "gdelt": search_gdelt,
    "hackernews": search_hackernews,
    "tavily": search_tavily,
}


# ---------------------------------------------------------------------------
# Public tool
# ---------------------------------------------------------------------------
def search_news(
    topic: str,
    queries: list[str] | None = None,
    keywords: list[str] | None = None,
    lookback_days: int | None = None,
    sources: list[str] | None = None,
    settings: Settings | None = None,
    query_context: str | None = None,
) -> dict:
    """Search all configured free sources.

    Returns {"articles": [...], "log": [{"source", "query", "count", "error", "cached"}]}
    """
    settings = settings or get_settings()
    lookback = lookback_days or settings.default_lookback_days
    query_limit = max(1, int(settings.max_rewritten_queries))
    queries = [q for q in (queries or [topic]) if q and q.strip()][:query_limit]
    context = collapse_ws(query_context or "")
    keywords = keywords or tokenize(topic)[:6]
    sources = sources or settings.search_sources
    cache = FileCache(f"{settings.data_dir}/cache", settings.research_cache_ttl_minutes * 60)

    articles: list[dict] = []
    log: list[dict] = []

    def run(source: str, query: str, fn, cache_query: str | None = None):
        key = f"{source}|{cache_query or query}|{lookback}|{settings.news_language}"
        cached = cache.get(key)
        if cached is not None:
            articles.extend(cached)
            log.append({"source": source, "query": query, "count": len(cached), "error": None, "cached": True})
            return
        try:
            found = fn()
            found = [a for a in found if a["title"] and a["url"] and _within_lookback(a["published_at"], lookback)]
            cache.set(key, found)
            articles.extend(found)
            log.append({"source": source, "query": query, "count": len(found), "error": None, "cached": False})
        except (SearchError, requests.RequestException, ValueError) as exc:
            logger.warning("search_news :: %s :: %s", source, exc)
            log.append({"source": source, "query": query, "count": 0, "error": str(exc)[:200], "cached": False})

    for source in sources:
        if source == "rss":
            run("rss", ",".join(keywords), lambda: search_rss_feeds(keywords, lookback, settings))
            continue
        fn = QUERY_SOURCES.get(source)
        if fn is None:
            continue
        if source == "tavily" and not settings.tavily_api_key:
            continue
        # GDELT is slow and rate limited, so it only sees the first two rewrites.
        # Tavily is semantic: it searches every rewrite, with the original request attached.
        if source == "gdelt":
            src_queries = queries[:2]
        elif source == "tavily":
            src_queries = queries[: max(1, settings.tavily_max_queries)]
        else:
            src_queries = queries
        for q in src_queries:
            if source == "tavily" and context:
                expanded = truncate(collapse_ws(f"{q}. User request: {context}"), 380)
                run(
                    source,
                    q,
                    lambda fn=fn, expanded=expanded, short=q: fn(expanded, lookback, settings, display_query=short),
                    cache_query=expanded,
                )
            else:
                run(source, q, lambda fn=fn, q=q: fn(q, lookback, settings))

    return {"articles": articles, "log": log}


# ---------------------------------------------------------------------------
# Article content (only for selected articles, only when permitted)
# ---------------------------------------------------------------------------
def _robots_allows(url: str, timeout: int) -> bool:
    domain = domain_of(url)
    if domain not in _robots_cache:
        parser = urllib.robotparser.RobotFileParser()
        scheme = url.split("://", 1)[0]
        try:
            resp = http_get(f"{scheme}://{url.split('://', 1)[1].split('/', 1)[0]}/robots.txt", timeout=timeout)
            if resp.status_code >= 400:
                parser = None  # no robots.txt -> allowed
            else:
                parser.parse(resp.text.splitlines())
        except requests.RequestException:
            parser = None
        _robots_cache[domain] = parser
    parser = _robots_cache[domain]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def decode_google_news_url(url: str, timeout: int = 5) -> str | None:
    """Decode a modern Google News RSS CBMi redirect URL to its canonical publisher URL."""
    match = re.search(r"articles/([^/?]+)", url)
    if not match:
        return None
    gn_art_id = match.group(1)
    if len(gn_art_id) < 30:
        return None

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(f"https://news.google.com/articles/{gn_art_id}", headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        div = soup.select_one("c-wiz > div")
        if not div:
            return None
        signature = div.get("data-n-a-sg")
        timestamp = div.get("data-n-a-ts")
        if not signature or not timestamp:
            return None

        rpc_request = [
            "Fbv4je",
            json.dumps([
                "garturlreq",
                [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                 "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                gn_art_id,
                timestamp,
                signature
            ])
        ]
        payload = f"f.req={quote_plus(json.dumps([[rpc_request]]))}"
        post_headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers=post_headers,
            data=payload,
            timeout=timeout
        )
        if response.status_code != 200:
            return None
        response_lines = response.text.split("\n\n")
        if len(response_lines) < 2:
            return None
        data = json.loads(response_lines[1])
        inner_array = json.loads(data[0][2])
        real_url = inner_array[1]
        return real_url if is_valid_http_url(real_url) else None
    except Exception as exc:
        logger.debug("decode_google_news_url failed for %s: %s", url, exc)
        return None


def fetch_article_content(article: dict, settings: Settings | None = None) -> dict:
    """Try to fetch readable article text. Never bypasses paywalls or logins.

    Returns a copy of the article with `content` and `content_status` updated:
    full | excerpt_only | title_only | blocked_by_robots | unavailable
    """
    settings = settings or get_settings()
    art = dict(article)
    url = art.get("url", "")

    # Decode Google News wrappers to the canonical publisher URL when possible
    if "news.google.com" in url:
        decoded_url = decode_google_news_url(url, timeout=settings.http_timeout_seconds)
        if decoded_url:
            url = decoded_url
            art["url"] = decoded_url
            art["domain"] = domain_of(decoded_url)
        else:
            art["content_status"] = "excerpt_only" if art.get("excerpt") else "title_only"
            return art

    if not settings.fetch_article_content or not is_valid_http_url(url):
        return art
    try:
        if not _robots_allows(url, settings.http_timeout_seconds):
            art["content_status"] = "blocked_by_robots"
            return art
        resp = http_get(url, timeout=settings.http_timeout_seconds, headers={"Accept": "text/html"})
    except requests.RequestException as exc:
        logger.info("fetch_article_content :: %s :: %s", url, exc)
        art["content_status"] = art.get("content_status") or "unavailable"
        return art
    if resp.status_code in (401, 402, 403):
        # Paywall / access control: respect it.
        art["content_status"] = "unavailable"
        return art
    if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "html"):
        return art
    text = extract_main_text(resp.text[:1_500_000])
    if len(text) >= 350:
        art["content"] = sanitize_untrusted(text, settings.max_article_chars)
        art["content_status"] = "full"
        if not art.get("excerpt"):
            art["excerpt"] = truncate(text, 400)
    elif art.get("excerpt"):
        art["content_status"] = "excerpt_only"
    else:
        art["content_status"] = "title_only"
    return art


def extract_main_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]):
        tag.decompose()
    candidates = [
        soup.find("article"),
        soup.find("main"),
        soup.find(attrs={"itemprop": "articleBody"}),
        soup.find(class_=re.compile(r"article[-_]?body|post[-_]?content|entry[-_]?content|story[-_]?content", re.I)),
        soup.body,
        soup,
    ]
    root = soup.body or soup
    for c in candidates:
        if c and len(c.find_all("p")) >= 3:
            root = c
            break
    paragraphs = [collapse_ws(p.get_text(" ")) for p in root.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 50]
    return "\n".join(paragraphs)
