from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import faiss
import numpy as np


@dataclass
class IndexedChunk:
    text: str
    source: str
    doc_hash: str | None = None
    chunk_hash: str | None = None


@dataclass
class FaissIndex:
    index: faiss.Index
    chunks: List[IndexedChunk]


def build_faiss_index(vectors: List[List[float]], chunks: List[IndexedChunk]) -> FaissIndex:
    if not vectors:
        raise ValueError("No vectors to index")
    dim = len(vectors[0])
    index = faiss.IndexFlatL2(dim)
    arr = np.array(vectors, dtype="float32")
    index.add(arr)
    return FaissIndex(index=index, chunks=chunks)


def create_empty_index(dim: int) -> faiss.Index:
    return faiss.IndexFlatL2(dim)


def add_vectors(index: faiss.Index, vectors: List[List[float]]) -> None:
    if not vectors:
        return
    arr = np.array(vectors, dtype="float32")
    index.add(arr)


def save_faiss_index_parts(index_dir: str | Path, index: faiss.Index, chunks: List[IndexedChunk]) -> None:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "index.faiss"))
    metadata = [chunk.__dict__ for chunk in chunks]
    (index_dir / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def save_faiss_index(index_dir: str | Path, faiss_index: FaissIndex) -> None:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss_index.index, str(index_dir / "index.faiss"))
    metadata = [chunk.__dict__ for chunk in faiss_index.chunks]
    (index_dir / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def load_faiss_index(index_dir: str | Path) -> FaissIndex:
    index_dir = Path(index_dir)
    index = faiss.read_index(str(index_dir / "index.faiss"))
    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
    chunks = [IndexedChunk(**item) for item in meta]
    return FaissIndex(index=index, chunks=chunks)
