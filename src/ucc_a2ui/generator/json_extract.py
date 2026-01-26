from __future__ import annotations

import json
import re
from typing import Any


class JSONExtractError(Exception):
    pass


def extract_first_json(text: str) -> Any:
    if not text:
        raise JSONExtractError("Empty output")
    cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    while start != -1:
        depth = 0
        for idx in range(start, len(cleaned)):
            if cleaned[idx] == "{":
                depth += 1
            elif cleaned[idx] == "}":
                depth -= 1
                if depth == 0:
                    snippet = cleaned[start : idx + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        break
        start = cleaned.find("{", start + 1)
    raise JSONExtractError("No valid JSON object found")
