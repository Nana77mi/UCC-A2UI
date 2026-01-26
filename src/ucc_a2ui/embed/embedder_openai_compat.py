from __future__ import annotations

from typing import List

import requests

from .embedder_base import EmbeddingResult, EmbedderBase


class OpenAICompatibleEmbedder(EmbedderBase):
    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def embed(self, texts: List[str]) -> EmbeddingResult:
        url = f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "input": texts}
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        response.raise_for_status()
        data = response.json()
        vectors = [item["embedding"] for item in data.get("data", [])]
        return EmbeddingResult(vectors=vectors)
