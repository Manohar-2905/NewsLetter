"""End-to-end workflow tests with mocked research and a scripted model."""

import uuid
from pathlib import Path

import pytest

from app.agent.context import RunContext
from app.agent.graph import build_graph, resume_newsletter_agent, run_newsletter_agent
from app.services.llm_base import LLMQuotaError
from tests.conftest import FakeLLM


def run(llm, mode="autonomous", **opts):
    rid = uuid.uuid4().hex
    graph = build_graph()
    ctx = RunContext(rid, "gemini", llm=llm, build_models=False)
    result = run_newsletter_agent("Create a newsletter about agentic AI and autonomous coding agents",
                                  graph=graph, run_id=rid, context=ctx, mode=mode, **opts)
    return graph, result


@pytest.mark.parametrize("bad", ["", "  ", "a"])
def test_invalid_goal_rejected(bad):
    with pytest.raises(ValueError):
        run_newsletter_agent(bad)


def test_autonomous_run_completes(mock_research, fake_llm):
    _, result = run(fake_llm, article_count=5)
    assert result["status"] == "completed", result["review"]
    assert len(result["summaries"]) == 5
    assert result["newsletter"]["subject"]
    assert result["review"]["passed"]
    assert result["output"] and Path(result["output"]["directory"], result["output"]["primary_file"]).exists()
    # planning, rewritten-query answers, relevance check, batch summary, framing, review
    assert result["llm_calls"] == 6
    assert result["research_brief"]
    assert result["ranked_responses"]
    assert any(
        "Create a newsletter about agentic AI and autonomous coding agents" in (item.get("prompt") or "")
        for item in result["ranked_responses"]
    )


def test_markdown_output(mock_research, fake_llm):
    _, result = run(fake_llm, output_format="markdown", article_count=6)
    assert result["output"]["primary_format"] == "markdown"
    assert result["newsletter"]["content"].startswith("# ")
    assert len(result["summaries"]) == 6


def test_no_suitable_articles(monkeypatch, fake_llm):
    import app.agent.nodes.researcher as researcher_mod

    monkeypatch.setattr(researcher_mod, "search_news",
                        lambda *a, **k: {"articles": [], "log": [{"source": "gdelt", "query": "x", "count": 0,
                                                                  "error": "down", "cached": False}]})
    _, result = run(fake_llm)
    assert result["status"] == "no_results"
    assert result["newsletter"] is None
    assert result["output"] is None
    # agent autonomously broadened the search once before giving up
    assert len([e for e in result["research_log"]]) == 2


def test_critic_failure_respects_revision_limit(mock_research):
    llm = FakeLLM(review_issues=[{"article_index": 0, "type": "unsupported_claim",
                                  "message": "Summary 1 makes a claim not in the source", "fix": "Remove it"}])
    _, result = run(llm)
    assert result["revision_count"] == 2
    assert result["status"] == "completed_with_issues"
    assert len(result["review_history"]) == 3  # initial + 2 revisions
    assert any("still flagged" in d for d in result["newsletter"]["disclosures"])


def test_revision_fixes_problem(mock_research):
    state = {"n": 0}

    def review(prompt):
        state["n"] += 1
        if state["n"] == 1:
            return {"passed": False, "issues": [{"article_index": 2, "type": "factual_inconsistency",
                                                 "message": "Wrong detail", "fix": "Fix it"}]}
        return {"passed": True, "issues": []}

    llm = FakeLLM(overrides={"Review the newsletter below": review})
    _, result = run(llm)
    assert result["status"] == "completed"
    assert result["revision_count"] == 1


def test_human_in_the_loop_approve(mock_research, fake_llm):
    graph, result = run(fake_llm, mode="hitl")
    assert result["status"] == "awaiting_approval"
    assert result["output"] is None  # nothing saved before approval
    assert result["newsletter"]["subject"]
    final = resume_newsletter_agent(result["run_id"], "approve", graph=graph)
    assert final["status"] == "completed"
    assert final["approved"] is True
    assert final["output"]


def test_human_in_the_loop_revise_then_approve(mock_research, fake_llm):
    graph, result = run(fake_llm, mode="hitl")
    after = resume_newsletter_agent(result["run_id"], "revise", "Make the intro shorter please", graph=graph)
    assert after["status"] == "awaiting_approval"
    assert after["human_rounds"] == 1
    assert any("Make the intro shorter" in p for p in fake_llm.prompts if "Write the framing" in p)
    final = resume_newsletter_agent(result["run_id"], "approve", graph=graph)
    assert final["status"] == "completed"


def test_human_feedback_can_remove_article(mock_research):
    llm = FakeLLM(overrides={"human editor reviewed": {"remove_articles": [2], "rewrite_articles": [],
                                                       "newsletter_instructions": ""}})
    graph, result = run(llm, mode="hitl")
    after = resume_newsletter_agent(result["run_id"], "revise", "Remove article 2", graph=graph)
    assert len(after["summaries"]) == len(result["summaries"]) - 1


def test_hitl_persists_across_restart(mock_research, fake_llm, tmp_path):
    """A paused run can be resumed by a NEW graph using the same SQLite checkpoint."""
    from app.agent.context import drop_context, register_context
    from app.agent.graph import sqlite_checkpointer

    db = str(tmp_path / "cp.sqlite")
    rid = uuid.uuid4().hex
    graph1 = build_graph(sqlite_checkpointer(db))
    result = run_newsletter_agent("agentic AI coding agents news", graph=graph1, run_id=rid,
                                  context=RunContext(rid, "gemini", llm=fake_llm, build_models=False), mode="hitl")
    assert result["status"] == "awaiting_approval"
    drop_context(rid)  # simulate process restart: in-memory context lost
    register_context(RunContext(rid, "gemini", llm=fake_llm, build_models=False))
    graph2 = build_graph(sqlite_checkpointer(db))
    final = resume_newsletter_agent(rid, "approve", graph=graph2)
    assert final["status"] == "completed"


def test_quota_exhaustion_mid_run_is_transparent(mock_research):
    """Quota runs out at summarization: the agent continues with honest fallbacks and says so."""
    from app.services.llm_factory import ResilientLLM

    inner = FakeLLM(overrides={'"items"': LLMQuotaError("Gemini free-tier daily quota is exhausted.", "gemini")})
    llm = ResilientLLM(inner, sleep=lambda s: None)
    _, result = run(llm)
    assert result["status"] in ("completed", "completed_with_issues")
    assert any("quota" in w.lower() for w in result["warnings"])
    assert all(s["limited_info"] for s in result["summaries"])
    # after exhaustion no further model calls were attempted
    assert inner.calls == 4  # plan + rewritten answers + relevance + failed batch
