from __future__ import annotations

from pathlib import Path

from ucc_a2ui.generator.validator import validate_ir
from ucc_a2ui.library import LibrarySourceConfig, build_whitelist, load_library_sources


def _write_json(component_path: Path, params_path: Path) -> None:
    component_path.write_text(
        """
{
  "components": [
    {
      "ComponentGroup": "基础",
      "ComponentName_CN": "按钮",
      "ComponentName_EN": "Button",
      "KeyParams": ["text", "color"],
      "MaterialLike_DefaultColors": "primary=#111111"
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
      "ComponentName": "Button",
      "ParamCategory": "Style",
      "ParamName": "text",
      "ValueType": "string",
      "EnumValues": "",
      "DefaultValue": "",
      "Required": "yes",
      "Notes": ""
    },
    {
      "ComponentName": "Button",
      "ParamCategory": "Style",
      "ParamName": "color",
      "ValueType": "string",
      "EnumValues": "",
      "DefaultValue": "",
      "Required": "no",
      "Notes": ""
    }
  ]
}
""",
        encoding="utf-8",
    )


def _load_whitelist(tmp_path: Path):
    component_path = tmp_path / "components.json"
    params_path = tmp_path / "params.json"
    _write_json(component_path, params_path)
    sources = LibrarySourceConfig(
        component_path=str(component_path),
        params_path=str(params_path),
        source_format="json",
    )
    components, params = load_library_sources(sources)
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
