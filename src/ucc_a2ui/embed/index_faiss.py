from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import faiss
import numpy as np


@dataclass
class IndexedChunk:
    text: str
    source: str
    doc_hash: str | None = None
    chunk_hash: str | None = None


class ChunkStore:
    def __init__(self, chunks_path: str | Path, offsets_path: str | Path) -> None:
        self.chunks_path = Path(chunks_path)
        self.offsets_path = Path(offsets_path)
        self._offsets = self._load_offsets()

    def _load_offsets(self) -> np.ndarray:
        if self.offsets_path.exists():
            return np.load(self.offsets_path)
        if not self.chunks_path.exists():
            return np.array([], dtype=np.int64)
        offsets: list[int] = []
        with self.chunks_path.open("rb") as handle:
            while True:
                offset = handle.tell()
                line = handle.readline()
                if not line:
                    break
                offsets.append(offset)
        arr = np.asarray(offsets, dtype=np.int64)
        if offsets:
            np.save(self.offsets_path, arr)
        return arr

    def __len__(self) -> int:
        return int(self._offsets.size)

    def get(self, index: int) -> IndexedChunk:
        offset = int(self._offsets[index])
        with self.chunks_path.open("rb") as handle:
            handle.seek(offset)
            line = handle.readline()
        payload = json.loads(line.decode("utf-8"))
        return IndexedChunk(**payload)


class InMemoryChunkStore:
    def __init__(self, chunks: List[IndexedChunk]) -> None:
        self._chunks = chunks

    def __len__(self) -> int:
        return len(self._chunks)

    def get(self, index: int) -> IndexedChunk:
        return self._chunks[index]


@dataclass
class FaissIndex:
    index: faiss.Index
    chunks: ChunkStore | InMemoryChunkStore


def build_faiss_index(
    vectors: Sequence[Sequence[float]] | np.ndarray, chunks: List[IndexedChunk]
) -> FaissIndex:
    if not vectors:
        raise ValueError("No vectors to index")
    dim = len(vectors[0])
    index = faiss.IndexFlatL2(dim)
    arr = np.asarray(vectors, dtype="float32")
    index.add(arr)
    return FaissIndex(index=index, chunks=InMemoryChunkStore(chunks))


def create_empty_index(dim: int) -> faiss.Index:
    return faiss.IndexFlatL2(dim)


def add_vectors(index: faiss.Index, vectors: Sequence[Sequence[float]] | np.ndarray) -> None:
    if isinstance(vectors, np.ndarray):
        if vectors.size == 0:
            return
        if vectors.dtype != np.float32:
            arr = vectors.astype(np.float32, copy=False)
        else:
            arr = vectors
    else:
        if not vectors:
            return
        arr = np.asarray(vectors, dtype=np.float32)
    index.add(arr)


def count_chunks(chunks_path: str | Path) -> int:
    chunks_path = Path(chunks_path)
    if not chunks_path.exists():
        return 0
    count = 0
    with chunks_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            count += block.count(b"\n")
    return count


def open_chunk_store(index_dir: str | Path) -> ChunkStore:
    index_dir = Path(index_dir)
    return ChunkStore(index_dir / "chunks.jsonl", index_dir / "chunks.offsets.npy")


def save_faiss_index_parts(index_dir: str | Path, index: faiss.Index) -> None:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "index.faiss"))


def save_faiss_index(index_dir: str | Path, faiss_index: FaissIndex) -> None:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(faiss_index.index, str(index_dir / "index.faiss"))


def load_faiss_index(index_dir: str | Path) -> FaissIndex:
    index_dir = Path(index_dir)
    index = faiss.read_index(str(index_dir / "index.faiss"))
    chunk_store = open_chunk_store(index_dir)
    return FaissIndex(index=index, chunks=chunk_store)
