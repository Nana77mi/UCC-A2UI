from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .excel_loader import ComponentRecord, ParamRecord, load_component_library, load_params_library
from .json_loader import (
    JSONComponentRecord,
    JSONParamRecord,
    load_component_library_json,
    load_params_library_json,
)


@dataclass
class LibrarySourceConfig:
    component_path: str
    params_path: str
    source_format: str


def _cast_components(records: List[JSONComponentRecord]) -> List[ComponentRecord]:
    return [
        ComponentRecord(
            group=item.group,
            name_cn=item.name_cn,
            name_en=item.name_en,
            component_type=item.component_type,
            key_params=item.key_params,
            theme_tokens=item.theme_tokens,
        )
        for item in records
    ]


def _cast_params(records: List[JSONParamRecord]) -> List[ParamRecord]:
    return [
        ParamRecord(
            component_type=item.component_type,
            param_category=item.param_category,
            param_name=item.param_name,
            value_type=item.value_type,
            enum_values=item.enum_values,
            default_value=item.default_value,
            required=item.required,
            notes=item.notes,
        )
        for item in records
    ]


def load_library_sources(config: LibrarySourceConfig) -> Tuple[List[ComponentRecord], List[ParamRecord]]:
    source = config.source_format.lower()
    if source == "json":
        components = load_component_library_json(Path(config.component_path))
        params = load_params_library_json(Path(config.params_path))
        return _cast_components(components), _cast_params(params)
    components = load_component_library(Path(config.component_path))
    params = load_params_library(Path(config.params_path))
    return components, params
