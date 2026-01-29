from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from .embedder_base import EmbedderBase
from .index_faiss import FaissIndex, load_faiss_index


@dataclass
class SearchResult:
    score: float
    text: str
    source: str


def search_index(index_dir: str, query: str, embedder: EmbedderBase, top_k: int = 5) -> List[SearchResult]:
    faiss_index = load_faiss_index(index_dir)
    query_vec = embedder.embed([query]).vectors[0]
    query_arr = np.array([query_vec], dtype="float32")
    distances, indices = faiss_index.index.search(query_arr, top_k)
    results: List[SearchResult] = []
    for rank, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(faiss_index.chunks):
            continue
        chunk = faiss_index.chunks[idx]
        score = float(distances[0][rank])
        results.append(SearchResult(score=score, text=chunk.text, source=chunk.source))
    return results
