"""Optional OpenAI provider.

OpenAI API usage is billed per token. A ChatGPT Plus/Pro subscription does
NOT include API credits, so this provider is never used unless you set
OPENAI_API_KEY and select it.
"""

from __future__ import annotations

from .llm_base import (
    BaseLLM,
    LLMAuthError,
    LLMNotConfiguredError,
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseError,
)


class OpenAIService(BaseLLM):
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: int = 60):
        super().__init__(model)
        if not api_key:
            raise LLMNotConfiguredError(
                "OpenAI is not configured. Add OPENAI_API_KEY to backend/.env (paid API usage).", self.name
            )
        import openai

        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=0)

    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_tokens: int = 2048) -> str:
        openai = self._openai
        kwargs = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_tokens,
        }
        if system:
            kwargs["instructions"] = system
        if json_mode:
            kwargs["text"] = {"format": {"type": "json_object"}}
        try:
            self._count()
            response = self._client.responses.create(**kwargs)
        except openai.RateLimitError as exc:
            body = str(getattr(exc, "body", "") or exc).lower()
            if "insufficient_quota" in body or "quota" in body:
                raise LLMQuotaError(
                    "OpenAI quota/credits exhausted for this API key. Add credits or use another provider.",
                    self.name,
                ) from exc
            raise LLMRateLimitError("OpenAI rate limit reached.", self.name) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise LLMAuthError("OpenAI rejected the API key. Check OPENAI_API_KEY.", self.name) from exc
        except openai.APIError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}", self.name) from exc
        except Exception as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}", self.name) from exc

        text = getattr(response, "output_text", None)
        if not text:
            raise LLMResponseError("OpenAI returned an empty response.", self.name)
        return text
