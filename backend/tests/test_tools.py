"""Selection, summarization, newsletter generation, review and saving."""

from pathlib import Path

import pytest

from app.agent.nodes.selector import pick_diverse, relevant_candidates, score_articles
from app.services.llm_base import LLMProviderError, LLMQuotaError
from app.tools.generate_newsletter import generate_newsletter, render
from app.tools.review_newsletter import review_newsletter, validate_html
from app.tools.save_newsletter import save_newsletter
from app.tools.summarize_article import summarize_articles
from tests.conftest import FakeLLM, make_article


# --- selection -------------------------------------------------------------
def test_selection_count_and_diversity():
    arts = [make_article(i, publisher="Same Pub" if i <= 4 else None) for i in range(1, 10)]
    scored = score_articles(arts, ["agentic", "autonomous", "coding agents"], 7)
    picked, reserve = pick_diverse(scored, 5)
    assert len(picked) == 5
    assert sum(1 for a in picked if a["publisher"] == "Same Pub") <= 2
    assert reserve  # leftovers kept for replacements


def test_irrelevant_articles_filtered():
    arts = [make_article(1, title="Best pizza recipes", excerpt="cheese", content="tomato sauce")]
    assert relevant_candidates(arts, ["agentic", "coding agents"]) == []


def test_multi_source_corroboration_and_accessibility_ranking():
    # 1. PR wire penalty: identical relevance and recency, reputable wins on quality
    pr_wire = make_article(1, title="Agentic AI milestone reached", publisher="PR Newswire", domain="prnewswire.com")
    reputable = make_article(2, title="Agentic AI milestone reached", publisher="Reuters", domain="reuters.com")
    scored = score_articles([pr_wire, reputable], ["agentic"], 7)
    assert scored[0]["url"] == reputable["url"]
    assert scored[0]["scores"]["quality"] > scored[1]["scores"]["quality"]

    # 2. Content accessibility: full content ranks higher than headline-only redirect wrapper
    full_art = make_article(3, title="Security alert for enterprise systems", content="A" * 500, content_status="full",
                            url="https://sec.example.com/story")
    stub_art = make_article(4, title="Security alert for enterprise systems", content="", content_status="title_only",
                            url="https://news.google.com/rss/articles/123", excerpt="")
    scored_access = score_articles([stub_art, full_art], ["security"], 7)
    assert scored_access[0]["url"] == full_art["url"]
    assert scored_access[0]["scores"]["accessibility"] > scored_access[1]["scores"]["accessibility"]

    # 3. Cross-source corroboration: articles covered across distinct publishers get corroboration boost
    story_a1 = make_article(5, title="Critical PHP vulnerability exploited in wild", publisher="WIRED", source_api="gdelt")
    story_a2 = make_article(6, title="Critical PHP vulnerability exploited in wild", publisher="Reuters", source_api="rss")
    story_isolated = make_article(7, title="Local bakery adopts solar panels in small town", publisher="Local Gazette", source_api="rss")
    scored_corrob = score_articles([story_a1, story_a2, story_isolated], ["php", "vulnerability"], 7)
    assert scored_corrob[0]["scores"]["corroboration"] > 0
    assert scored_corrob[1]["scores"]["corroboration"] > 0
    # Isolated story has zero cross-publisher corroboration
    isolated_scored = [s for s in scored_corrob if s["url"] == story_isolated["url"]][0]
    assert isolated_scored["scores"]["corroboration"] == 0.0


# --- summarization -----------------------------------------------------------
def test_batch_summarization_one_call():
    llm = FakeLLM()
    arts = [make_article(i) for i in range(1, 6)]
    summaries, warnings = summarize_articles(arts, llm, "agentic AI")
    assert len(summaries) == 5 and not warnings
    assert llm.calls == 1  # cost control: one request for all articles
    assert all(s["url"] == a["url"] for s, a in zip(summaries, arts))
    assert all(s["headline"] == a["title"] for s, a in zip(summaries, arts))  # headline never rewritten


def test_summarization_failure_falls_back_per_article():
    llm = FakeLLM(overrides={'"items"': LLMProviderError("boom")})
    arts = [make_article(i) for i in range(1, 4)]
    summaries, warnings = summarize_articles(arts, llm, "agentic AI")
    assert len(summaries) == 3
    assert any("one by one" in w for w in warnings)
    assert llm.calls == 4  # 1 failed batch + 3 single


