from __future__ import annotations

import hashlib
from typing import List

import numpy as np

from .embedder_base import EmbeddingResult, EmbedderBase


class MockEmbedder(EmbedderBase):
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: List[str]) -> EmbeddingResult:
        vectors = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(self.dim).astype("float32")
            vectors.append(vector.tolist())
        return EmbeddingResult(vectors=vectors)
