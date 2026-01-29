from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

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

    print("[sync] chunking docs")
    documents = [(Path(doc).read_text(encoding="utf-8"), str(doc)) for doc in docs]
    chunk_size = int(embed_config.get("chunk_size", 800))
    chunk_overlap = int(embed_config.get("chunk_overlap", 120))
    batch_size = int(embed_config.get("batch_size", 64))
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    index_path = Path(index_dir) / "index.faiss"
    meta_path = Path(index_dir) / "meta.json"

    doc_hashes = {
        source: hashlib.sha256(text.encode("utf-8")).hexdigest() for text, source in documents
    }

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

    def build_chunks(target_sources: set[str]) -> list[IndexedChunk]:
        chunks: list[IndexedChunk] = []
        for text, source in documents:
            if source not in target_sources:
                continue
            doc_hash = doc_hashes[source]
            for chunk in chunk_text(text, chunk_size, chunk_overlap):
                chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                chunks.append(
                    IndexedChunk(text=chunk, source=source, doc_hash=doc_hash, chunk_hash=chunk_hash)
                )
        return chunks

    indexed_chunks: list[IndexedChunk] = []
    index = None
    index_status = "rebuilt"

    if removed_sources or changed_sources:
        print("[sync] rebuilding full index")
        indexed_chunks = build_chunks(current_sources)
        for start in range(0, len(indexed_chunks), batch_size):
            batch = indexed_chunks[start : start + batch_size]
            print(f"[sync] embedding batch {start + 1}-{start + len(batch)} / {len(indexed_chunks)}")
            vectors = embedder.embed([chunk.text for chunk in batch]).vectors
            if index is None:
                index = create_empty_index(len(vectors[0]))
            add_vectors(index, vectors)
    elif new_sources:
        print("[sync] appending new docs to index")
        indexed_chunks = existing_chunks + build_chunks(new_sources)
        if existing_chunks:
            index = existing_index
        for start in range(len(existing_chunks), len(indexed_chunks), batch_size):
            batch = indexed_chunks[start : start + batch_size]
            print(f"[sync] embedding batch {start + 1}-{start + len(batch)} / {len(indexed_chunks)}")
            vectors = embedder.embed([chunk.text for chunk in batch]).vectors
            if index is None:
                index = create_empty_index(len(vectors[0]))
            add_vectors(index, vectors)
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
