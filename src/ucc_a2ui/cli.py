from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .docs import generate_docs
from .embed import build_embedder
from .embed.chunker import chunk_documents_with_sources
from .embed.index_faiss import IndexedChunk, build_faiss_index, save_faiss_index
from .embed.search import search_index
from .generator import generate_ui, validate_ir
from .library import LibrarySourceConfig, build_whitelist, export_library, load_library_sources


def _load_whitelist(config: Config):
    source_format = config.get("library", "source_format", default="json")
    component_path = config.get("library", "component_path")
    params_path = config.get("library", "params_path")
    if not component_path or not params_path:
        component_path = config.get("library", "excel_component_path")
        params_path = config.get("library", "excel_params_path")
        source_format = "excel"

    sources = LibrarySourceConfig(
        component_path=component_path,
        params_path=params_path,
        source_format=source_format,
    )
    components, params = load_library_sources(sources)
    return build_whitelist(components, params)


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
    chunks = [chunk for chunk, _ in chunk_pairs]
    vectors = embedder.embed(chunks).vectors
    indexed_chunks = [IndexedChunk(text=chunk, source=source) for chunk, source in chunk_pairs]
    faiss_index = build_faiss_index(vectors, indexed_chunks)
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    save_faiss_index(index_dir, faiss_index)

    summary = {
        "components": len(whitelist.components),
        "docs": len(docs),
        "chunks": len(chunks),
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="ucc-a2ui")
    parser.add_argument("--config", default="config.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync")

    gen_parser = subparsers.add_parser("generate")
    gen_parser.add_argument("--prompt", required=True)
    gen_parser.add_argument("--out")
    gen_parser.add_argument("--print-messages", action="store_true")
    gen_parser.add_argument("--save-plan", action="store_true")

    val_parser = subparsers.add_parser("validate")
    val_parser.add_argument("--in", dest="input", required=True)

    search_parser = subparsers.add_parser("search")
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
