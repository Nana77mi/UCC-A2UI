from __future__ import annotations

import time
from typing import List

import requests

from .embedder_base import EmbeddingResult, EmbedderBase


class OpenAICompatibleEmbedder(EmbedderBase):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: int = 60,
        retries: int = 2,
        retry_backoff_s: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.retries = retries
        self.retry_backoff_s = retry_backoff_s

    def embed(self, texts: List[str]) -> EmbeddingResult:
        url = f"{self.base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "input": texts}
        attempt = 0
        while True:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
            if response.status_code == 503 and attempt < self.retries:
                time.sleep(self.retry_backoff_s * (2**attempt))
                attempt += 1
                continue
            response.raise_for_status()
            data = response.json()
            break
        vectors = [item["embedding"] for item in data.get("data", [])]
        return EmbeddingResult(vectors=vectors)