def test_summarization_total_failure_uses_honest_fallback():
    llm = FakeLLM(overrides={'"items"': LLMProviderError("boom"), 'Return JSON: {"summary"': LLMProviderError("boom")})
    arts = [make_article(1)]
    summaries, warnings = summarize_articles(arts, llm, "agentic AI")
    assert summaries[0]["limited_info"] is True
    assert "excerpt" in summaries[0]["note"].lower()


def test_summarization_quota_propagates():
    llm = FakeLLM(overrides={'"items"': LLMQuotaError("quota", "gemini")})
    with pytest.raises(LLMQuotaError):
        summarize_articles([make_article(1)], llm, "agentic AI")


# --- newsletter generation & review ------------------------------------------
def _summaries(n=5):
    arts = [make_article(i) for i in range(1, n + 1)]
    summaries, _ = summarize_articles(arts, FakeLLM(), "agentic AI")
    return arts, summaries


@pytest.mark.parametrize("fmt", ["html", "markdown"])
def test_generate_newsletter_formats(fmt):
    arts, summaries = _summaries()
    nl, warnings = generate_newsletter(summaries, {"topic": "agentic AI", "output_format": fmt}, llm=FakeLLM())
    assert nl["subject"] and nl["title"] and nl["intro"] and nl["conclusion"]
    assert nl["content"] == (nl["html"] if fmt == "html" else nl["markdown"])
    for a in arts:
        assert a["url"] in nl["html"] and a["url"] in nl["markdown"]
    assert validate_html(nl["html"]) == []
    review = review_newsletter(nl, arts, {"topic": "agentic AI", "article_count": 5, "keywords": ["agentic"]}, llm=FakeLLM())
    assert review["passed"], review["issues"]
    assert review["checks"]["valid_html"] and review["checks"]["valid_markdown"]


def test_generate_without_llm_uses_template():
    _, summaries = _summaries(3)
    nl, _ = generate_newsletter(summaries, {"topic": "cybersecurity"}, llm=None)
    assert "Cybersecurity" in nl["title"]


def test_html_validation_detects_errors():
    errors = validate_html("<html><head><title>x</title></head><body><div><p>unclosed</div></body></html>")
    assert errors
    assert any("Missing <title>" in e for e in validate_html("<html><body></body></html>"))


def test_review_flags_unsupported_numbers_duplicates_and_links():
    arts, summaries = _summaries(3)
    summaries[0] = dict(summaries[0], summary="The company raised $500 million and grew 45% according to the report.")
    summaries[2] = dict(summaries[1])  # duplicate story
    summaries[1] = dict(summaries[1], url="")
    nl, _ = generate_newsletter(summaries, {"topic": "agentic AI"}, llm=None)
    review = review_newsletter(nl, arts, {"topic": "agentic AI", "article_count": 3})
    codes = {i["code"] for i in review["issues"]}
    assert not review["passed"]
    assert {"unsupported_number", "duplicate_story", "missing_link"} <= codes
    assert review["semantic_review"]["status"] == "skipped"


def test_review_semantic_issues_become_errors():
    arts, summaries = _summaries(5)
    nl, _ = generate_newsletter(summaries, {"topic": "agentic AI"}, llm=None)
    llm = FakeLLM(review_issues=[{"article_index": 1, "type": "unsupported_claim", "message": "Claim not in source", "fix": "Remove"}])
    review = review_newsletter(nl, arts, {"topic": "agentic AI", "article_count": 5}, llm=llm)
    assert not review["passed"]
    assert review["issues"][-1]["article_index"] == 1


def test_save_newsletter_writes_files(tmp_path):
    _, summaries = _summaries(2)
    nl, _ = generate_newsletter(summaries, {"topic": "agentic AI", "output_format": "markdown"}, llm=None)
    out = save_newsletter(nl, "markdown", "abc123", {"passed": True}, output_dir=str(tmp_path))
    assert out["primary_format"] == "markdown"
    for name in out["files"].values():
        assert (tmp_path / name).exists()
    assert Path(tmp_path / out["files"]["markdown"]).read_text(encoding="utf-8").startswith("# ")


def test_render_escapes_untrusted_html():
    _, summaries = _summaries(1)
    summaries[0] = dict(summaries[0], headline="<script>alert(1)</script>")
    nl, _ = generate_newsletter(summaries, {"topic": "x"}, llm=None)
    nl = render(nl)
    assert "<script>alert(1)</script>" not in nl["html"]
