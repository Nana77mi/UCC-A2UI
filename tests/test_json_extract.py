from __future__ import annotations

import pytest

from ucc_a2ui.generator.json_extract import JSONExtractError, extract_first_json


def test_extract_first_json() -> None:
    text = """
    ```json
    {"plan": {"intent": "x"}, "ir": {"version": "ucc-ui-ir@v0", "theme": {}, "variables": [], "tree": {"type": "button", "props": {}, "events": {}, "children": []}}}
    ```
    """
    data = extract_first_json(text)
    assert "plan" in data


def test_extract_invalid_json() -> None:
    with pytest.raises(JSONExtractError):
        extract_first_json("no json")
