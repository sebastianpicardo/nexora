from __future__ import annotations

from typing import Any


def clean_schema(schema: dict) -> dict:
    """Adapta un JSON Schema de Pydantic a un subconjunto aceptado por LLMs."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            target = defs.get(name)
            if isinstance(target, dict):
                return walk(target)

        result: dict = {}
        for key, value in node.items():
            if key in {"$defs", "$ref", "title", "format", "default"}:
                continue
            if key == "properties" and isinstance(value, dict):
                result[key] = {name: walk(sub) for name, sub in value.items()}
            else:
                result[key] = walk(value)

        if result.get("type") == "object":
            result.setdefault("additionalProperties", False)
        return result

    return walk(schema)
