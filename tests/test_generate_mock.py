from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.config import Config
from ucc_a2ui.generator import generate_ui
from ucc_a2ui.library import build_whitelist, load_component_schema_json


def _write_json(component_path: Path) -> None:
    component_path.write_text(
        """
{
  "schema_version": "ucc-component-params@v0",
  "components": [
    {
      "type": "label",
      "group": "基础组件",
      "component_name": "Label",
      "props_by_category": {
        "Data": [
          {
            "name": "text",
            "type": "string",
            "enum": [],
            "description": "显示文本",
            "default": null,
            "required": true,
            "notes": ""
          }
        ]
      }
    }
  ]
}
""",
        encoding="utf-8",
    )


def test_generate_mock(tmp_path: Path) -> None:
    component_path = tmp_path / "schema.json"
    _write_json(component_path)

    components, _ = load_component_schema_json(component_path)
    whitelist = build_whitelist(components)

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
