from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from .normalize import normalize_component_name


@dataclass
class JSONComponentRecord:
    component_type: str
    group: str
    component_name: str
    props_by_category: Dict[str, List["JSONParamRecord"]]


@dataclass
class JSONParamRecord:
    name: str
    category: str
    value_type: str
    enum_values: List[str]
    description: str
    default_value: str | None
    required: bool
    notes: str


def _parse_param(param: dict, category: str) -> JSONParamRecord:
    return JSONParamRecord(
        name=str(param.get("name", "")),
        category=category,
        value_type=str(param.get("type", "")),
        enum_values=list(param.get("enum", []) or []),
        description=str(param.get("description", "")),
        default_value=param.get("default"),
        required=bool(param.get("required", False)),
        notes=str(param.get("notes", "")),
    )


def _parse_component(item: dict) -> JSONComponentRecord:
    props_by_category: Dict[str, List[JSONParamRecord]] = {}
    for category, props in (item.get("props_by_category") or {}).items():
        props_by_category[category] = [_parse_param(prop, category) for prop in props or []]
    component_type = normalize_component_name(item.get("type", ""))
    return JSONComponentRecord(
        component_type=component_type,
        group=str(item.get("group", "")),
        component_name=str(item.get("component_name", "")),
        props_by_category=props_by_category,
    )


def load_component_schema_json(path: str | Path) -> Tuple[List[JSONComponentRecord], Dict[str, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("components", []) if isinstance(data, dict) else data
    records = [_parse_component(item) for item in items or []]
    metadata = {
        "schema_version": str(data.get("schema_version", "")),
        "source_file": str(data.get("source", {}).get("file", "")),
        "source_sheet": str(data.get("source", {}).get("sheet", "")),
    }
    return records, metadata
