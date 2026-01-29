from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class EmbeddingResult:
    vectors: List[List[float]]


class EmbedderBase:
    def embed(self, texts: List[str]) -> EmbeddingResult:
        raise NotImplementedError
