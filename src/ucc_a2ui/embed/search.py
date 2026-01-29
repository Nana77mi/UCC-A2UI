from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List

import faiss
import numpy as np

from .embedder_base import EmbedderBase


@dataclass
class SearchResult:
    score: float
    text: str
    source: str


def search_index(index_dir: str, query: str, embedder: EmbedderBase, top_k: int = 5) -> List[SearchResult]:
    index_path = Path(index_dir) / "index.faiss"
    meta_path = Path(index_dir) / "index_meta.json"
    normalize = False
    if meta_path.exists():
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        normalize = bool(payload.get("normalize", False))
    index = faiss.read_index(str(index_path))
    query_vec = embedder.embed_texts([query])[0]
    if normalize:
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm
    query_arr = np.array([query_vec], dtype="float32")
    distances, indices = index.search(query_arr, top_k)
    targets = {int(idx) for idx in indices[0] if idx >= 0}
    chunk_lookup: Dict[int, Dict[str, str]] = {}
    chunks_path = Path(index_dir) / "chunks.jsonl"
    if targets and chunks_path.exists():
        max_target = max(targets)
        with chunks_path.open("r", encoding="utf-8") as handle:
            for row_id, line in enumerate(handle):
                if row_id > max_target:
                    break
                if row_id not in targets:
                    continue
                payload = json.loads(line)
                chunk_lookup[row_id] = {
                    "text": payload.get("text", ""),
                    "source": payload.get("source", ""),
                }
    results: List[SearchResult] = []
    for rank, idx in enumerate(indices[0]):
        if idx < 0:
            continue
        chunk = chunk_lookup.get(int(idx))
        if not chunk:
            continue
        score = float(distances[0][rank])
        results.append(SearchResult(score=score, text=chunk["text"], source=chunk["source"]))
    return results
