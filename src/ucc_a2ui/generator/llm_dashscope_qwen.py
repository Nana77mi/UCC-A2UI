from __future__ import annotations

from typing import List

import requests

from .llm_client_base import LLMClientBase, LLMResponse


class DashScopeQwenLLM(LLMClientBase):
    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int, timeout_s: int) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    def complete(self, messages: List[dict]) -> LLMResponse:
        if not self.api_key:
            raise ValueError("DashScope API key is required. Set llm.api_key in config.yaml.")
        if not self.model:
            raise ValueError("DashScope model is required. Set llm.model in config.yaml.")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
        }
        response = requests.post(self.base_url, headers=headers, json=payload, timeout=self.timeout_s)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text.strip()
            raise requests.HTTPError(f"{exc} - {detail}") from exc
        data = response.json()
        content = data.get("output", {}).get("text", "")
        return LLMResponse(content=content)
