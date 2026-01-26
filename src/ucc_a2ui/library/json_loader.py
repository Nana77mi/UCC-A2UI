from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .normalize import normalize_component_name


@dataclass
class JSONComponentRecord:
    group: str
    name_cn: str
    name_en: str
    component_type: str
    key_params: List[str]
    theme_tokens: Dict[str, str]


@dataclass
class JSONParamRecord:
    component_type: str
    param_category: str
    param_name: str
    value_type: str
    enum_values: str
    default_value: str
    required: str
    notes: str


def _parse_theme_tokens(raw: str) -> Dict[str, str]:
    if not raw or not isinstance(raw, str):
        return {}
    tokens: Dict[str, str] = {}
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            tokens[key.strip()] = value.strip()
    return tokens


def load_component_library_json(path: str | Path) -> List[JSONComponentRecord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("components", []) if isinstance(data, dict) else data
    records: List[JSONComponentRecord] = []
    for item in items or []:
        name_en = str(item.get("ComponentName_EN", item.get("name_en", "")))
        component_type = normalize_component_name(item.get("type") or name_en)
        records.append(
            JSONComponentRecord(
                group=str(item.get("ComponentGroup", item.get("group", ""))),
                name_cn=str(item.get("ComponentName_CN", item.get("name_cn", ""))),
                name_en=name_en,
                component_type=component_type,
                key_params=list(item.get("KeyParams", item.get("key_params", [])) or []),
                theme_tokens=_parse_theme_tokens(
                    str(item.get("MaterialLike_DefaultColors", item.get("theme_tokens", "")))
                ),
            )
        )
    return records


def load_params_library_json(path: str | Path) -> List[JSONParamRecord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("params", []) if isinstance(data, dict) else data
    records: List[JSONParamRecord] = []
    for item in items or []:
        component_raw = str(item.get("ComponentName", item.get("component", item.get("component_type", ""))))
        component_type = normalize_component_name(component_raw)
        records.append(
            JSONParamRecord(
                component_type=component_type,
                param_category=str(item.get("ParamCategory", item.get("param_category", ""))),
                param_name=str(item.get("ParamName", item.get("param_name", ""))),
                value_type=str(item.get("ValueType", item.get("value_type", ""))),
                enum_values=str(item.get("EnumValues", item.get("enum_values", ""))),
                default_value=str(item.get("DefaultValue", item.get("default_value", ""))),
                required=str(item.get("Required", item.get("required", ""))),
                notes=str(item.get("Notes", item.get("notes", ""))),
            )
        )
    return records
