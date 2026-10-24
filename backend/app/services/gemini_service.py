"""Google Gemini provider (default, free tier friendly)."""

from __future__ import annotations

import re

from .llm_base import (
    BaseLLM,
    LLMAuthError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseError,
)

_RETRY_RE = re.compile(r"retry(?:Delay)?['\"]?\s*[:=]?\s*['\"]?(\d+(?:\.\d+)?)s", re.IGNORECASE)


class GeminiService(BaseLLM):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: int = 60):
        super().__init__(model)
        if not api_key:
            raise LLMNotConfiguredError(
                "Gemini is not configured. Add GEMINI_API_KEY to backend/.env "
                "(free key: https://aistudio.google.com/apikey).",
                self.name,
            )
        from google import genai  # imported lazily so tests don't need it

        self._client = genai.Client(api_key=api_key, http_options={"timeout": timeout * 1000})

    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_tokens: int = 2048) -> str:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
        )
        try:
            self._count()
            response = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        except errors.ClientError as exc:  # 4xx
            raise classify_gemini_error(exc) from exc
        except errors.ServerError as exc:  # 5xx
            raise LLMProviderError(f"Gemini server error: {exc}", self.name) from exc
        except Exception as exc:  # network / timeout
            raise LLMProviderError(f"Gemini request failed: {exc}", self.name) from exc

        text = getattr(response, "text", None)
        if not text:
            raise LLMResponseError("Gemini returned an empty response (it may have been blocked).", self.name)
        return text


def classify_gemini_error(exc) -> Exception:
    code = getattr(exc, "code", None)
    message = str(getattr(exc, "message", "") or exc)
    lower = message.lower()
    if code == 429 or "resource_exhausted" in lower:
        # Daily quota / free tier exhausted -> permanent for this run.
        if "perday" in lower.replace(" ", "") or "per day" in lower or "daily" in lower or "limit: 0" in lower:
            return LLMQuotaError(
                "Gemini free-tier daily quota is exhausted for this project. It resets at midnight "
                "Pacific time. Try later, use another configured provider, or enable billing.",
                "gemini",
            )
        match = _RETRY_RE.search(message)
        retry_after = float(match.group(1)) if match else None
        return LLMRateLimitError(
            "Gemini rate limit reached (requests per minute).", "gemini", retry_after=retry_after
        )
    if code in (401, 403) or "api key" in lower or "permission" in lower:
        return LLMAuthError("Gemini rejected the API key. Check GEMINI_API_KEY.", "gemini")
    if code == 404:
        return LLMProviderError(
            f"Gemini model not found ({message[:120]}). Check GEMINI_MODEL in backend/.env.", "gemini"
        )
    return LLMProviderError(f"Gemini request error ({code}): {message[:300]}", "gemini")

