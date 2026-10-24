"""Query rewrite, reciprocal-rank fusion, and Tavily query translation."""

from datetime import datetime, timezone

from app.agent.query_rewrite import normalize_rewrites
from app.agent.ranking import (
    annotate_query_ranks,
    articles_from_ranked_responses,
    rank_articles,
    rank_responses,
)
from app.config import get_settings
from app.tools.generate_newsletter import generate_newsletter
from app.tools.review_newsletter import validate_html
from app.utils.dedupe import dedupe_articles
from tests.conftest import make_article

import importlib

sn = importlib.import_module("app.tools.search_news")
NOW = datetime.now(timezone.utc)


GOAL = "Create a weekly newsletter on quantum networking for telecom engineers"


def test_rewrites_keep_the_original_request_and_vary_the_search():
    rewrites = normalize_rewrites(GOAL, ["quantum networking"], ["quantum", "networking", "telecom"], "quantum networking")
    assert len(rewrites) >= 3
    queries = [item["query"].lower() for item in rewrites]
    assert len(set(queries)) == len(queries)
    assert rewrites[0]["angle"] == "paraphrase"
    for item in rewrites:
        assert GOAL in item["prompt"]
        assert item["query"] in item["prompt"]
        assert "Original user request:" in item["prompt"]


def test_rrf_ranks_a_story_found_by_two_queries_first():
    first = {**make_article(1, title="Quantum networking trial links two cities"), "query": "quantum networking"}
    second = {**make_article(2, title="Unrelated chip supply note"), "query": "quantum networking"}
    again = {**make_article(1, title="Quantum networking trial links two cities"), "query": "telecom quantum"}
    unique, removed = dedupe_articles(annotate_query_ranks([first, second, again]))
    assert removed == 1
    ranked = rank_articles(unique, ["quantum", "networking", "telecom"], 7)
    assert ranked[0]["url"] == first["url"]
    assert set(ranked[0]["queries"]) == {"quantum networking", "telecom quantum"}
    assert ranked[0]["rrf"] > ranked[1]["rrf"]


def test_weak_answers_do_not_keep_their_articles():
    strong = [make_article(i, title=f"Quantum networking update {i}") for i in range(1, 7)]
    weak = [make_article(i, title=f"Gardening calendar {i}") for i in range(7, 13)]
    articles = []
    for index, article in enumerate(strong + weak, start=1):
        item = dict(article)
        item["fusion_score"] = 0.9 if index <= 6 else 0.2
        item["query_ranks"] = {"quantum networking": index}
        articles.append(item)
    responses = rank_responses(
        [
            {
                "query": "quantum networking",
                "angle": "paraphrase",
                "prompt": f"Original user request:\n{GOAL}",
                "answer": "Carriers tested quantum networking between two cities.",
                "relevance": 9,
                "supporting_urls": [article["url"] for article in strong],
                "origin": "model",
            },
            {
                "query": "gardening calendar",
                "angle": "recent",
                "prompt": f"Original user request:\n{GOAL}",
                "answer": "This is about planting schedules and has nothing to do with networks.",
                "relevance": 1,
                "supporting_urls": [article["url"] for article in weak],
                "origin": "model",
            },
        ],
        articles,
        ["quantum", "networking", "telecom"],
    )
    kept, dropped = articles_from_ranked_responses(articles, responses, need=5)
    kept_urls = {article["url"] for article in kept}
    assert dropped > 0
    assert all(article["url"] in kept_urls for article in strong)
    assert not any(article["url"] in kept_urls for article in weak)


def test_tavily_search_attaches_the_original_request(monkeypatch):
    captured = {}

    class Resp:
        status_code = 200

        def json(self):
            return {
                "results": [
                    {
                        "url": "https://example.com/quantum",
                        "title": "Quantum networking trial",
                        "content": "A carrier tested quantum networking between two cities.",
                        "published_date": NOW.isoformat(),
                        "score": 0.91,
                    }
                ]
            }

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return Resp()

    monkeypatch.setattr(sn.requests, "post", fake_post)
    settings = get_settings().model_copy(update={"tavily_api_key": "test-tavily", "tavily_search_depth": "advanced"})
    out = sn.search_news(
        "quantum networking",
        queries=["quantum networking", "telecom quantum impact"],
        sources=["tavily"],
        query_context=GOAL,
        settings=settings,
    )
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["json"]["api_key"] == "test-tavily"
    assert "User request:" in captured["json"]["query"]
    assert GOAL in captured["json"]["query"]
    assert captured["json"]["search_depth"] == "advanced"
    assert captured["json"]["topic"] == "news"
    assert captured["timeout"] >= 20
    assert len(out["articles"]) == 2  # one hit per rewrite
    assert {article["query"] for article in out["articles"]} == {"quantum networking", "telecom quantum impact"}
    assert out["articles"][0]["retrieval_score"] == 0.91
    assert out["articles"][0]["source_api"] == "tavily"
    assert all(entry["error"] is None for entry in out["log"])


def test_ranked_brief_is_rendered_from_top_answers():
    summaries = [
        {
            "headline": "Quantum networking trial",
            "publisher": "Example",
            "published_at": NOW.isoformat(),
            "url": "https://example.com/quantum",
            "summary": "A carrier tested quantum networking between two cities.",
            "key_takeaway": "Why it matters: telecom teams can trial the link.",
            "based_on": "full_text",
            "limited_info": False,
        }
    ]
    responses = [
        {
            "query": "quantum networking",
            "answer": "A carrier tested quantum networking between two cities for telecom engineers.",
            "rank": 1,
        }
    ]
    newsletter, _warnings = generate_newsletter(
        summaries,
        {"topic": "quantum networking", "output_format": "html", "ranked_responses": responses},
        llm=None,
    )
    assert "Ranked research brief" in newsletter["html"]
    assert "Ranked research brief" in newsletter["markdown"]
    assert "quantum networking" in newsletter["research_brief"].lower()
    assert validate_html(newsletter["html"]) == []
