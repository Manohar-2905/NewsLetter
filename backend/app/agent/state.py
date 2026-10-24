"""Shared state passed between LangGraph nodes.

Everything here is JSON serialisable so the SQLite checkpointer can persist it
(this is what lets a Human-in-the-Loop run survive a server restart).
"""

from typing import Any, TypedDict


class AgentConfig(TypedDict, total=False):
    provider: str           # gemini | openai | ollama
    output_format: str      # html | markdown
    article_count: int      # 5-7 by default
    tone: str               # professional | casual | technical | executive
    mode: str               # autonomous | hitl
    lookback_days: int


class AgentState(TypedDict, total=False):
    run_id: str
    goal: str
    config: AgentConfig

    plan: dict[str, Any]
    research_round: int
    research_log: list[dict]
    candidates: list[dict]
    ranked_responses: list[dict]
    research_brief: str

    selected: list[dict]        # raw source articles, in newsletter order
    reserve: list[dict]         # next best articles, used to replace bad ones
    summaries: list[dict]       # one per selected article, same order

    newsletter: dict[str, Any]
    revision_feedback: str
    review: dict[str, Any]
    review_history: list[dict]
    revision_count: int

    human_feedback: str
    human_feedback_history: list[str]
    human_rounds: int
    approved: bool

    output: dict[str, Any]
    status: str
    message: str
    warnings: list[str]
