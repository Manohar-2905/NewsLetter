"""Shared fixtures. Every external call (LLMs, RSS, APIs) is mocked."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.services.llm_base import BaseLLM


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "")
    monkeypatch.setenv("CRITIC_PROVIDER", "")
    monkeypatch.setenv("RESEARCH_CACHE_TTL_MINUTES", "0")
    monkeypatch.setenv("SEARCH_PROVIDER", "google_news,gdelt,rss,hackernews")
    get_settings.cache_clear()
    import importlib

    sn = importlib.import_module("app.tools.search_news")

    monkeypatch.setattr(sn, "GDELT_MIN_INTERVAL", 0)
    sn._robots_cache.clear()
    yield
    get_settings.cache_clear()


def iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


DISTINCT_TITLES = [
    "Startup unveils agentic coding assistant for enterprise teams",
    "Open source project adds autonomous agents to code review",
    "Cloud vendor previews agentic AI platform for developers",
    "Researchers test how coding agents handle legacy software",
    "Security experts warn about prompt injection in autonomous agents",
    "Agentic AI moves from demos to production at large banks",
    "Universities launch courses on building autonomous coding agents",
    "Chipmaker optimises hardware for agentic AI workloads",
    "Regulators examine accountability for autonomous agents",
    "Game studio uses coding agents to speed up prototyping",
]


def make_article(i: int, title: str | None = None, publisher: str | None = None, days: float = 1.0, **extra) -> dict:
    title = title or DISTINCT_TITLES[(i - 1) % len(DISTINCT_TITLES)]
    art = {
        "title": title,
        "url": f"https://news{i}.example.com/story-{i}",
        "publisher": publisher or f"Publisher {i}",
        "domain": f"news{i}.example.com",
        "published_at": iso_days_ago(days),
        "excerpt": f"{title}. The company described agentic AI tools for developers.",
        "content": (
            f"{title}. The company said the agentic AI system can plan and execute coding tasks autonomously. "
            "Developers can review each step before changes are merged. The release is available in preview."
        ),
        "content_status": "full",
        "source_api": "gdelt",
        "query": "agentic ai",
    }
    art.update(extra)
    return art


class FakeLLM(BaseLLM):
    """Scripted model. Override behaviour per test with `overrides`."""

    name = "fake"

    def __init__(self, overrides: dict | None = None, review_issues: list | None = None):
        super().__init__("fake-model")
        self.overrides = overrides or {}
        self.review_issues = review_issues
        self.prompts: list[str] = []

    def _response(self, prompt: str):
        for marker, value in self.overrides.items():
            if marker in prompt:
                return value(prompt) if callable(value) else value
        if "Create a research plan" in prompt:
            return {
                "topic": "Agentic AI coding agents",
                "search_queries": ["agentic AI", "autonomous coding agents"],
                "keywords": ["agentic", "coding agents", "autonomous"],
                "lookback_days": 7,
                "audience": "developers",
                "angle": "What changed this week",
                "quality_criteria": ["on topic", "recent"],
            }
        if "Rate how relevant" in prompt:
            ids = re.findall(r"^(\d+)\. ", prompt, re.M)
            return {"ratings": [{"id": int(i), "relevance": 8} for i in ids]}
        if '"items"' in prompt:
            ids = re.findall(r'<source id="(\d+)">', prompt)
            return {"items": [{"id": int(i), "summary": "The source reports a new agentic AI tool that plans and executes coding tasks.",
                               "key_takeaway": "Why it matters: developers get more autonomous help."} for i in ids]}
        if 'Return JSON: {"summary"' in prompt:
            return {"summary": "The source describes an agentic AI system for coding tasks.",
                    "key_takeaway": "Why it matters: it shows how agents are maturing."}
        if "Write the framing" in prompt:
            return {"subject": "Agentic AI coding agents: this week's briefing", "title": "Agentic AI Weekly",
                    "intro": "Agentic AI tools for developers kept moving this week.",
                    "key_takeaways": ["Agents are taking on more coding work", "Human review remains central"],
                    "conclusion": "Thanks for reading."}
        if "Review the newsletter below" in prompt:
            issues = self.review_issues or []
            return {"passed": not issues, "relevance_score": 9, "summary_quality": 8, "issues": issues}
        if "human editor reviewed" in prompt:
            return {"remove_articles": [], "rewrite_articles": [], "newsletter_instructions": "Make the intro shorter."}
        return {}

    def generate(self, prompt, system="", json_mode=False, max_tokens=2048):
        self._count()
        self.prompts.append(prompt)
        value = self._response(prompt)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value)


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def articles():
    return [make_article(i, days=i * 0.5) for i in range(1, 9)]


@pytest.fixture
def mock_research(monkeypatch, articles):
    """Replace network research with fixture articles."""
    import app.agent.nodes.critic as critic_mod
    import app.agent.nodes.researcher as researcher_mod
    import app.agent.nodes.selector as selector_mod

    calls = {"search": 0}

    def fake_search(topic, queries=None, keywords=None, lookback_days=None, sources=None, settings=None, query_context=None):
        calls["search"] += 1
        return {"articles": [dict(a) for a in articles],
                "log": [{"source": "gdelt", "query": q, "count": len(articles), "error": None, "cached": False}
                        for q in (queries or [topic])]}

    monkeypatch.setattr(researcher_mod, "search_news", fake_search)
    monkeypatch.setattr(selector_mod, "fetch_article_content", lambda a, s=None: dict(a))
    monkeypatch.setattr(critic_mod, "fetch_article_content", lambda a, s=None: dict(a))
    return calls
