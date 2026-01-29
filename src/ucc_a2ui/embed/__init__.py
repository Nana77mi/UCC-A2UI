from __future__ import annotations

from typing import Any, Dict

from .embedder_base import EmbedderBase, EmbeddingResult
from .embedder_dashscope_qwen import DashScopeQwenEmbedder
from .embedder_mock import MockEmbedder
from .embedder_openai_compat import OpenAICompatibleEmbedder


class FallbackEmbedder(EmbedderBase):
    def __init__(self, primary: EmbedderBase, fallback: EmbedderBase, allow_fallback: bool) -> None:
        self.primary = primary
        self.fallback = fallback
        self.allow_fallback = allow_fallback

    def embed(self, texts: list[str]) -> EmbeddingResult:
        try:
            return self.primary.embed(texts)
        except Exception:
            if not self.allow_fallback:
                raise
            return self.fallback.embed(texts)


def build_embedder(config: Dict[str, Any]) -> EmbedderBase:
    mode = config.get("mode", "mock")
    allow_fallback = bool(config.get("allow_fallback", False))
    if mode == "openai_compatible":
        primary = OpenAICompatibleEmbedder(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
        if allow_fallback:
            return FallbackEmbedder(primary, MockEmbedder(), allow_fallback=True)
        return primary
    if mode == "dashscope_qwen":
        api_key = config.get("api_key", "")
        if not api_key:
            return MockEmbedder()
        primary = DashScopeQwenEmbedder(api_key=api_key, model=config.get("model", ""))
        if allow_fallback:
            return FallbackEmbedder(primary, MockEmbedder(), allow_fallback=True)
        return primary
    return MockEmbedder()

__all__ = [
    "build_embedder",
    "EmbedderBase",
    "OpenAICompatibleEmbedder",
    "DashScopeQwenEmbedder",
    "MockEmbedder",
    "FallbackEmbedder",
]
