from __future__ import annotations

import gc
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

import numpy as np

from .embed.embedder_base import EmbedderBase

try:
    import faiss
except ImportError:  # pragma: no cover - optional dependency
    faiss = None

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


@dataclass
class EmbedManifest:
    out_dir: str
    dim: int
    total_vectors: int
    shard_size: int
    shards: List[str]
    chunks_path: str


def _iter_json_array(handle) -> Iterator[object]:
    decoder = json.JSONDecoder()
    buffer = ""
    for chunk in iter(lambda: handle.read(1024 * 1024), ""):
        buffer += chunk
        while True:
            stripped = buffer.lstrip()
            if not stripped:
                break
            if stripped[0] in "[,":
                stripped = stripped[1:].lstrip()
            if stripped.startswith("]"):
                return
            try:
                obj, idx = decoder.raw_decode(stripped)
            except json.JSONDecodeError:
                break
            yield obj
            buffer = stripped[idx:]
    remaining = buffer.strip()
    if remaining and remaining not in ("]", ""):
        obj, _ = decoder.raw_decode(remaining)
        yield obj


def _iter_documents_from_json(path: Path) -> Iterator[Tuple[str, str, str | None]]:
    with path.open("r", encoding="utf-8") as handle:
        first_char = ""
        while True:
            first_char = handle.read(1)
            if not first_char:
                break
            if not first_char.isspace():
                break
        handle.seek(0)
        if first_char == "[":
            for record in _iter_json_array(handle):
                if isinstance(record, str):
                    text = record
                    source = str(path)
                    doc_hash = None
                else:
                    text = record.get("text", "")
                    source = record.get("source", str(path))
                    doc_hash = record.get("doc_hash")
                yield text, source, doc_hash
            return
        payload = json.load(handle)
    if isinstance(payload, dict) and "documents" in payload:
        payload = payload["documents"]
    if isinstance(payload, list):
        for record in payload:
            if isinstance(record, str):
                text = record
                source = str(path)
                doc_hash = None
            else:
                text = record.get("text", "")
                source = record.get("source", str(path))
                doc_hash = record.get("doc_hash")
            yield text, source, doc_hash


def _iter_documents_from_jsonl(path: Path) -> Iterator[Tuple[str, str, str | None]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, str):
                text = payload
                source = str(path)
                doc_hash = None
            else:
                text = payload.get("text", "")
                source = payload.get("source", str(path))
                doc_hash = payload.get("doc_hash")
            yield text, source, doc_hash


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("r", encoding="utf-8") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), ""):
            if not chunk:
                break
            hasher.update(chunk.encode("utf-8"))
    return hasher.hexdigest()


def _iter_chunks_from_file(path: Path, chunk_size: int, chunk_overlap: int) -> Iterator[str]:
    if chunk_size <= 0:
        yield path.read_text(encoding="utf-8")
        return
    buffer = ""
    with path.open("r", encoding="utf-8") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), ""):
            if not chunk:
                break
            buffer += chunk
            while len(buffer) >= chunk_size:
                yield buffer[:chunk_size]
                if chunk_overlap > 0:
                    buffer = buffer[chunk_size - chunk_overlap :]
                else:
                    buffer = buffer[chunk_size:]
        if buffer:
            yield buffer


def _iter_chunks(text: str, chunk_size: int, chunk_overlap: int) -> Iterator[str]:
    if chunk_size <= 0:
        yield text
        return
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        yield text[start:end]
        start = end - chunk_overlap if chunk_overlap > 0 else end
        if start < 0:
            start = 0
        if start >= length:
            break


def _iter_documents(
    sources: Iterable[str],
    chunk_size: int,
    chunk_overlap: int,
) -> Iterator[Tuple[str, str, str, str]]:
    for source in sources:
        path = Path(source)
        if path.suffix.lower() == ".jsonl":
            for text, record_source, doc_hash in _iter_documents_from_jsonl(path):
                doc_hash = doc_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()
                for chunk in _iter_chunks(text, chunk_size, chunk_overlap):
                    chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                    yield chunk, record_source, doc_hash, chunk_hash
            continue
        if path.suffix.lower() == ".json":
            for text, record_source, doc_hash in _iter_documents_from_json(path):
                doc_hash = doc_hash or hashlib.sha256(text.encode("utf-8")).hexdigest()
                for chunk in _iter_chunks(text, chunk_size, chunk_overlap):
                    chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                    yield chunk, record_source, doc_hash, chunk_hash
            continue
        doc_hash = _file_hash(path)
        for chunk in _iter_chunks_from_file(path, chunk_size, chunk_overlap):
            chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            yield chunk, str(path), doc_hash, chunk_hash


