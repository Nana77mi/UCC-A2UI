from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .excel_loader import ComponentRecord, ParamRecord
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
    strict_params: List[ParamRecord]


@dataclass
class LibraryWhitelist:
    components: Dict[str, ComponentWhitelist]
    theme_tokens: Dict[str, str]


def build_whitelist(
    components: List[ComponentRecord] | List[JSONComponentRecord],
    params: List[ParamRecord] | List[JSONParamRecord],
) -> LibraryWhitelist:
    param_map: Dict[str, List[ParamRecord]] = {}
    for param in params:
        if not param.component_type:
            continue
        param_map.setdefault(param.component_type, []).append(param)

    theme_tokens: Dict[str, str] = {}
    whitelist: Dict[str, ComponentWhitelist] = {}
    for component in components:
        if not component.component_type:
            continue
        theme_tokens.update(component.theme_tokens)
        whitelist[component.component_type] = ComponentWhitelist(
            component_type=component.component_type,
            name_cn=component.name_cn,
            name_en=component.name_en,
            key_params=component.key_params,
            strict_params=param_map.get(component.component_type, []),
        )
    return LibraryWhitelist(components=whitelist, theme_tokens=theme_tokens)
