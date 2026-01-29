from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterator

import numpy as np

from .config import Config
from .docs import generate_docs
from .embed import build_embedder
from .embed.chunker import chunk_text
from .embed.index_faiss import (
    IndexedChunk,
    add_vectors,
    create_empty_index,
    load_faiss_index,
    save_faiss_index_parts,
)
from .embed.search import search_index
from .generator import generate_ui, validate_ir
from .library import build_whitelist, export_library, load_component_schema_json

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


def _load_whitelist(config: Config):
    component_path = config.get("library", "component_path")
    if not component_path:
        raise ValueError("library.component_path is required for JSON schema input.")
    components, _ = load_component_schema_json(component_path)
    return build_whitelist(components)


def _run_sync(config: Config) -> int:
    print("[sync] loading library and exporting whitelist")
    whitelist = _load_whitelist(config)
    output_path = config.get("library", "output_path", default="library.json")
    export_library(output_path, whitelist)

    print("[sync] generating docs")
    docs_dir = config.get("docs", "output_dir", default="docs/components")
    docs = generate_docs(docs_dir, whitelist)

    embed_config = config.get_resolved("embed", default={})
    embedder = build_embedder(embed_config)
    embed_mode = str(embed_config.get("mode", "mock"))
    embed_base_url = str(embed_config.get("base_url", ""))
    embed_model = str(embed_config.get("model", ""))
    if embed_mode == "openai_compatible" and embed_base_url.startswith("http://localhost:11434"):
        if "bge-m3" in embed_model:
            print(
                "[sync] warning: local Ollama embedding model 'bge-m3' is large and may OOM; "
                "consider a smaller embedding model or a remote embedding service."
            )

    print("[sync] chunking docs")
    doc_sources = [str(doc) for doc in docs]
    chunk_size = int(embed_config.get("chunk_size", 800))
    chunk_overlap = int(embed_config.get("chunk_overlap", 120))
    batch_size = int(embed_config.get("batch_size", 64))
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    index_path = Path(index_dir) / "index.faiss"
    meta_path = Path(index_dir) / "meta.json"

    doc_hashes = {}
    for source in doc_sources:
        text = Path(source).read_text(encoding="utf-8")
        doc_hashes[source] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    existing_chunks: list[IndexedChunk] = []
    existing_doc_hashes: dict[str, str] = {}
    existing_index = None
    if index_path.exists() and meta_path.exists():
        faiss_index = load_faiss_index(index_dir)
        existing_index = faiss_index.index
        existing_chunks = faiss_index.chunks
        for chunk in existing_chunks:
            if chunk.doc_hash:
                existing_doc_hashes[chunk.source] = chunk.doc_hash

    current_sources = set(doc_hashes.keys())
    existing_sources = set(existing_doc_hashes.keys())
    removed_sources = existing_sources - current_sources
    changed_sources = {
        source for source in current_sources if existing_doc_hashes.get(source) not in (None, doc_hashes[source])
    }
    new_sources = current_sources - existing_sources
    print(
        "[sync] diff status:",
        f"new={len(new_sources)}",
        f"changed={len(changed_sources)}",
        f"removed={len(removed_sources)}",
    )

    def build_chunks_stream(
        target_sources: set[str],
        chunk_size: int,
        chunk_overlap: int,
        batch_size: int,
    ) -> Iterator[list[IndexedChunk]]:
        batch: list[IndexedChunk] = []
        for source in target_sources:
            text = Path(source).read_text(encoding="utf-8")
            doc_hash = doc_hashes[source]
            for chunk in chunk_text(text, chunk_size, chunk_overlap):
                chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                batch.append(
                    IndexedChunk(text=chunk, source=source, doc_hash=doc_hash, chunk_hash=chunk_hash)
                )
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
        if batch:
            yield batch

    def _format_rss_mb() -> str:
        if psutil is None:
            return "rss=unavailable"
        rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        return f"rss={rss_mb:.1f}MB"

    indexed_chunks: list[IndexedChunk] = []
    index = None
    index_status = "rebuilt"

    if removed_sources or changed_sources:
        print("[sync] rebuilding full index")
        # Releasing vectors alone isn't enough; streaming chunks avoids full-text accumulation.
        # Tune batch_size/chunk_size/chunk_overlap in config to further reduce peak memory.
        total_vectors = 0
        batch_num = 0
        for batch in build_chunks_stream(current_sources, chunk_size, chunk_overlap, batch_size):
            batch_num += 1
            indexed_chunks.extend(batch)
            texts = [chunk.text for chunk in batch]
            vectors = np.asarray(embedder.embed(texts).vectors, dtype="float32")
            if index is None:
                dim = int(vectors.shape[1]) if vectors.ndim > 1 else len(vectors[0])
                index = create_empty_index(dim)
            add_vectors(index, vectors)
            total_vectors += len(batch)
            print(
                "[sync] embedding batch",
                f"#{batch_num}",
                f"size={len(batch)}",
                f"total_vectors={total_vectors}",
                _format_rss_mb(),
            )
            del vectors
            del texts
            del batch
            gc.collect()
    elif new_sources:
        print("[sync] appending new docs to index")
        indexed_chunks = existing_chunks
        if existing_chunks:
            index = existing_index
        total_vectors = len(existing_chunks)
        batch_num = 0
        for batch in build_chunks_stream(new_sources, chunk_size, chunk_overlap, batch_size):
            batch_num += 1
            indexed_chunks.extend(batch)
            texts = [chunk.text for chunk in batch]
            vectors = np.asarray(embedder.embed(texts).vectors, dtype="float32")
            if index is None:
                dim = int(vectors.shape[1]) if vectors.ndim > 1 else len(vectors[0])
                index = create_empty_index(dim)
            add_vectors(index, vectors)
            total_vectors += len(batch)
            print(
                "[sync] embedding batch",
                f"#{batch_num}",
                f"size={len(batch)}",
                f"total_vectors={total_vectors}",
                _format_rss_mb(),
            )
            del vectors
            del texts
            del batch
            gc.collect()
        index_status = "appended"
    else:
        print("[sync] no doc changes detected; index unchanged")
        indexed_chunks = existing_chunks
        index_status = "unchanged"
        index = existing_index

    if index is None:
        raise ValueError("No chunks to index")
    save_faiss_index_parts(index_dir, index, indexed_chunks)
    print("[sync] index saved")

    summary = {
        "components": len(whitelist.components),
        "docs": len(docs),
        "chunks": len(indexed_chunks),
        "index_dir": index_dir,
        "index_status": index_status,
        "changed_components": len(changed_sources),
        "new_components": len(new_sources),
        "removed_components": len(removed_sources),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _run_generate(args: argparse.Namespace, config: Config) -> int:
    whitelist = _load_whitelist(config)
    out_dir = args.out or config.get("output", "dir", default="out")
    _, report = generate_ui(
        args.prompt,
        config=config,
        whitelist=whitelist,
        out_dir=out_dir,
        print_messages=args.print_messages,
        save_plan=args.save_plan,
    )
    return 0 if report.get("SchemaPass") and not report.get("errors") else 2


def _run_validate(args: argparse.Namespace, config: Config) -> int:
    whitelist = _load_whitelist(config)
    ir = json.loads(Path(args.input).read_text(encoding="utf-8"))
    strict = bool(config.get("library", "strict_params", default=False))
    report = validate_ir(ir, whitelist, strict=strict)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("SchemaPass") and not report.get("errors") else 2


def _run_search(args: argparse.Namespace, config: Config) -> int:
    embed_config = config.get_resolved("embed", default={})
    embedder = build_embedder(embed_config)
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    results = search_index(index_dir, args.query, embedder, top_k=args.k)
    payload = [result.__dict__ for result in results]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _add_shared_config_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(prog="ucc-a2ui")
    _add_shared_config_flag(parser)

    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    _add_shared_config_flag(sync_parser)

    gen_parser = subparsers.add_parser("generate")
    _add_shared_config_flag(gen_parser)
    gen_parser.add_argument("--prompt", required=True)
    gen_parser.add_argument("--out")
    gen_parser.add_argument("--print-messages", action="store_true")
    gen_parser.add_argument("--save-plan", action="store_true")

    val_parser = subparsers.add_parser("validate")
    _add_shared_config_flag(val_parser)
    val_parser.add_argument("--in", dest="input", required=True)

    search_parser = subparsers.add_parser("search")
    _add_shared_config_flag(search_parser)
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--k", type=int, default=5)

    args = parser.parse_args()
    config = Config.load(args.config)

    if args.command == "sync":
        sys.exit(_run_sync(config))
    if args.command == "generate":
        sys.exit(_run_generate(args, config))
    if args.command == "validate":
        sys.exit(_run_validate(args, config))
    if args.command == "search":
        sys.exit(_run_search(args, config))


if __name__ == "__main__":
    main()
