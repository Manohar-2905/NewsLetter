"""Optional local provider using Ollama (https://ollama.com).

Free to run, but quality and speed depend on your hardware and model.
"""

from __future__ import annotations

import requests

from .llm_base import BaseLLM, LLMNotConfiguredError, LLMProviderError, LLMResponseError


class OllamaService(BaseLLM):
    name = "ollama"

    def __init__(self, base_url: str, model: str, enabled: bool = True, timeout: int = 120):
        super().__init__(model)
        if not enabled:
            raise LLMNotConfiguredError(
                "Ollama is disabled. Install Ollama, pull a model and set OLLAMA_ENABLED=true.", self.name
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = max(timeout, 120)

    def generate(self, prompt: str, system: str = "", json_mode: bool = False, max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            self._count()
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMProviderError(
                f"Could not reach Ollama at {self.base_url}. Is `ollama serve` running? ({exc})", self.name
            ) from exc
        if resp.status_code == 404:
            raise LLMProviderError(
                f"Ollama model '{self.model}' not found. Run `ollama pull {self.model}`.", self.name
            )
        if resp.status_code >= 400:
            raise LLMProviderError(f"Ollama error {resp.status_code}: {resp.text[:200]}", self.name)
        text = (resp.json().get("message") or {}).get("content", "")
        if not text:
            raise LLMResponseError("Ollama returned an empty response.", self.name)
        return text
