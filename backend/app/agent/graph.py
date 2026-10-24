"""The LangGraph workflow and the main entry point `run_newsletter_agent(goal)`.

    plan -> research -(too few results?)-> broaden -> research
                     \\-> fuse (rank rewrites, answers, and articles) -> select -(no articles)-> END
                                \\-> summarize -> write -> review
    review -(failed & revisions left)-> revise -> write
           -(hitl & not approved)-> human_review -(approve)-> save -> END
                                                \\-(feedback)-> write
           -(otherwise)-> save -> END
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ..config import get_settings
from .context import RunContext, drop_context, register_context
from .nodes import (
    broaden_node,
    critic_node,
    fuse_node,
    human_review_node,
    plan_node,
    research_node,
    revise_node,
    route_after_human,
    route_after_research,
    route_after_review,
    save_node,
    select_node,
    summarize_node,
    write_node,
)
from .state import AgentState

DEFAULTS = {
    "provider": None,
    "output_format": "html",
    "article_count": 5,
    "tone": "professional",
    "mode": "autonomous",
    "lookback_days": None,
}


def _route_after_select(state: dict) -> str:
    return "end" if not state.get("selected") else "summarize"


def build_graph(checkpointer=None):
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("research", research_node)
    graph.add_node("broaden", broaden_node)
    graph.add_node("fuse", fuse_node)
    graph.add_node("select", select_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("write", write_node)
    graph.add_node("review", critic_node)
    graph.add_node("revise", revise_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("save", save_node)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_conditional_edges("research", route_after_research, {"broaden": "broaden", "fuse": "fuse"})
    graph.add_edge("broaden", "research")
    graph.add_edge("fuse", "select")
    graph.add_conditional_edges("select", _route_after_select, {"end": END, "summarize": "summarize"})
    graph.add_edge("summarize", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges(
        "review", route_after_review, {"revise": "revise", "human_review": "human_review", "save": "save"}
    )
    graph.add_edge("revise", "write")
    graph.add_conditional_edges("human_review", route_after_human, {"save": "save", "write": "write"})
    graph.add_edge("save", END)
    return graph.compile(checkpointer=checkpointer or MemorySaver())


def sqlite_checkpointer(path: str | None = None):
    """Persistent checkpointer so paused (HITL) runs survive restarts."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = path or str(Path(get_settings().data_dir) / "checkpoints.sqlite")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(conn)


def initial_state(run_id: str, goal: str, config: dict) -> dict:
    return {
        "run_id": run_id,
        "goal": goal,
        "config": config,
        "status": "running",
        "warnings": [],
        "revision_count": 0,
        "human_rounds": 0,
        "approved": False,
        "review_history": [],
    }


def normalize_config(options: dict | None) -> dict:
    settings = get_settings()
    cfg = {**DEFAULTS, **{k: v for k, v in (options or {}).items() if v is not None}}
    cfg["provider"] = (cfg.get("provider") or settings.llm_provider).lower()
    cfg["output_format"] = "markdown" if str(cfg["output_format"]).lower() in ("markdown", "md") else "html"
    cfg["mode"] = "hitl" if str(cfg["mode"]).lower() in ("hitl", "human", "human-in-the-loop") else "autonomous"
    cfg["article_count"] = max(1, min(settings.max_articles, int(cfg["article_count"])))
    return cfg


def summarize_result(graph, run_id: str) -> dict[str, Any]:
    """Turn the graph's current state into a result dictionary."""
    snapshot = graph.get_state({"configurable": {"thread_id": run_id}})
    values = dict(snapshot.values or {})
    waiting = "human_review" in (snapshot.next or ())
    status = "awaiting_approval" if waiting else values.get("status", "running")
    if status == "running" and not snapshot.next:
        status = "failed"
    newsletter = values.get("newsletter") or {}
    return {
        "run_id": run_id,
        "status": status,
        "message": values.get("message")
        or ("Draft ready for your review. Approve it or request changes." if waiting else ""),
        "goal": values.get("goal"),
        "config": values.get("config"),
        "plan": values.get("plan"),
        "research_log": values.get("research_log") or [],
        "ranked_responses": values.get("ranked_responses") or [],
        "research_brief": values.get("research_brief") or "",
        "candidates_count": len(values.get("candidates") or []),
        "articles": [
            {k: a.get(k) for k in ("title", "url", "publisher", "published_at", "content_status", "source_api", "scores", "excerpt")}
            for a in values.get("selected") or []
        ],
        "summaries": values.get("summaries") or [],
        "newsletter": {
            k: newsletter.get(k)
            for k in ("subject", "title", "date", "format", "html", "markdown", "content", "disclosures", "key_takeaways", "research_brief")
        } if newsletter else None,
        "review": values.get("review"),
        "review_history": values.get("review_history") or [],
        "revision_count": values.get("revision_count", 0),
        "human_rounds": values.get("human_rounds", 0),
        "approved": values.get("approved", False),
        "output": values.get("output"),
        "warnings": values.get("warnings") or [],
    }


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------
_default_graph = None


def _get_default_graph():
    global _default_graph
    if _default_graph is None:
        _default_graph = build_graph(MemorySaver())
    return _default_graph


def run_newsletter_agent(goal: str, graph=None, run_id: str | None = None, context: RunContext | None = None,
                         **options) -> dict:
    """Run the whole agent with ONE call.

    Example:
        result = run_newsletter_agent(
            "Create a weekly newsletter on the latest AI agent news",
            mode="autonomous", output_format="html", article_count=5,
        )

    Options: provider, output_format (html|markdown), article_count, tone,
    mode (autonomous|hitl), lookback_days.

    In "hitl" mode the run pauses with status "awaiting_approval"; continue it
    with resume_newsletter_agent(run_id, "approve") or
    resume_newsletter_agent(run_id, "revise", "your feedback").
    """
    goal = (goal or "").strip()
    if len(goal) < 3:
        raise ValueError("Please describe a newsletter topic or goal (at least 3 characters).")
    graph = graph or _get_default_graph()
    run_id = run_id or uuid.uuid4().hex
    cfg = normalize_config(options)
    ctx = context or RunContext(run_id, cfg["provider"])
    register_context(ctx)
    if ctx.llm is None and ctx.llm_error:
        raise RuntimeError(ctx.llm_error)
    graph.invoke(initial_state(run_id, goal, cfg), {"configurable": {"thread_id": run_id}, "recursion_limit": 60})
    result = summarize_result(graph, run_id)
    result["llm_calls"] = ctx.llm_calls
    if result["status"] != "awaiting_approval":
        drop_context(run_id)
    return result


def resume_newsletter_agent(run_id: str, action: str, feedback: str = "", graph=None) -> dict:
    """Resume a paused Human-in-the-Loop run ('approve' or 'revise')."""
    if action not in ("approve", "revise"):
        raise ValueError("action must be 'approve' or 'revise'")
    if action == "revise" and len(feedback.strip()) < 3:
        raise ValueError("Please describe the changes you want.")
    graph = graph or _get_default_graph()
    graph.invoke(Command(resume={"action": action, "feedback": feedback}),
                 {"configurable": {"thread_id": run_id}, "recursion_limit": 60})
    result = summarize_result(graph, run_id)
    if result["status"] != "awaiting_approval":
        drop_context(run_id)
    return result
