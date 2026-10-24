"""Per-run resources (model clients, progress reporting).

Model clients can't live inside the checkpointed state, so each run gets a
RunContext looked up by run_id. It is rebuilt automatically after a restart.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable

from ..config import get_settings
from ..services.llm_base import BaseLLM, LLMError
from ..services.llm_factory import build_critic_llm, build_llm

logger = logging.getLogger(__name__)

# sink(run_id, event_dict) — set by the API layer to record progress.
EventSink = Callable[[str, dict], None]
_event_sink: EventSink | None = None
_contexts: dict[str, "RunContext"] = {}
_lock = threading.Lock()


def set_event_sink(sink: EventSink | None) -> None:
    global _event_sink
    _event_sink = sink


class RunContext:
    def __init__(
        self,
        run_id: str,
        provider: str,
        llm: BaseLLM | None = None,
        critic_llm: BaseLLM | None = None,
        sink: EventSink | None = None,
        build_models: bool = True,
    ):
        self.run_id = run_id
        self.provider = provider
        self._sink = sink
        self.llm_error: str | None = None
        self.llm = llm
        self.critic_llm = critic_llm
        if llm is None and build_models:
            try:
                self.llm = build_llm(provider, on_event=lambda m: self.emit("llm", "info", m))
            except LLMError as exc:
                self.llm_error = str(exc)
            if critic_llm is None:
                self.critic_llm = build_critic_llm(provider, on_event=lambda m: self.emit("llm", "info", m))

    def emit(self, step: str, status: str, message: str, data: dict | None = None) -> None:
        event = {
            "step": step,
            "status": status,
            "message": message,
            "data": data or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("[%s] %s/%s: %s", self.run_id[:8], step, status, message)
        sink = self._sink or _event_sink
        if sink:
            try:
                sink(self.run_id, event)
            except Exception:  # never let progress reporting break the agent
                logger.exception("event sink failed")

    def publish(self, **partial) -> None:
        """Push partial results (e.g. research results) to the UI early."""
        self.emit("data", "update", "partial results", {"partial": partial})

    @property
    def llm_calls(self) -> int:
        total = self.llm.calls if self.llm else 0
        if self.critic_llm:
            total += self.critic_llm.calls
        return total


def register_context(ctx: RunContext) -> RunContext:
    with _lock:
        _contexts[ctx.run_id] = ctx
    return ctx


def get_context(run_id: str, provider: str | None = None) -> RunContext:
    with _lock:
        ctx = _contexts.get(run_id)
    if ctx is None:
        ctx = register_context(RunContext(run_id, provider or get_settings().llm_provider))
    return ctx


def drop_context(run_id: str) -> None:
    with _lock:
        _contexts.pop(run_id, None)
