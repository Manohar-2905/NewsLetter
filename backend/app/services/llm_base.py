"""Shared pieces for every LLM provider.

Each provider implements `generate(prompt, system, json_mode, max_tokens)` and
raises one of the errors below so the agent can react the same way no matter
which provider is in use.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any


class LLMError(Exception):
    """Base error for model providers."""

    retryable = False

    def __init__(self, message: str, provider: str = ""):
        super().__init__(message)
        self.provider = provider


class LLMNotConfiguredError(LLMError):
    """The provider is missing an API key or is disabled."""


class LLMQuotaError(LLMError):
    """Free quota / credits exhausted. Never retried automatically."""


class LLMRateLimitError(LLMError):
    """Short term rate limit (requests per minute)."""

    retryable = True

    def __init__(self, message: str, provider: str = "", retry_after: float | None = None):
        super().__init__(message, provider)
        self.retry_after = retry_after


class LLMAuthError(LLMError):
    """Invalid / unauthorised API key. Never retried."""


class LLMProviderError(LLMError):
    """Any other provider failure (network, 5xx, bad model name ...)."""

    retryable = True


class LLMResponseError(LLMError):
    """The model answered but the answer was not usable (e.g. bad JSON)."""


class BaseLLM:
    name = "base"

    def __init__(self, model: str):
        self.model = model
        self.calls = 0
        self._lock = threading.Lock()

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"

    def _count(self) -> None:
        with self._lock:
            self.calls += 1

    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_tokens: int = 2048) -> str:
        raise NotImplementedError

    def generate_json(self, prompt: str, system: str = "", max_tokens: int = 2048) -> Any:
        """Generate and parse JSON, with one repair attempt on malformed output."""
        text = self.generate(prompt, system=system, json_mode=True, max_tokens=max_tokens)
        try:
            return parse_json_response(text)
        except LLMResponseError:
            repair_prompt = (
                "The following text was supposed to be valid JSON but is malformed. "
                "Return ONLY the corrected JSON, nothing else.\n\n" + text[:6000]
            )
            text = self.generate(repair_prompt, system="You fix JSON.", json_mode=True, max_tokens=max_tokens)
            return parse_json_response(text)


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_json_response(text: str) -> Any:
    """Parse JSON from a model response, tolerating code fences or extra prose."""
    if text is None:
        raise LLMResponseError("Empty model response")
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass
    # Fall back to the outermost {...} or [...] block.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(open_ch), cleaned.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                continue
    raise LLMResponseError("Model did not return valid JSON")
