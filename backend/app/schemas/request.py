from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=500, description="Topic or goal in plain English")
    mode: Literal["autonomous", "hitl"] = "autonomous"
    article_count: int = Field(5, ge=1, le=7)
    tone: Literal["professional", "casual", "technical", "executive"] = "professional"
    output_format: Literal["html", "markdown"] = "html"
    provider: Optional[Literal["gemini", "openai", "ollama"]] = None
    lookback_days: Optional[int] = Field(None, ge=1, le=30)

    @field_validator("goal")
    @classmethod
    def goal_not_blank(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Please enter a topic or goal (at least 3 characters).")
        if not any(ch.isalpha() for ch in value):
            raise ValueError("The topic must contain words.")
        return value


class ReviseRequest(BaseModel):
    feedback: str = Field(..., min_length=3, max_length=2000)

    @field_validator("feedback")
    @classmethod
    def feedback_not_blank(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Please describe the changes you want.")
        return value