def _open_shard(out_dir: Path, shard_id: int, shard_size: int, dim: int) -> np.memmap:
    shard_path = out_dir / f"vectors_shard_{shard_id}.mmap"
    return np.memmap(shard_path, dtype="float32", mode="w+", shape=(shard_size, dim))


def _rss_mb() -> float | None:
    if psutil is None:
        return None
    return psutil.Process().memory_info().rss / (1024 * 1024)


def embed_to_disk(
    sources: Iterable[str],
    embedder: EmbedderBase,
    out_dir: str | Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
    shard_size: int,
    max_rss_mb: int = 1500,
) -> EmbedManifest:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = out_dir / "chunks.jsonl"
    batch_texts: List[str] = []
    batch_meta: List[Tuple[str, str, str]] = []
    shard_id = 0
    row_id = 0
    dim: int | None = None
    current_shard: np.memmap | None = None
    total_written = 0
    shard_paths: List[str] = []
    batch_id = 0

    with chunks_path.open("w", encoding="utf-8") as chunk_handle:
        for chunk_text, source, doc_hash, chunk_hash in _iter_documents(
            sources, chunk_size, chunk_overlap
        ):
            batch_texts.append(chunk_text)
            batch_meta.append((source, doc_hash, chunk_hash))
            if len(batch_texts) < batch_size:
                continue
            batch_id += 1
            vectors = embedder.embed_texts(batch_texts)
            if vectors.ndim != 2:
                raise ValueError("Embedder returned invalid shape")
            if dim is None:
                dim = int(vectors.shape[1])
            for idx, vector in enumerate(vectors):
                if current_shard is None:
                    current_shard = _open_shard(out_dir, shard_id, shard_size, dim)
                    shard_paths.append(str(out_dir / f"vectors_shard_{shard_id}.mmap"))
                if row_id >= shard_size:
                    current_shard.flush()
                    del current_shard
                    shard_id += 1
                    row_id = 0
                    current_shard = _open_shard(out_dir, shard_id, shard_size, dim)
                    shard_paths.append(str(out_dir / f"vectors_shard_{shard_id}.mmap"))
                current_shard[row_id] = vector
                source_val, doc_hash_val, chunk_hash_val = batch_meta[idx]
                record = {
                    "text": batch_texts[idx],
                    "source": source_val,
                    "doc_hash": doc_hash_val,
                    "chunk_hash": chunk_hash_val,
                    "shard_id": shard_id,
                    "row_id": row_id,
                    "dim": dim,
                }
                chunk_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                row_id += 1
                total_written += 1
            del vectors
            del batch_texts
            del batch_meta
            batch_texts = []
            batch_meta = []
            gc.collect()
            rss_mb = _rss_mb()
            print(
                "[embed] batch",
                f"#{batch_id}",
                f"rss_mb={rss_mb:.1f}" if rss_mb is not None else "rss_mb=unavailable",
                f"shard_id={shard_id}",
                f"total_written={total_written}",
            )
            if rss_mb is not None and rss_mb > max_rss_mb:
                new_batch_size = max(1, batch_size // 2)
                if new_batch_size == batch_size and batch_size == 1:
                    raise RuntimeError(
                        f"RSS {rss_mb:.1f}MB exceeded max_rss_mb={max_rss_mb}; "
                        "batch_size already at 1."
                    )
                batch_size = new_batch_size

        if batch_texts:
            batch_id += 1
            vectors = embedder.embed_texts(batch_texts)
            if vectors.ndim != 2:
                raise ValueError("Embedder returned invalid shape")
            if dim is None:
                dim = int(vectors.shape[1])
            for idx, vector in enumerate(vectors):
                if current_shard is None:
                    current_shard = _open_shard(out_dir, shard_id, shard_size, dim)
                    shard_paths.append(str(out_dir / f"vectors_shard_{shard_id}.mmap"))
                if row_id >= shard_size:
                    current_shard.flush()
                    del current_shard
                    shard_id += 1
                    row_id = 0
                    current_shard = _open_shard(out_dir, shard_id, shard_size, dim)
                    shard_paths.append(str(out_dir / f"vectors_shard_{shard_id}.mmap"))
                current_shard[row_id] = vector
                source_val, doc_hash_val, chunk_hash_val = batch_meta[idx]
                record = {
                    "text": batch_texts[idx],
                    "source": source_val,
                    "doc_hash": doc_hash_val,
                    "chunk_hash": chunk_hash_val,
                    "shard_id": shard_id,
                    "row_id": row_id,
                    "dim": dim,
                }
                chunk_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                row_id += 1
                total_written += 1
            del vectors
            del batch_texts
            del batch_meta
            batch_texts = []
            batch_meta = []
            gc.collect()
            rss_mb = _rss_mb()
            print(
                "[embed] batch",
                f"#{batch_id}",
                f"rss_mb={rss_mb:.1f}" if rss_mb is not None else "rss_mb=unavailable",
                f"shard_id={shard_id}",
                f"total_written={total_written}",
            )
            if rss_mb is not None and rss_mb > max_rss_mb:
                new_batch_size = max(1, batch_size // 2)
                if new_batch_size == batch_size and batch_size == 1:
                    raise RuntimeError(
                        f"RSS {rss_mb:.1f}MB exceeded max_rss_mb={max_rss_mb}; "
                        "batch_size already at 1."
                    )
                batch_size = new_batch_size

    if current_shard is not None:
        current_shard.flush()
        del current_shard

    if dim is None:
        raise ValueError("No vectors written")

    manifest = EmbedManifest(
        out_dir=str(out_dir),
        dim=dim,
        total_vectors=total_written,
        shard_size=shard_size,
        shards=shard_paths,
        chunks_path=str(chunks_path),
    )
    manifest_path = out_dir / "embed_manifest.json"
    manifest_path.write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    vectors /= norms
    return vectors


def build_index_from_disk(
    out_dir: str | Path,
    *,
    index_type: str = "ivfpq",
    nlist: int = 4096,
    m: int = 48,
    nbits: int = 8,
    nprobe: int = 32,
    train_max: int = 20000,
    block_size: int = 8192,
    normalize: bool = True,
    shard_size: int = 50_000,
) -> None:
    if faiss is None:
        raise RuntimeError("faiss is required to build an index")
    out_dir = Path(out_dir)
    chunks_path = out_dir / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Missing chunks.jsonl at {chunks_path}")

    shard_counts: Dict[int, int] = {}
    shard_ids: set[int] = set()
    total_vectors = 0
    dim: int | None = None
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if dim is None:
                dim = int(payload.get("dim", 0))
            shard_id = int(payload["shard_id"])
            shard_ids.add(shard_id)
            shard_counts[shard_id] = shard_counts.get(shard_id, 0) + 1
            total_vectors += 1
    if dim is None or dim <= 0:
        raise ValueError("Invalid embedding dimension in chunks.jsonl")

    metric = faiss.METRIC_INNER_PRODUCT if normalize else faiss.METRIC_L2
    if index_type == "flat":
        if normalize:
            index = faiss.IndexFlatIP(dim)
        else:
            index = faiss.IndexFlatL2(dim)
    else:
        quantizer = faiss.IndexFlatIP(dim) if normalize else faiss.IndexFlatL2(dim)
        index = faiss.IndexIVFPQ(quantizer, dim, nlist, m, nbits, metric)
        index.nprobe = nprobe

    if index_type != "flat":
        train_count = min(train_max, total_vectors)
        train_arr = np.empty((train_count, dim), dtype="float32")
        filled = 0
        for shard_id in sorted(shard_ids):
            shard_path = out_dir / f"vectors_shard_{shard_id}.mmap"
            count = shard_counts[shard_id]
            mmap = np.memmap(shard_path, dtype="float32", mode="r", shape=(shard_size, dim))
            available = min(count, train_count - filled)
            if available <= 0:
                del mmap
                break
            train_arr[filled : filled + available] = mmap[:available]
            filled += available
            del mmap
            if filled >= train_count:
                break
        if normalize:
            _normalize_vectors(train_arr)
        index.train(train_arr)

    for shard_id in sorted(shard_ids):
        shard_path = out_dir / f"vectors_shard_{shard_id}.mmap"
        count = shard_counts[shard_id]
        mmap = np.memmap(shard_path, dtype="float32", mode="r", shape=(shard_size, dim))
        for start in range(0, count, block_size):
            end = min(start + block_size, count)
            block = np.array(mmap[start:end], dtype="float32", copy=True)
            if normalize:
                _normalize_vectors(block)
            index.add(block)
        del mmap

    faiss.write_index(index, str(out_dir / "index.faiss"))
    meta = {
        "dim": dim,
        "total_vectors": total_vectors,
        "index_type": index_type,
        "nlist": nlist,
        "m": m,
        "nbits": nbits,
        "nprobe": nprobe,
        "normalize": normalize,
        "train_max": train_max,
        "block_size": block_size,
        "shard_size": shard_size,
    }
    (out_dir / "index_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
