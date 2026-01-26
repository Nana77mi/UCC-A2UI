from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from ucc_a2ui.config import Config
from ucc_a2ui.generator import generate_ui
from ucc_a2ui.library import build_whitelist, load_component_library, load_params_library


def _write_excel(component_path: Path, params_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ComponentGroup",
            "ComponentName_CN",
            "ComponentName_EN",
            "KeyParams",
            "MaterialLike_DefaultColors",
        ]
    )
    ws.append(["基础", "文本", "Text", "text", "primary=#222222"])
    wb.save(component_path)

    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "ComponentGroup",
            "ComponentName",
            "ParamCategory",
            "ParamName",
            "ValueType",
            "EnumValues",
            "DefaultValue",
            "Required",
            "Notes",
        ]
    )
    ws.append(["基础", "Text", "Data", "text", "string", "", "", "yes", ""])
    wb.save(params_path)


def test_generate_mock(tmp_path: Path) -> None:
    component_path = tmp_path / "components.xlsx"
    params_path = tmp_path / "params.xlsx"
    _write_excel(component_path, params_path)

    components = load_component_library(component_path)
    params = load_params_library(params_path)
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
