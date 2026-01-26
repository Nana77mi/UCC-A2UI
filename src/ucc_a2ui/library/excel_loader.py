from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from .normalize import normalize_component_name


@dataclass
class ComponentRecord:
    group: str
    name_cn: str
    name_en: str
    component_type: str
    key_params: List[str]
    theme_tokens: Dict[str, str]


@dataclass
class ParamRecord:
    component_type: str
    param_category: str
    param_name: str
    value_type: str
    enum_values: str
    default_value: str
    required: str
    notes: str


def _split_params(raw: str) -> List[str]:
    if not raw or not isinstance(raw, str):
        return []
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def _parse_theme_tokens(raw: str) -> Dict[str, str]:
    if not raw or not isinstance(raw, str):
        return {}
    tokens: Dict[str, str] = {}
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            tokens[key.strip()] = value.strip()
    return tokens


def load_component_library(path: str | Path) -> List[ComponentRecord]:
    df = pd.read_excel(path)
    records: List[ComponentRecord] = []
    for _, row in df.iterrows():
        group = str(row.get("ComponentGroup", ""))
        name_cn = str(row.get("ComponentName_CN", ""))
        name_en = str(row.get("ComponentName_EN", ""))
        key_params_raw = row.get("KeyParams", "")
        theme_raw = row.get("MaterialLike_DefaultColors", "")
        component_type = normalize_component_name(name_en)
        records.append(
            ComponentRecord(
                group=group,
                name_cn=name_cn,
                name_en=name_en,
                component_type=component_type,
                key_params=_split_params(str(key_params_raw)),
                theme_tokens=_parse_theme_tokens(str(theme_raw)),
            )
        )
    return records


def _column_lookup(columns: Iterable[str], candidates: List[str]) -> str | None:
    lowered = {col.lower(): col for col in columns}
    for name in candidates:
        key = name.lower()
        if key in lowered:
            return lowered[key]
    return None


def load_params_library(path: str | Path) -> List[ParamRecord]:
    df = pd.read_excel(path)
    columns = list(df.columns)
    col_component = _column_lookup(columns, ["ComponentName", "ComponentName_EN", "Component", "ComponentName/Param"])
    col_group = _column_lookup(columns, ["ComponentGroup", "ComponentGroup/ComponentName"])
    col_category = _column_lookup(columns, ["ParamCategory", "Category"])
    col_name = _column_lookup(columns, ["ParamName", "Name"])
    col_value = _column_lookup(columns, ["ValueType", "Type"])
    col_enum = _column_lookup(columns, ["EnumValues", "Enum", "Values"])
    col_default = _column_lookup(columns, ["DefaultValue", "Default"])
    col_required = _column_lookup(columns, ["Required", "IsRequired"])
    col_notes = _column_lookup(columns, ["Notes", "Description", "Note"])

    records: List[ParamRecord] = []
    for _, row in df.iterrows():
        component_name = str(row.get(col_component or "", ""))
        group_name = str(row.get(col_group or "", ""))
        component_raw = component_name or group_name
        component_type = normalize_component_name(component_raw)
        records.append(
            ParamRecord(
                component_type=component_type,
                param_category=str(row.get(col_category or "", "")),
                param_name=str(row.get(col_name or "", "")),
                value_type=str(row.get(col_value or "", "")),
                enum_values=str(row.get(col_enum or "", "")),
                default_value=str(row.get(col_default or "", "")),
                required=str(row.get(col_required or "", "")),
                notes=str(row.get(col_notes or "", "")),
            )
        )
    return records
