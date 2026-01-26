from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.config import Config
from ucc_a2ui.generator import generate_ui
from ucc_a2ui.library import LibrarySourceConfig, build_whitelist, load_library_sources


def _write_json(component_path: Path, params_path: Path) -> None:
    component_path.write_text(
        """
{
  "components": [
    {
      "ComponentGroup": "基础",
      "ComponentName_CN": "文本",
      "ComponentName_EN": "Text",
      "KeyParams": ["text"],
      "MaterialLike_DefaultColors": "primary=#222222"
    }
  ]
}
""",
        encoding="utf-8",
    )
    params_path.write_text(
        """
{
  "params": [
    {
      "ComponentName": "Text",
      "ParamCategory": "Data",
      "ParamName": "text",
      "ValueType": "string",
      "EnumValues": "",
      "DefaultValue": "",
      "Required": "yes",
      "Notes": ""
    }
  ]
}
""",
        encoding="utf-8",
    )


def test_generate_mock(tmp_path: Path) -> None:
    component_path = tmp_path / "components.json"
    params_path = tmp_path / "params.json"
    _write_json(component_path, params_path)

    sources = LibrarySourceConfig(
        component_path=str(component_path),
        params_path=str(params_path),
        source_format="json",
    )
    components, params = load_library_sources(sources)
    whitelist = build_whitelist(components, params)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
llm:\n  mode: mock\noutput:\n  dir: out\n""",
        encoding="utf-8",
    )
    config = Config.load(config_path)

    out_dir = tmp_path / "out"
    ir, report = generate_ui("生成文本页面", config, whitelist, out_dir)
    assert report["SchemaPass"]
    assert (out_dir / "ui_ir.json").exists()
    saved = json.loads((out_dir / "ui_ir.json").read_text(encoding="utf-8"))
    assert saved["version"] == "ucc-ui-ir@v0"
