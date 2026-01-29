IR_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "theme", "variables", "tree"],
    "properties": {
        "version": {"type": "string"},
        "theme": {"type": "object"},
        "variables": {"type": "array"},
        "tree": {"$ref": "#/definitions/node"},
    },
    "definitions": {
        "node": {
            "type": "object",
            "required": ["type", "props", "events", "children"],
            "properties": {
                "type": {"type": "string"},
                "props": {"type": "object"},
                "events": {"type": "object"},
                "children": {"type": "array", "items": {"$ref": "#/definitions/node"}},
            },
        }
    },
}
