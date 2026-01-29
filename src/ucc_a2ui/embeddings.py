from __future__ import annotations

import hashlib
import time
from typing import Iterable, List

import numpy as np
import requests


class EmbeddingClient:
    def __init__(self, batch_size: int = 8) -> None:
        self.batch_size = max(int(batch_size), 1)
        self.dim: int | None = None

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            dim = self.dim or 0
            return np.empty((0, dim), dtype=np.float32)
        batches = []
        for batch in _iter_batches(texts, self.batch_size):
            vectors = self._embed_batch(batch)
            vectors = np.asarray(vectors, dtype=np.float32)
            if vectors.ndim != 2:
                raise ValueError(f"Embedding output must be 2D, got shape={vectors.shape}")
            if self.dim is None:
                self.dim = int(vectors.shape[1])
            elif int(vectors.shape[1]) != self.dim:
                raise ValueError(
                    "Embedding dimension changed: "
                    f"expected {self.dim}, got {int(vectors.shape[1])}"
                )
            batches.append(vectors)
        if not batches:
            dim = self.dim or 0
            return np.empty((0, dim), dtype=np.float32)
        return np.vstack(batches)

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError


class MockEmbeddingClient(EmbeddingClient):
    def __init__(self, dim: int = 64, batch_size: int = 8) -> None:
        super().__init__(batch_size=batch_size)
        self.dim = dim

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        vectors = np.empty((len(texts), self.dim), dtype=np.float32)
        for idx, text in enumerate(texts):
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
            rng = np.random.default_rng(seed)
            vectors[idx] = rng.standard_normal(self.dim).astype(np.float32)
        return vectors


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: int = 60,
        retries: int = 2,
        batch_size: int = 8,
    ) -> None:
        super().__init__(batch_size=batch_size)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = int(timeout_s)
        self.retries = min(max(int(retries), 0), 2)

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        endpoint = _ollama_endpoint(self.base_url)
        payload = {"model": self.model}
        if endpoint.endswith("/embeddings"):
            payload["input"] = texts
        else:
            payload["input"] = texts
        data = _post_json(
            endpoint,
            payload,
            headers={"Content-Type": "application/json"},
            timeout_s=self.timeout_s,
            retries=self.retries,
        )
        if "data" in data:
            vectors = [item["embedding"] for item in data.get("data", [])]
        elif "embeddings" in data:
            vectors = data.get("embeddings", [])
        else:
            raise ValueError(f"Unexpected Ollama response format: {data}")
        return np.asarray(vectors, dtype=np.float32)


class QwenEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://dashscope.aliyuncs.com/api/v1/embeddings",
        timeout_s: int = 60,
        retries: int = 2,
        batch_size: int = 8,
    ) -> None:
        super().__init__(batch_size=batch_size)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout_s = int(timeout_s)
        self.retries = min(max(int(retries), 0), 2)

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "input": {"texts": texts},
        }
        data = _post_json(
            self.base_url,
            payload,
            headers=headers,
            timeout_s=self.timeout_s,
            retries=self.retries,
        )
        vectors = [item["embedding"] for item in data.get("output", {}).get("embeddings", [])]
        if not vectors:
            raise ValueError(f"Unexpected Qwen response format: {data}")
        return np.asarray(vectors, dtype=np.float32)


class FallbackEmbeddingClient:
    def __init__(
        self,
        primary: EmbeddingClient,
        fallback: EmbeddingClient,
        allow_fallback: bool = True,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.allow_fallback = allow_fallback
        self.dim: int | None = None

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        try:
            vectors = self.primary.embed_texts(texts)
            self.dim = self.primary.dim
            return vectors
        except Exception as exc:  # pragma: no cover - exercised in failure
            if not self.allow_fallback:
                raise
            print(f"[embed] primary backend failed, falling back to mock: {exc}")
            vectors = self.fallback.embed_texts(texts)
            self.dim = self.fallback.dim
            return vectors


def build_embedding_client(cfg: dict) -> EmbeddingClient | FallbackEmbeddingClient:
    backend = str(cfg.get("backend") or cfg.get("mode") or "mock").lower()
    if backend == "dashscope_qwen":
        backend = "qwen"
    if backend == "openai_compatible":
        backend = "ollama"
    base_url = str(cfg.get("base_url") or "http://localhost:11434")
    api_key = str(cfg.get("api_key") or "")
    model = str(cfg.get("model") or "")
    timeout_s = int(cfg.get("timeout", cfg.get("timeout_s", 60)))
    retries = int(cfg.get("retries", 2))
    batch_size = int(cfg.get("batch_size", 8))
    allow_fallback = bool(cfg.get("allow_fallback", True))
    mock_dim = int(cfg.get("mock_dim", 64))

    if backend == "qwen":
        primary = QwenEmbeddingClient(
            api_key=api_key,
            model=model,
            base_url=str(cfg.get("qwen_base_url", cfg.get("base_url", "https://dashscope.aliyuncs.com/api/v1/embeddings"))),
            timeout_s=timeout_s,
            retries=retries,
            batch_size=batch_size,
        )
    elif backend == "ollama":
        primary = OllamaEmbeddingClient(
            base_url=base_url,
            model=model,
            timeout_s=timeout_s,
            retries=retries,
            batch_size=batch_size,
        )
    else:
        return MockEmbeddingClient(dim=mock_dim, batch_size=batch_size)

    fallback = MockEmbeddingClient(dim=mock_dim, batch_size=batch_size)
    if allow_fallback:
        return FallbackEmbeddingClient(primary=primary, fallback=fallback, allow_fallback=True)
    return primary


def _iter_batches(items: List[str], batch_size: int) -> Iterable[List[str]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _ollama_endpoint(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    if cleaned.endswith("/v1"):
        return f"{cleaned}/embeddings"
    return f"{cleaned}/api/embed"


def _post_json(
    url: str,
    payload: dict,
    headers: dict,
    timeout_s: int,
    retries: int,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - need to wrap network errors
            last_error = exc
            if attempt >= retries:
                break
            sleep_s = 0.5 * (attempt + 1)
            time.sleep(sleep_s)
    raise RuntimeError(f"Embedding request failed after {retries + 1} attempts: {last_error}")
