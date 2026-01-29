from __future__ import annotations

import json
from pathlib import Path

import faiss

from ucc_a2ui.embed import MockEmbedder
from ucc_a2ui.pipeline_embed_disk import build_index_from_disk, embed_to_disk


def main() -> None:
    out_dir = Path("tmp/smoke_embed")
    out_dir.mkdir(parents=True, exist_ok=True)
    source_path = out_dir / "sources.jsonl"
    total_docs = 200_000
    with source_path.open("w", encoding="utf-8") as handle:
        for idx in range(total_docs):
            payload = {"text": f"smoke text {idx % 1000}", "source": "smoke"}
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    embedder = MockEmbedder(dim=64)
    manifest = embed_to_disk(
        [str(source_path)],
        embedder,
        out_dir,
        chunk_size=64,
        chunk_overlap=0,
        batch_size=64,
        shard_size=50_000,
        max_rss_mb=800,
    )

    shard_files = sorted(out_dir.glob("vectors_shard_*.mmap"))
    chunks_path = out_dir / "chunks.jsonl"
    line_count = 0
    with chunks_path.open("r", encoding="utf-8") as handle:
        for _ in handle:
            line_count += 1
    if line_count != manifest.total_vectors:
        raise RuntimeError(
            f"chunks.jsonl lines ({line_count}) != total_vectors ({manifest.total_vectors})"
        )
    expected_shards = (line_count + manifest.shard_size - 1) // manifest.shard_size
    if len(shard_files) != expected_shards:
        raise RuntimeError(
            f"shard count mismatch: got {len(shard_files)}, expected {expected_shards}"
        )
    print(
        f"[smoke] shards={len(shard_files)} chunks={line_count} shard_size={manifest.shard_size}"
    )

    build_index_from_disk(
        out_dir,
        index_type="ivfpq",
        nlist=64,
        m=8,
        nbits=8,
        nprobe=16,
        train_max=20000,
        block_size=8192,
        normalize=True,
        shard_size=manifest.shard_size,
    )

    index = faiss.read_index(str(out_dir / "index.faiss"))
    print(f"[smoke] index.ntotal={index.ntotal} index.d={index.d} nprobe={index.nprobe}")


if __name__ == "__main__":
    main()
