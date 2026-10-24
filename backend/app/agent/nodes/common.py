"""Helpers shared by the nodes."""

from __future__ import annotations

from ...services.llm_base import BaseLLM, LLMQuotaError
from ..context import RunContext, get_context


def ctx_for(state: dict) -> RunContext:
    return get_context(state["run_id"], (state.get("config") or {}).get("provider"))


def usable_llm(ctx: RunContext) -> BaseLLM | None:
    """Return the model, or None if it is unavailable / its quota is exhausted."""
    llm = ctx.llm
    if llm is None:
        return None
    if getattr(llm, "exhausted", None) is not None:
        return None
    return llm


def quota_warning(ctx: RunContext, step: str, exc: LLMQuotaError) -> str:
    msg = f"{exc} Step '{step}' continued with a deterministic fallback."
    ctx.emit(step, "warning", msg)
    return msg
