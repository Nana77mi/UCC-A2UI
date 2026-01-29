from __future__ import annotations

import json
from typing import List

from ..library.whitelist import LibraryWhitelist
from .llm_client_base import LLMClientBase, LLMResponse


class MockLLM(LLMClientBase):
    def __init__(self, whitelist: LibraryWhitelist) -> None:
        self.whitelist = whitelist

    def complete(self, messages: List[dict]) -> LLMResponse:
        component = next(iter(self.whitelist.components.values()))
        sample_prop = component.key_params[0] if component.key_params else None
        plan = {
            "intent": "生成一个基础页面",
            "widgets": [component.component_type],
            "bindings": [],
            "events": [],
            "layout": "vertical",
        }
        ir = {
            "version": "ucc-ui-ir@v0",
            "theme": {},
            "variables": [],
            "tree": {
                "type": component.component_type,
                "props": {sample_prop: "示例"} if sample_prop else {},
                "events": {},
                "children": [],
            },
        }
        content = json.dumps({"plan": plan, "ir": ir}, ensure_ascii=False, indent=2)
        return LLMResponse(content=content)
