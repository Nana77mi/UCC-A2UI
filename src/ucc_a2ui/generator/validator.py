from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

from jsonschema import Draft7Validator

from ..library.whitelist import EVENT_WHITELIST, LibraryWhitelist
from .ir_schema import IR_SCHEMA

BINDING_KEYS = {
    "textBinding",
    "valueBinding",
    "srcBinding",
    "optionsBinding",
    "urlBinding",
    "itemsBinding",
}


@dataclass
class ValidationError:
    code: str
    path: str
    message: str


def _json_path(path_parts: List[Any]) -> str:
    if not path_parts:
        return "$"
    return "$" + "".join([f"[{part!r}]" if isinstance(part, int) else f".{part}" for part in path_parts])


def _extract_variable_names(variables: List[Dict[str, Any]]) -> Set[str]:
    names: Set[str] = set()
    for var in variables:
        name = var.get("name") if isinstance(var, dict) else None
        if isinstance(name, str):
            names.add(name)
    return names


def _normalize_binding(value: str) -> str:
    if value.startswith("@"):
        return value[1:]
    return value


def _validate_node(
    node: Dict[str, Any],
    whitelist: LibraryWhitelist,
    strict: bool,
    errors: List[ValidationError],
    path: List[Any],
) -> None:
    component_type = node.get("type")
    component = whitelist.components.get(component_type)
    if component is None:
        errors.append(ValidationError("E_UNKNOWN_COMPONENT", _json_path(path + ["type"]), "Unknown component"))
        return

    allowed_props = set(component.key_params)
    if strict and component.strict_params:
        allowed_props = {param.name for param in component.strict_params if param.name}

    props = node.get("props", {})
    if isinstance(props, dict):
        for key in props.keys():
            if key not in allowed_props:
                errors.append(
                    ValidationError("E_UNKNOWN_PROP", _json_path(path + ["props", key]), "Unknown prop")
                )
    events = node.get("events", {})
    if isinstance(events, dict):
        for key in events.keys():
            if key not in EVENT_WHITELIST:
                errors.append(
                    ValidationError("E_UNKNOWN_EVENT", _json_path(path + ["events", key]), "Unknown event")
                )

    children = node.get("children", [])
    if isinstance(children, list):
        for idx, child in enumerate(children):
            _validate_node(child, whitelist, strict, errors, path + ["children", idx])


def validate_ir(
    ir: Dict[str, Any],
    whitelist: LibraryWhitelist,
    strict: bool = False,
) -> Dict[str, Any]:
    errors: List[ValidationError] = []

    schema_validator = Draft7Validator(IR_SCHEMA)
    for error in schema_validator.iter_errors(ir):
        errors.append(ValidationError("E_SCHEMA", _json_path(list(error.path)), error.message))

    if errors:
        return _build_report(errors, schema_pass=False)

    _validate_node(ir.get("tree", {}), whitelist, strict, errors, ["tree"])

    variables = ir.get("variables", [])
    variable_names = _extract_variable_names(variables if isinstance(variables, list) else [])
    binding_errors: List[ValidationError] = []

    def walk_bindings(node: Dict[str, Any], path: List[Any]) -> None:
        props = node.get("props", {})
        if isinstance(props, dict):
            for key, value in props.items():
                if key in BINDING_KEYS and isinstance(value, str):
                    name = _normalize_binding(value)
                    if name not in variable_names:
                        binding_errors.append(
                            ValidationError(
                                "E_UNKNOWN_BINDING_VAR",
                                _json_path(path + ["props", key]),
                                f"Unknown binding var {name}",
                            )
                        )
        for idx, child in enumerate(node.get("children", []) or []):
            walk_bindings(child, path + ["children", idx])

    walk_bindings(ir.get("tree", {}), ["tree"])
    errors.extend(binding_errors)

    theme = ir.get("theme")
    if not isinstance(theme, dict):
        errors.append(ValidationError("E_INVALID_THEME", "$.theme", "Theme must be object"))

    return _build_report(errors, schema_pass=True)


def _build_report(errors: List[ValidationError], schema_pass: bool) -> Dict[str, Any]:
    error_dicts = [error.__dict__ for error in errors]
    return {
        "SchemaPass": schema_pass,
        "ComponentWhitelistPass": not any(error.code == "E_UNKNOWN_COMPONENT" for error in errors),
        "PropsWhitelistPass": not any(error.code == "E_UNKNOWN_PROP" for error in errors),
        "EventsWhitelistPass": not any(error.code == "E_UNKNOWN_EVENT" for error in errors),
        "BindingSanity": not any(error.code == "E_UNKNOWN_BINDING_VAR" for error in errors),
        "ThemePass": not any(error.code == "E_INVALID_THEME" for error in errors),
        "errors": error_dicts,
    }
