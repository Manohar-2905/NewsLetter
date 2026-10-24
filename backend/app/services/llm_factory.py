"""Build LLM clients and wrap them with retry / quota handling."""

from __future__ import annotations

import logging
import time
from typing import Callable

from ..config import Settings, get_settings
from .gemini_service import GeminiService
from .llm_base import (
    BaseLLM,
    LLMError,
    LLMNotConfiguredError,
    LLMQuotaError,
    LLMRateLimitError,
)
from .ollama_service import OllamaService
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

MAX_RATE_LIMIT_WAIT = 30.0


def create_provider(provider: str, settings: Settings | None = None) -> BaseLLM:
    settings = settings or get_settings()
    provider = (provider or "").lower().strip()
    if provider == "gemini":
        return GeminiService(settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_seconds)
    if provider == "openai":
        return OpenAIService(settings.openai_api_key, settings.openai_model, settings.llm_timeout_seconds)
    if provider == "ollama":
        return OllamaService(
            settings.ollama_base_url, settings.ollama_model, settings.ollama_enabled, settings.llm_timeout_seconds
        )
    raise LLMNotConfiguredError(f"Unknown LLM provider '{provider}'.", provider)


class ResilientLLM(BaseLLM):
    """Wraps a provider with sensible, cost-aware retry rules.

    * rate limits (per minute): wait once (max 30s) and retry once
    * transient provider errors: retry once
    * quota exhausted / auth errors: never retried. If (and only if) the user
      explicitly configured LLM_FALLBACK_PROVIDER, switch to it and report it.
    """

    name = "resilient"

    def __init__(
        self,
        primary: BaseLLM,
        fallback_factory: Callable[[], BaseLLM] | None = None,
        on_event: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        super().__init__(primary.model)
        self.active = primary
        self._fallback_factory = fallback_factory
        self._on_event = on_event or (lambda msg: None)
        self._sleep = sleep
        self.exhausted: LLMQuotaError | None = None

    @property
    def label(self) -> str:
        return self.active.label

    @property
    def calls(self) -> int:  # type: ignore[override]
        return self.active.calls

    @calls.setter
    def calls(self, value):  # BaseLLM.__init__ assigns it
        pass

    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_tokens: int = 2048) -> str:
        if self.exhausted is not None:
            raise self.exhausted
        attempt = 0
        while True:
            try:
                return self.active.generate(prompt, system=system, json_mode=json_mode, max_tokens=max_tokens)
            except LLMRateLimitError as exc:
                if attempt >= 1:
                    raise
                wait = min(exc.retry_after or 10.0, MAX_RATE_LIMIT_WAIT)
                self._on_event(f"{self.active.label} rate limited, waiting {wait:.0f}s before one retry")
                self._sleep(wait)
            except LLMQuotaError as exc:
                if self._fallback_factory is not None:
                    factory, self._fallback_factory = self._fallback_factory, None
                    try:
                        fallback = factory()
                    except LLMError as fb_exc:
                        self.exhausted = exc
                        raise exc from fb_exc
                    self._on_event(
                        f"{self.active.label} quota exhausted; switching to explicitly configured "
                        f"fallback {fallback.label}"
                    )
                    self.active = fallback
                    attempt = 0
                    continue
                self.exhausted = exc
                raise
            except LLMError as exc:
                if not exc.retryable or attempt >= 1:
                    raise
                logger.warning("LLM transient error, retrying once: %s", exc)
                self._sleep(2.0)
            attempt += 1


def build_llm(
    provider: str | None = None,
    settings: Settings | None = None,
    on_event: Callable[[str], None] | None = None,
) -> ResilientLLM:
    settings = settings or get_settings()
    provider = provider or settings.llm_provider
    primary = create_provider(provider, settings)
    fallback_name = (settings.llm_fallback_provider or "").strip().lower()
    fallback_factory = None
    if fallback_name and fallback_name != provider:
        fallback_factory = lambda: create_provider(fallback_name, settings)  # noqa: E731
    return ResilientLLM(primary, fallback_factory=fallback_factory, on_event=on_event)


def build_critic_llm(
    primary_provider: str, settings: Settings | None = None, on_event: Callable[[str], None] | None = None
) -> ResilientLLM | None:
    """Return an independent critic model only if one is configured and different."""
    settings = settings or get_settings()
    name = (settings.critic_provider or "").strip().lower()
    if not name or name == primary_provider or not settings.provider_configured(name):
        return None
    try:
        return ResilientLLM(create_provider(name, settings), on_event=on_event)
    except LLMError:
        return None
