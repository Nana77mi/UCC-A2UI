from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict

from .theme import merge_theme_tokens
from .whitelist import LibraryWhitelist


def export_library(path: str | Path, whitelist: LibraryWhitelist) -> Dict:
    data = {
        "version": "ucc-library@v0",
        "components": {
            key: {
                "type": value.component_type,
                "name_cn": value.name_cn,
                "name_en": value.name_en,
                "key_params": value.key_params,
                "strict_params": [asdict(param) for param in value.strict_params],
            }
            for key, value in whitelist.components.items()
        },
        "theme_tokens": merge_theme_tokens(whitelist.theme_tokens),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
