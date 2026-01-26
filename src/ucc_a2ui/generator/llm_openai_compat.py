from __future__ import annotations

from typing import List

import requests

from .llm_client_base import LLMClientBase, LLMResponse


class OpenAICompatibleLLM(LLMClientBase):
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float, max_tokens: int, timeout_s: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    def complete(self, messages: List[dict]) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(content=content)
