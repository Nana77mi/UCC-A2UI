from __future__ import annotations

from pathlib import Path

from ucc_a2ui.generator.validator import validate_ir
from ucc_a2ui.library import build_whitelist, load_component_schema_json


def _write_json(component_path: Path) -> None:
    component_path.write_text(
        """
{
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
            "default": null,
            "required": true,
            "notes": ""
          }
        ],
        "Style": [
          {
            "name": "color",
            "type": "string",
            "enum": [],
            "description": "按钮颜色",
            "default": null,
            "required": false,
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


def _load_whitelist(tmp_path: Path):
    component_path = tmp_path / "schema.json"
    _write_json(component_path)
    components, _ = load_component_schema_json(component_path)
    return build_whitelist(components)


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
