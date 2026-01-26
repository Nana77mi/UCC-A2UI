from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from ucc_a2ui.generator.validator import validate_ir
from ucc_a2ui.library import build_whitelist, load_component_library, load_params_library


def _write_excel(component_path: Path, params_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "components"
    ws.append(
        [
            "ComponentGroup",
            "ComponentName_CN",
            "ComponentName_EN",
            "KeyParams",
            "MaterialLike_DefaultColors",
        ]
    )
    ws.append(["基础", "按钮", "Button", "text,color", "primary=#111111"])
    wb.save(component_path)

    wb = Workbook()
    ws = wb.active
    ws.title = "params"
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
    ws.append(["基础", "Button", "Style", "text", "string", "", "", "yes", ""])
    ws.append(["基础", "Button", "Style", "color", "string", "", "", "no", ""])
    wb.save(params_path)


def _load_whitelist(tmp_path: Path):
    component_path = tmp_path / "components.xlsx"
    params_path = tmp_path / "params.xlsx"
    _write_excel(component_path, params_path)
    components = load_component_library(component_path)
    params = load_params_library(params_path)
    return build_whitelist(components, params)


def test_validator_schema_pass(tmp_path: Path) -> None:
    whitelist = _load_whitelist(tmp_path)
    ir = {
        "version": "ucc-ui-ir@v0",
        "theme": {},
        "variables": [{"name": "title"}],
        "tree": {
            "type": "button",
            "props": {"text": "hi"},
            "events": {},
            "children": [],
        },
    }
    report = validate_ir(ir, whitelist, strict=False)
    assert report["SchemaPass"]
    assert not report["errors"]


def test_validator_unknown_component(tmp_path: Path) -> None:
    whitelist = _load_whitelist(tmp_path)
    ir = {
        "version": "ucc-ui-ir@v0",
        "theme": {},
        "variables": [],
        "tree": {"type": "unknown", "props": {}, "events": {}, "children": []},
    }
    report = validate_ir(ir, whitelist, strict=False)
    assert not report["ComponentWhitelistPass"]


def test_validator_unknown_prop(tmp_path: Path) -> None:
    whitelist = _load_whitelist(tmp_path)
    ir = {
        "version": "ucc-ui-ir@v0",
        "theme": {},
        "variables": [],
        "tree": {"type": "button", "props": {"bad": 1}, "events": {}, "children": []},
    }
    report = validate_ir(ir, whitelist, strict=False)
    assert not report["PropsWhitelistPass"]


def test_validator_unknown_event(tmp_path: Path) -> None:
    whitelist = _load_whitelist(tmp_path)
    ir = {
        "version": "ucc-ui-ir@v0",
        "theme": {},
        "variables": [],
        "tree": {"type": "button", "props": {}, "events": {"onTap": "x"}, "children": []},
    }
    report = validate_ir(ir, whitelist, strict=False)
    assert not report["EventsWhitelistPass"]


def test_validator_binding_sanity(tmp_path: Path) -> None:
    whitelist = _load_whitelist(tmp_path)
    ir = {
        "version": "ucc-ui-ir@v0",
        "theme": {},
        "variables": [],
        "tree": {"type": "button", "props": {"textBinding": "@missing"}, "events": {}, "children": []},
    }
    report = validate_ir(ir, whitelist, strict=False)
    assert not report["BindingSanity"]
