# CALLING SPEC:
# - Purpose: implement focused service logic for `schema`.
# - Inputs: callers that import `backend/services/agent/tool_runtime_support/schema.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `schema`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from copy import deepcopy
from typing import Any


def inline_local_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not definitions:
        return schema

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            definition_key = ref.removeprefix("#/$defs/")
            definition = definitions.get(definition_key)
            if isinstance(definition, dict):
                merged = deepcopy(definition)
                for key, value in node.items():
                    if key == "$ref":
                        continue
                    merged[key] = resolve(value)
                return resolve(merged)

        return {key: resolve(value) for key, value in node.items() if key != "$defs"}

    return resolve(schema)
