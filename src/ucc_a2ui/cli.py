from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .docs import generate_docs
from .embed import build_embedder
from .embed.search import search_index
from .generator import generate_ui, validate_ir
from .library import build_whitelist, export_library, load_component_schema_json
from .pipeline_embed_disk import build_index_from_disk, embed_to_disk


def _load_whitelist(config: Config):
    component_path = config.get("library", "component_path")
    if not component_path:
        raise ValueError("library.component_path is required for JSON schema input.")
    components, _ = load_component_schema_json(component_path)
    return build_whitelist(components)


def _run_sync(config: Config) -> int:
    whitelist, docs = _prepare_docs(config)

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
    shard_size = int(embed_config.get("shard_size", 50_000))
    max_rss_mb = int(embed_config.get("max_rss_mb", 1500))
    embed_manifest = embed_to_disk(
        doc_sources,
        embedder,
        index_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        batch_size=batch_size,
        shard_size=shard_size,
        max_rss_mb=max_rss_mb,
    )

    print("[sync] embedding completed; building index")
    build_index_from_disk(
        index_dir,
        index_type=str(embed_config.get("index_type", "ivfpq")),
        nlist=int(embed_config.get("nlist", 4096)),
        m=int(embed_config.get("m", 48)),
        nbits=int(embed_config.get("nbits", 8)),
        nprobe=int(embed_config.get("nprobe", 32)),
        train_max=int(embed_config.get("train_max", 20000)),
        block_size=int(embed_config.get("block_size", 8192)),
        normalize=bool(embed_config.get("normalize", True)),
        shard_size=embed_manifest.shard_size,
    )
    print("[sync] index saved")

    summary = {
        "components": len(whitelist.components),
        "docs": len(docs),
        "chunks": embed_manifest.total_vectors,
        "index_dir": index_dir,
        "index_status": "rebuilt",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _prepare_docs(config: Config):
    print("[sync] loading library and exporting whitelist")
    whitelist = _load_whitelist(config)
    output_path = config.get("library", "output_path", default="library.json")
    export_library(output_path, whitelist)

    print("[sync] generating docs")
    docs_dir = config.get("docs", "output_dir", default="docs/components")
    docs = generate_docs(docs_dir, whitelist)
    return whitelist, docs


def _run_embed(config: Config) -> int:
    _, docs = _prepare_docs(config)
    embed_config = config.get_resolved("embed", default={})
    embedder = build_embedder(embed_config)
    doc_sources = [str(doc) for doc in docs]
    embed_to_disk(
        doc_sources,
        embedder,
        embed_config.get("index_dir", "index/ucc_docs"),
        chunk_size=int(embed_config.get("chunk_size", 800)),
        chunk_overlap=int(embed_config.get("chunk_overlap", 120)),
        batch_size=int(embed_config.get("batch_size", 64)),
        shard_size=int(embed_config.get("shard_size", 50_000)),
        max_rss_mb=int(embed_config.get("max_rss_mb", 1500)),
    )
    print("[embed] embedding completed")
    return 0


def _run_index(config: Config) -> int:
    embed_config = config.get_resolved("embed", default={})
    index_dir = embed_config.get("index_dir", "index/ucc_docs")
    build_index_from_disk(
        index_dir,
        index_type=str(embed_config.get("index_type", "ivfpq")),
        nlist=int(embed_config.get("nlist", 4096)),
        m=int(embed_config.get("m", 48)),
        nbits=int(embed_config.get("nbits", 8)),
        nprobe=int(embed_config.get("nprobe", 32)),
        train_max=int(embed_config.get("train_max", 20000)),
        block_size=int(embed_config.get("block_size", 8192)),
        normalize=bool(embed_config.get("normalize", True)),
        shard_size=int(embed_config.get("shard_size", 50_000)),
    )
    print("[index] index saved")
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
    embed_parser = subparsers.add_parser("embed")
    _add_shared_config_flag(embed_parser)
    index_parser = subparsers.add_parser("index")
    _add_shared_config_flag(index_parser)

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
    if args.command == "embed":
        sys.exit(_run_embed(config))
    if args.command == "index":
        sys.exit(_run_index(config))
    if args.command == "generate":
        sys.exit(_run_generate(args, config))
    if args.command == "validate":
        sys.exit(_run_validate(args, config))
    if args.command == "search":
        sys.exit(_run_search(args, config))


if __name__ == "__main__":
    main()
