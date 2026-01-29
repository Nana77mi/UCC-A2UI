from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class EmbeddingResult:
    vectors: Sequence[Sequence[float]]


class EmbedderBase:
    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError
