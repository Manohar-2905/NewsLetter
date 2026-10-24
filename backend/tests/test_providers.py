"""Provider error handling: quotas, rate limits, auth, fallbacks (all mocked)."""

import httpx
import openai
import pytest

from app.config import get_settings
from app.services.gemini_service import classify_gemini_error
from app.services.llm_base import (
    LLMAuthError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    parse_json_response,
)
from app.services.llm_factory import ResilientLLM, build_llm, create_provider
from app.services.openai_service import OpenAIService
from tests.conftest import FakeLLM


class FakeGeminiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def test_gemini_error_classification():
    daily = classify_gemini_error(FakeGeminiError(429, "RESOURCE_EXHAUSTED: Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
    assert isinstance(daily, LLMQuotaError)
    rpm = classify_gemini_error(FakeGeminiError(429, "RESOURCE_EXHAUSTED per minute. retryDelay: '17s'"))
    assert isinstance(rpm, LLMRateLimitError) and rpm.retry_after == 17
    assert isinstance(classify_gemini_error(FakeGeminiError(403, "API key not valid")), LLMAuthError)
    assert isinstance(classify_gemini_error(FakeGeminiError(404, "models/x not found")), LLMProviderError)


def test_missing_keys_raise_not_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(LLMNotConfiguredError):
        create_provider("gemini")
    with pytest.raises(LLMNotConfiguredError):
        create_provider("openai")
    with pytest.raises(LLMNotConfiguredError):
        create_provider("ollama")  # disabled by default


def test_rate_limit_retried_once():
    attempts = {"n": 0}

    def flaky(prompt):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return LLMRateLimitError("slow down", "fake", retry_after=99)
        return {"ok": True}

    waits = []
    llm = ResilientLLM(FakeLLM(overrides={"hello": flaky}), sleep=waits.append)
    assert llm.generate_json("hello") == {"ok": True}
    assert waits == [30.0]  # capped wait


def test_quota_not_retried_and_remembered():
    inner = FakeLLM(overrides={"hello": LLMQuotaError("quota gone", "fake")})
    llm = ResilientLLM(inner, sleep=lambda s: None)
    with pytest.raises(LLMQuotaError):
        llm.generate("hello")
    with pytest.raises(LLMQuotaError):
        llm.generate("hello again")
    assert inner.calls == 1  # second call short-circuited, no wasted requests


def test_auth_error_not_retried():
    inner = FakeLLM(overrides={"hello": LLMAuthError("bad key", "fake")})
    with pytest.raises(LLMAuthError):
        ResilientLLM(inner, sleep=lambda s: None).generate("hello")
    assert inner.calls == 1


def test_fallback_only_when_explicitly_configured():
    primary = FakeLLM(overrides={"hello": LLMQuotaError("quota", "fake")})
    backup = FakeLLM(overrides={"hello": {"from": "backup"}})
    events = []
    llm = ResilientLLM(primary, fallback_factory=lambda: backup, on_event=events.append, sleep=lambda s: None)
    assert llm.generate_json("hello") == {"from": "backup"}
    assert any("fallback" in e for e in events)  # switch is reported, never silent


def test_no_silent_switch_to_paid_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_FALLBACK_PROVIDER", "")
    get_settings.cache_clear()
    llm = build_llm("gemini")
    assert llm._fallback_factory is None


def test_openai_quota_and_auth_mapping(monkeypatch):
    svc = OpenAIService("sk-test", "gpt-test")
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")

    def raise_quota(**kw):
        raise openai.RateLimitError("quota", response=httpx.Response(429, request=request),
                                    body={"error": {"code": "insufficient_quota"}})

    monkeypatch.setattr(svc._client.responses, "create", raise_quota)
    with pytest.raises(LLMQuotaError):
        svc.generate("hi")

    def raise_auth(**kw):
        raise openai.AuthenticationError("bad", response=httpx.Response(401, request=request), body=None)

    monkeypatch.setattr(svc._client.responses, "create", raise_auth)
    with pytest.raises(LLMAuthError):
        svc.generate("hi")


def test_gemini_service_maps_sdk_errors(monkeypatch):
    from google.genai import errors

    from app.services.gemini_service import GeminiService

    svc = GeminiService("key", "gemini-test")

    def boom(**kw):
        raise errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded: limit per day", "status": "RESOURCE_EXHAUSTED"}})

    monkeypatch.setattr(svc._client.models, "generate_content", boom)
    with pytest.raises(LLMQuotaError):
        svc.generate("hi")


def test_malformed_json_repaired():
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response('Sure! Here it is: {"a": [1, 2]} hope it helps') == {"a": [1, 2]}
    calls = {"n": 0}

    def bad_then_good(prompt):
        calls["n"] += 1
        return "not json at all" if calls["n"] == 1 else '{"fixed": true}'

    llm = FakeLLM(overrides={"": bad_then_good})
    assert llm.generate_json("anything") == {"fixed": True}
