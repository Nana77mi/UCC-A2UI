from __future__ import annotations

from typing import List

import requests

from .embedder_base import EmbeddingResult, EmbedderBase


class DashScopeQwenEmbedder(EmbedderBase):
    def __init__(self, api_key: str, model: str, timeout_s: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/embeddings"

    def embed(self, texts: List[str]) -> EmbeddingResult:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "input": {"texts": texts},
        }
        response = requests.post(self.base_url, headers=headers, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        data = response.json()
        vectors = [item["embedding"] for item in data.get("output", {}).get("embeddings", [])]
        return EmbeddingResult(vectors=vectors)
