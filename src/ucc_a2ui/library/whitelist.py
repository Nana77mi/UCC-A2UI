from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .json_loader import JSONComponentRecord, JSONParamRecord

EVENT_WHITELIST = [
    "onClick",
    "onLongPress",
    "onChange",
    "onFocus",
    "onBlur",
    "onEnter",
    "onOpen",
    "onClose",
    "onTick",
    "onComplete",
    "onRowClick",
    "onSelectChange",
    "onLoad",
    "onError",
]


@dataclass
class ComponentWhitelist:
    component_type: str
    name_cn: str
    name_en: str
    key_params: List[str]
    strict_params: List[JSONParamRecord]


@dataclass
class LibraryWhitelist:
    components: Dict[str, ComponentWhitelist]
    theme_tokens: Dict[str, str]


def _collect_params(component: JSONComponentRecord) -> List[JSONParamRecord]:
    params: List[JSONParamRecord] = []
    for items in component.props_by_category.values():
        params.extend(items)
    return params


def build_whitelist(components: List[JSONComponentRecord]) -> LibraryWhitelist:
    whitelist: Dict[str, ComponentWhitelist] = {}
    for component in components:
        if not component.component_type:
            continue
        params = _collect_params(component)
        key_params = [param.name for param in params if param.name]
        whitelist[component.component_type] = ComponentWhitelist(
            component_type=component.component_type,
            name_cn=component.component_name,
            name_en=component.component_name,
            key_params=key_params,
            strict_params=params,
        )
    return LibraryWhitelist(components=whitelist, theme_tokens={})
