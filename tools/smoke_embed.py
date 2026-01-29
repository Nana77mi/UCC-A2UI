from __future__ import annotations

import argparse
import os
import importlib.util
import sys
from pathlib import Path
from typing import Iterator, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ucc_a2ui.embeddings import build_embedding_client

psutil = None
if importlib.util.find_spec("psutil") is not None:  # pragma: no cover - optional dependency
    import psutil as _psutil

    psutil = _psutil


def _iter_batches(items: List[str], batch_size: int) -> Iterator[List[str]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _format_rss_mb() -> str:
    if psutil is None:
        return "rss_mb=unavailable"
    rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    return f"rss_mb={rss_mb:.1f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--model", default=os.getenv("EMBED_MODEL", "mock-embedding"))
    parser.add_argument("--base-url", default=os.getenv("EMBED_BASE_URL", "http://localhost:11434"))
    parser.add_argument("--api-key", default=os.getenv("EMBED_API_KEY", ""))
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    texts = [f"smoke-text-{idx:04d}" for idx in range(args.count)]
    cfg = {
        "backend": args.backend,
        "batch_size": args.batch_size,
        "mock_dim": args.dim,
        "model": args.model,
        "base_url": args.base_url,
        "api_key": args.api_key,
        "timeout": args.timeout,
        "allow_fallback": True,
        "retries": 2,
    }
    client = build_embedding_client(cfg)

    dim = None
    for batch_id, batch in enumerate(_iter_batches(texts, args.batch_size), start=1):
        vectors = client.embed_texts(batch)
        dim = int(vectors.shape[1]) if vectors.ndim > 1 else 0
        print(
            f"batch_id={batch_id}",
            f"vectors.shape={vectors.shape}",
            f"dim={dim}",
            _format_rss_mb(),
        )
        del vectors
        del batch
    if dim is None:
        raise RuntimeError("No embeddings generated")
    if not isinstance(client.dim, int):
        raise RuntimeError("Embedding client did not set dim")
    if client.dim != dim:
        raise RuntimeError(f"Embedding dim mismatch: {client.dim} != {dim}")
    if not isinstance(client, object):
        raise RuntimeError("Smoke test failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
