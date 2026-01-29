from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


def _resolve_env(value: str) -> str:
    if isinstance(value, str) and value.startswith("ENV:"):
        env_key = value.split(":", 1)[1]
        return os.getenv(env_key, "")
    return value


@dataclass
class Config:
    data: Dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return cls(raw)

    def get(self, *keys: str, default: Any | None = None) -> Any:
        node: Any = self.data
        for key in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(key)
            if node is None:
                return default
        return node

    def get_resolved(self, *keys: str, default: Any | None = None) -> Any:
        value = self.get(*keys, default=default)
        if isinstance(value, dict):
            return {k: _resolve_env(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve_env(v) for v in value]
        return _resolve_env(value)
