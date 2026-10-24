"""Small, deterministic text helpers (no LLM needed)."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

_WS_RE = re.compile(r"\s+")
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "cmpid", "ocid"}

# Phrases often used in prompt-injection attempts inside scraped pages.
_INJECTION_RE = re.compile(
    r"(ignore (all |any )?(previous|prior|above) instructions|disregard (the )?(system|previous) prompt|"
    r"you are now|act as an? |system prompt:|<\s*/?\s*(system|assistant|instructions?)\s*>)",
    re.IGNORECASE,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "about", "be", "by", "create", "for", "from", "how", "in",
    "into", "is", "it", "latest", "make", "me", "new", "news", "newsletter", "of", "on", "or",
    "our", "recent", "send", "the", "this", "to", "top", "update", "updates", "weekly", "daily",
    "what", "with", "write", "developments", "subscribers", "week", "today", "monthly", "please",
    "generate", "build", "give", "summary", "summarize", "around", "trends", "happening",
}


def collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def clean_html(raw: str) -> str:
    """Convert an HTML fragment to plain text."""
    if not raw:
        return ""
    if "<" not in raw:
        return collapse_ws(html.unescape(raw))
    soup = BeautifulSoup(raw, "html.parser")
    return collapse_ws(soup.get_text(" "))


def truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit * 0.6 else cut).rstrip() + "…"


def sanitize_untrusted(text: str, limit: int = 4000) -> str:
    """Prepare scraped text for a prompt: trim it and neutralise injection phrases."""
    text = collapse_ws(text)
    text = _INJECTION_RE.sub("[removed]", text)
    return truncate(text, limit)


def normalize_url(url: str) -> str:
    """Canonical form used for de-duplication (drops tracking params, fragments...)."""
    if not url:
        return ""
    try:
        parts = urlparse(url.strip())
    except ValueError:
        return url.strip()
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/") or "/"
    return urlunparse((parts.scheme.lower() or "https", netloc, path, "", urlencode(query), ""))


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def is_valid_http_url(url: str) -> bool:
    try:
        parts = urlparse(url or "")
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc) and "." in parts.netloc


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].strip("-")) or "newsletter"


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9\-\+\.#]*", (text or "").lower()) if t not in STOPWORDS]


def keywords_from_goal(goal: str, limit: int = 8) -> list[str]:
    """Deterministic keyword extraction used when no LLM plan is available."""
    seen: list[str] = []
    for tok in tokenize(goal):
        tok = tok.strip(".-")
        if len(tok) > 2 and tok not in seen:
            seen.append(tok)
    return seen[:limit]


def parse_date(value) -> datetime | None:
    """Parse RFC-822, ISO-8601 or GDELT style (20261022T101500Z) dates to aware UTC."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        value = str(value).strip()
        dt = None
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                pass
        if dt is None:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                dt = None
        if dt is None:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_or_none(value) -> str | None:
    dt = parse_date(value)
    return dt.isoformat() if dt else None


def human_date(value) -> str:
    dt = parse_date(value)
    return dt.strftime("%b %d, %Y") if dt else "Date not available"
