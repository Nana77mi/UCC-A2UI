from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class EmbeddingResult:
    vectors: Sequence[Sequence[float]]


class EmbedderBase:
    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        result = self.embed(texts)
        return np.asarray(result.vectors, dtype="float32")
