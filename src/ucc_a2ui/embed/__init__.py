from __future__ import annotations

from typing import Any, Dict

from .embedder_base import EmbedderBase
from .embedder_dashscope_qwen import DashScopeQwenEmbedder
from .embedder_mock import MockEmbedder
from .embedder_openai_compat import OpenAICompatibleEmbedder


def build_embedder(config: Dict[str, Any]) -> EmbedderBase:
    mode = config.get("mode", "mock")
    if mode == "openai_compatible":
        return OpenAICompatibleEmbedder(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
    if mode == "dashscope_qwen":
        api_key = config.get("api_key", "")
        if not api_key:
            return MockEmbedder()
        return DashScopeQwenEmbedder(api_key=api_key, model=config.get("model", ""))
    return MockEmbedder()

__all__ = [
    "build_embedder",
    "EmbedderBase",
    "OpenAICompatibleEmbedder",
    "DashScopeQwenEmbedder",
    "MockEmbedder",
]
