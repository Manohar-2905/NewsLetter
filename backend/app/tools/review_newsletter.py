"""Tool: review_newsletter — self-critique.

Two layers:
  1. Deterministic checks (always run, free): article count, duplicates,
     links, required sections, HTML/Markdown validity, numbers that do not
     appear in the source material, missing dates ...
  2. LLM semantic review (when a model is available): topic relevance,
     factual consistency with sources, summary quality.

Passing this review does NOT prove the newsletter is factually correct; it
only means no problem was detected by these checks.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from ..agent.prompts import REVIEWER_SYSTEM, source_block
from ..services.llm_base import BaseLLM, LLMError, LLMQuotaError
from ..utils.dedupe import titles_similar
from ..utils.text import is_valid_http_url, normalize_url, tokenize

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
_NUM_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s?(?:%|percent|million|billion|trillion|bn|m|k)?", re.I)
_SUPERLATIVE_RE = re.compile(r"\b(the latest|first[- ]ever|world'?s first|unprecedented|record[- ]breaking)\b", re.I)
SEMANTIC_ERROR_TYPES = {"unsupported_claim", "factual_inconsistency", "off_topic", "fabrication"}


class _TagChecker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.seen: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.seen.add(tag)
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        for name, value in attrs:
            if name == "href" and value and not (value.startswith("http://") or value.startswith("https://")):
                self.errors.append(f"Non-http link found: {value[:60]}")

    def handle_startendtag(self, tag, attrs):
        self.seen.add(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag in self.stack:
            while self.stack:
                top = self.stack.pop()
                if top == tag:
                    break
                self.errors.append(f"Unclosed <{top}> before </{tag}>")
        else:
            self.errors.append(f"Unexpected closing tag </{tag}>")


def validate_html(content: str) -> list[str]:
    checker = _TagChecker()
    try:
        checker.feed(content or "")
        checker.close()
    except Exception as exc:  # HTMLParser rarely raises, but be safe
        return [f"HTML could not be parsed: {exc}"]
    errors = list(checker.errors)
    errors += [f"Unclosed <{t}>" for t in checker.stack]
    for required in ("html", "head", "body", "title"):
        if required not in checker.seen:
            errors.append(f"Missing <{required}> element")
    return errors


def validate_markdown(content: str, sections: list[dict]) -> list[str]:
    errors = []
    if not re.search(r"^# \S", content or "", re.M):
        errors.append("Markdown is missing a top-level '# ' title")
    if content.count("```") % 2:
        errors.append("Unbalanced code fence in Markdown")
    for s in sections:
        if is_valid_http_url(s.get("url", "")) and f"]({s['url']})" not in content:
            errors.append(f"Markdown link missing for '{s.get('headline', '')[:50]}'")
    return errors


def _numbers(text: str) -> set[str]:
    found = set()
    for m in _NUM_RE.finditer(text or ""):
        token = re.sub(r"[\s,]", "", m.group(0)).lower().replace("percent", "%")
        digits = re.sub(r"[^\d.]", "", token).rstrip(".")
        if len(digits) >= 2 or "%" in token or "$" in token:
            found.add(digits)
    return found


def _issue(severity, code, message, fix="", article_index=None) -> dict:
    return {"severity": severity, "code": code, "message": message, "fix": fix, "article_index": article_index}


def deterministic_checks(newsletter: dict, sources: list[dict], config: dict) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    checks: dict[str, bool] = {}
    sections = newsletter.get("sections", [])
    requested = int(config.get("article_count") or 5)
    max_articles = int(config.get("max_articles") or 7)

    # Article count
    if not sections:
        issues.append(_issue("error", "no_articles", "Newsletter has no articles."))
    elif len(sections) > max_articles:
        issues.append(_issue("error", "too_many_articles", f"{len(sections)} articles exceeds the limit of {max_articles}.",
                             "Remove the weakest articles."))
    elif len(sections) < requested:
        issues.append(_issue("warning", "fewer_articles",
                             f"Only {len(sections)} suitable articles found (requested {requested}).",
                             "Disclosed in the newsletter; not enough reliable sources were available."))
    checks["article_count"] = bool(sections) and len(sections) <= max_articles

    # Duplicates
    dup = False
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            a, b = sections[i], sections[j]
            if normalize_url(a["url"]) == normalize_url(b["url"]) or titles_similar(a["headline"], b["headline"]):
                dup = True
                issues.append(_issue("error", "duplicate_story", f"Articles {i + 1} and {j + 1} cover the same story.",
                                     "Remove one of the duplicates.", article_index=j))
    checks["no_duplicates"] = not dup

    # Links, summaries, dates
    links_ok, summaries_ok = True, True
    for i, s in enumerate(sections):
        if not is_valid_http_url(s.get("url", "")):
            links_ok = False
            issues.append(_issue("error", "missing_link", f"Article {i + 1} has no valid source link.",
                                 "Drop the article or restore its original URL.", i))
        if len((s.get("summary") or "").strip()) < 20:
            summaries_ok = False
            issues.append(_issue("error", "empty_summary", f"Article {i + 1} summary is empty or too short.",
                                 "Re-summarize from the source.", i))
        if not s.get("published_at"):
            issues.append(_issue("warning", "missing_date", f"Article {i + 1} has no publication date.",
                                 "Shown as 'Date not available'."))
    checks["source_links"] = links_ok
    checks["summaries_present"] = summaries_ok

    # Unsupported numbers: every figure in a summary must exist in its source.
    unsupported = False
    for i, s in enumerate(sections):
        src = sources[i] if i < len(sources) else {}
        haystack = " ".join(str(src.get(k) or "") for k in ("title", "excerpt", "content", "published_at"))
        source_numbers = _numbers(haystack)
        for num in _numbers(f"{s.get('summary', '')} {s.get('key_takeaway', '')}"):
            if num not in source_numbers and num not in haystack.replace(",", ""):
                unsupported = True
                issues.append(_issue("error", "unsupported_number",
                                     f"Article {i + 1} mentions '{num}', which does not appear in the source.",
                                     "Remove or correct the figure using only source facts.", i))
    framing_text = " ".join([newsletter.get("intro", ""), newsletter.get("conclusion", ""),
                             " ".join(newsletter.get("key_takeaways", []))])
    summary_text = " ".join(f"{s.get('headline', '')} {s.get('summary', '')} {s.get('key_takeaway', '')}" for s in sections)
    allowed = _numbers(summary_text) | _numbers(newsletter.get("date", ""))
    for num in _numbers(framing_text) - allowed:
        unsupported = True
        issues.append(_issue("error", "unsupported_number",
                             f"Intro/takeaways/conclusion mention '{num}', which is not in any article summary.",
                             "Remove figures that are not supported by the summaries."))
    if _SUPERLATIVE_RE.search(framing_text) and not _SUPERLATIVE_RE.search(summary_text):
        issues.append(_issue("warning", "unsupported_superlative",
                             "Framing uses superlatives ('the latest', 'first-ever'...) not found in the summaries.",
                             "Use neutral wording."))
    checks["numbers_supported"] = not unsupported

    # Completeness
    missing = [k for k in ("subject", "title", "intro", "conclusion", "footer") if not (newsletter.get(k) or "").strip()]
    if not newsletter.get("key_takeaways"):
        missing.append("key_takeaways")
    for k in missing:
        issues.append(_issue("error", "missing_section", f"Newsletter is missing its {k}.", f"Write the {k}."))
    if len(newsletter.get("subject", "")) > 120:
        issues.append(_issue("warning", "long_subject", "Subject line is longer than 120 characters.", "Shorten it."))
    checks["complete"] = not missing

    # Format validity
    html_errors = validate_html(newsletter.get("html", ""))
    md_errors = validate_markdown(newsletter.get("markdown", ""), sections)
    for e in html_errors[:5]:
        issues.append(_issue("error", "invalid_html", e, "Re-render the HTML."))
    for e in md_errors[:5]:
        issues.append(_issue("error", "invalid_markdown", e, "Re-render the Markdown."))
    checks["valid_html"] = not html_errors
    checks["valid_markdown"] = not md_errors

    # Every source link must be present in the rendered output
    content = newsletter.get("content", "")
    for i, s in enumerate(sections):
        if is_valid_http_url(s["url"]) and s["url"] not in content and s["url"].replace("&", "&amp;") not in content:
            issues.append(_issue("error", "link_not_rendered", f"Article {i + 1} link missing from output.",
                                 "Re-render.", i))

    # Light topical relevance check
    keywords = [k.lower() for k in (config.get("keywords") or [])]
    if keywords:
        for i, s in enumerate(sections):
            text = f"{s.get('headline', '')} {s.get('summary', '')}".lower()
            if not any(k in text for k in keywords) and not set(tokenize(text)) & set(keywords):
                issues.append(_issue("warning", "weak_relevance",
                                     f"Article {i + 1} does not mention any topic keyword.",
                                     "Confirm it is relevant or replace it.", i))
    return issues, checks


def semantic_review(newsletter: dict, sources: list[dict], topic: str, llm: BaseLLM) -> dict:
    sections_text = "\n\n".join(
        f"[article {i}] headline: {s['headline']}\nsummary: {s['summary']}\ntakeaway: {s.get('key_takeaway', '')}"
        for i, s in enumerate(newsletter.get("sections", []))
    )
    prompt = (
        f"Topic requested by the user: {topic}\n\n"
        "Review the newsletter below against its sources. Check: topic relevance of each article, factual "
        "consistency of each summary with its source, unsupported claims, summary quality, and whether the "
        "intro/takeaways/conclusion add claims not supported by the articles.\n"
        "Only report real problems. Article indices are 0-based and match <source id>.\n"
        'Return JSON: {"passed": true|false, "relevance_score": 1-10, "summary_quality": 1-10, '
        '"issues": [{"article_index": <int or null>, "type": "unsupported_claim|factual_inconsistency|off_topic|'
        'quality|style", "message": "...", "fix": "..."}]}\n\n'
        f"NEWSLETTER\nsubject: {newsletter.get('subject')}\nintro: {newsletter.get('intro')}\n"
        f"key_takeaways: {newsletter.get('key_takeaways')}\nconclusion: {newsletter.get('conclusion')}\n\n"
        f"{sections_text}\n\nSOURCES\n"
        + "\n\n".join(source_block(i, a, max_chars=1500) for i, a in enumerate(sources))
    )
    return llm.generate_json(prompt, system=REVIEWER_SYSTEM, max_tokens=1500)


def review_newsletter(
    newsletter: dict,
    articles: list[dict],
    config: dict | None = None,
    llm: BaseLLM | None = None,
) -> dict:
    """Review the newsletter. `articles` are the raw source articles, in section order."""
    config = config or {}
    issues, checks = deterministic_checks(newsletter, articles, config)
    semantic = {"status": "skipped", "reason": "No model available for semantic review."}
    scores = {}
    if llm is not None and newsletter.get("sections"):
        try:
            raw = semantic_review(newsletter, articles, config.get("topic", ""), llm)
            if not isinstance(raw, dict):
                raise ValueError("unexpected review format")
            scores = {
                "relevance_score": raw.get("relevance_score"),
                "summary_quality": raw.get("summary_quality"),
            }
            for item in raw.get("issues") or []:
                if not isinstance(item, dict) or not item.get("message"):
                    continue
                kind = str(item.get("type", "quality")).lower()
                idx = item.get("article_index")
                idx = idx if isinstance(idx, int) and 0 <= idx < len(newsletter["sections"]) else None
                issues.append(_issue(
                    "error" if kind in SEMANTIC_ERROR_TYPES else "warning",
                    kind, str(item["message"])[:400], str(item.get("fix", ""))[:300], idx,
                ))
            semantic = {"status": "completed", "model": llm.label, "model_passed": bool(raw.get("passed"))}
        except LLMQuotaError as exc:
            semantic = {"status": "skipped", "reason": str(exc)}
        except (LLMError, ValueError) as exc:
            semantic = {"status": "failed", "reason": f"Semantic review failed: {exc}"}

    errors = [i for i in issues if i["severity"] == "error"]
    passed = not errors
    if semantic.get("status") == "completed" and semantic.get("model_passed") is False and not errors:
        # Model said fail but gave no concrete error-level issue -> treat as warning only.
        issues.append(_issue("warning", "reviewer_doubt", "The AI reviewer was not fully satisfied but gave no specific error."))
    recommendations = [i["fix"] for i in issues if i.get("fix")][:10]
    return {
        "passed": passed,
        "status": "pass" if passed else "fail",
        "issues": issues,
        "error_count": len(errors),
        "warning_count": len(issues) - len(errors),
        "checks": checks,
        "scores": scores,
        "semantic_review": semantic,
        "recommendations": recommendations,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Automated review reduces but does not eliminate errors. Verify important facts in the sources.",
    }
