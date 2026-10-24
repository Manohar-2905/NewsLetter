from typing import Any, Optional

from pydantic import BaseModel

from .newsletter import ArticleOut, ArticleSummary, NewsletterOut, ReviewReport


class RunResult(BaseModel):
    status: Optional[str] = None
    message: Optional[str] = None
    plan: Optional[dict[str, Any]] = None
    research_log: list[dict[str, Any]] = []
    ranked_responses: list[dict[str, Any]] = []
    research_brief: str = ""
    candidates_count: Optional[int] = None
    articles: list[ArticleOut] = []
    selected: list[ArticleOut] = []
    summaries: list[ArticleSummary] = []
    newsletter: Optional[NewsletterOut] = None
    review: Optional[ReviewReport] = None
    review_history: list[dict[str, Any]] = []
    revision_count: int = 0
    human_rounds: int = 0
    approved: bool = False
    output: Optional[dict[str, Any]] = None
    warnings: list[str] = []
    llm_calls: Optional[int] = None


class RunCreated(BaseModel):
    run_id: str
    status: str


class RunStatus(BaseModel):
    run_id: str
    goal: str
    status: str
    message: Optional[str] = None
    error: Optional[str] = None
    config: dict[str, Any]
    created_at: str
    updated_at: str
    events: list[dict[str, Any]] = []
    result: RunResult = RunResult()
    downloads: dict[str, str] = {}


class RunListItem(BaseModel):
    run_id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    subject: Optional[str] = None
