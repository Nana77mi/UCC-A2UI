from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.library import LibrarySourceConfig, load_library_sources


def test_load_library_sources_json(tmp_path: Path) -> None:
    components = {
        "components": [
            {
                "ComponentGroup": "基础",
                "ComponentName_CN": "按钮",
                "ComponentName_EN": "Button",
                "KeyParams": ["text"],
                "MaterialLike_DefaultColors": "primary=#111111",
            }
        ]
    }
    params = {
        "params": [
            {
                "ComponentName": "Button",
                "ParamCategory": "Style",
                "ParamName": "text",
                "ValueType": "string",
                "EnumValues": "",
                "DefaultValue": "",
                "Required": "yes",
                "Notes": "",
            }
        ]
    }
    component_path = tmp_path / "components.json"
    params_path = tmp_path / "params.json"
    component_path.write_text(json.dumps(components, ensure_ascii=False), encoding="utf-8")
    params_path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")

    sources = LibrarySourceConfig(
        component_path=str(component_path),
        params_path=str(params_path),
        source_format="json",
    )
    comps, prs = load_library_sources(sources)

    assert comps[0].component_type == "button"
    assert prs[0].param_name == "text"
