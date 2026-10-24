"""Shapes of the agent's main outputs (used for API documentation)."""

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ArticleOut(BaseModel):
    title: str
    url: str
    publisher: str
    published_at: Optional[str] = None
    content_status: Optional[str] = None
    source_api: Optional[str] = None
    excerpt: Optional[str] = None
    scores: Optional[dict[str, float]] = None


class ArticleSummary(BaseModel):
    headline: str
    publisher: str
    published_at: Optional[str] = None
    url: str
    summary: str
    key_takeaway: str = ""
    based_on: Literal["full_text", "excerpt", "headline_only"]
    limited_info: bool
    note: Optional[str] = None


class ReviewIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    fix: str = ""
    article_index: Optional[int] = None


class ReviewReport(BaseModel):
    passed: bool
    status: Literal["pass", "fail"]
    issues: list[ReviewIssue]
    error_count: int
    warning_count: int
    checks: dict[str, bool]
    scores: dict[str, Any] = {}
    semantic_review: dict[str, Any]
    recommendations: list[str] = []
    reviewed_at: str
    disclaimer: str
    attempt: Optional[int] = None


class NewsletterOut(BaseModel):
    subject: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    format: Optional[str] = None
    html: Optional[str] = None
    markdown: Optional[str] = None
    content: Optional[str] = None
    disclosures: list[str] = []
    key_takeaways: Optional[list[str]] = None
    research_brief: Optional[str] = None
    ranked_responses: list[dict[str, Any]] = []
