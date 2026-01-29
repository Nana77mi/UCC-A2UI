from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.library import load_component_schema_json


def test_load_library_sources_json(tmp_path: Path) -> None:
    schema = {
        "schema_version": "ucc-component-params@v0",
        "components": [
            {
                "type": "button",
                "group": "基础组件",
                "component_name": "Button",
                "props_by_category": {
                    "Data": [
                        {
                            "name": "text",
                            "type": "string",
                            "enum": [],
                            "description": "按钮文本",
                            "default": None,
                            "required": True,
                            "notes": "",
                        }
                    ]
                },
            }
        ],
    }
    component_path = tmp_path / "schema.json"
    component_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

    components, _ = load_component_schema_json(component_path)
    assert components[0].component_type == "button"
    assert components[0].props_by_category["Data"][0].name == "text"
