from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .docs import generate_docs
from .embed import build_embedder
from .embed.chunker import chunk_documents_with_sources
from .embed.index_faiss import IndexedChunk, add_vectors, create_empty_index, save_faiss_index_parts
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
    whitelist = _load_whitelist(config)
    output_path = config.get("library", "output_path", default="library.json")
    export_library(output_path, whitelist)

    docs_dir = config.get("docs", "output_dir", default="docs/components")
    docs = generate_docs(docs_dir, whitelist)

    embed_config = config.get_resolved("embed", default={})
    embedder = build_embedder(embed_config)

    documents = [(Path(doc).read_text(encoding="utf-8"), str(doc)) for doc in docs]
    chunk_pairs = chunk_documents_with_sources(
        documents,
        chunk_size=int(embed_config.get("chunk_size", 800)),
        chunk_overlap=int(embed_config.get("chunk_overlap", 120)),
    )
    batch_size = int(embed_config.get("batch_size", 64))
    indexed_chunks: list[IndexedChunk] = []
    index = None
    for start in range(0, len(chunk_pairs), batch_size):
        batch = chunk_pairs[start : start + batch_size]
        chunks = [chunk for chunk, _ in batch]
        vectors = embedder.embed(chunks).vectors
        if index is None:
            index = create_empty_index(len(vectors[0]))
        add_vectors(index, vectors)
        indexed_chunks.extend(IndexedChunk(text=chunk, source=source) for chunk, source in batch)
    if index is None:
        raise ValueError("No chunks to index")
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    save_faiss_index_parts(index_dir, index, indexed_chunks)

    summary = {
        "components": len(whitelist.components),
        "docs": len(docs),
        "chunks": len(indexed_chunks),
        "index_dir": index_dir,
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
