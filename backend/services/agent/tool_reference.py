"""Rendered markdown references for the model-visible agent tool surface.

CALLING SPEC:
    render_runtime_tool_contract_markdown() -> str

Inputs:
    - none
Outputs:
    - markdown describing the exact runtime-visible tool names, descriptions, and typed arguments
Side effects:
    - none
"""

from __future__ import annotations

from typing import Any

from backend.services.agent.tool_runtime_support.catalog import build_openai_tool_schemas


def render_runtime_tool_contract_markdown() -> str:
    sections: list[str] = []
    for schema in build_openai_tool_schemas():
        tool = schema["function"]
        parameters = tool["parameters"]
        properties = parameters.get("properties") or {}
        required = set(parameters.get("required") or [])
        lines = [f"### `{tool['name']}`", "", "Description:", "", tool["description"], "", "Arguments:", ""]
        if not properties:
            lines.append("- none")
        else:
            for name, property_schema in properties.items():
                lines.extend(_argument_lines(name, property_schema, required=name in required))
        sections.append("\n".join(lines).rstrip())
    return "\n\n".join(sections) + "\n"


def _argument_lines(name: str, property_schema: dict[str, Any], *, required: bool) -> list[str]:
    type_text = _schema_type_text(property_schema)
    lines = [f"- `{name}: {type_text}`{' required' if required else ''}"]
    description = str(property_schema.get("description") or "").strip()
    if description:
        lines.append(f"  description: {description}")
    constraints = _constraint_bits(property_schema)
    if constraints:
        lines.append(f"  constraints: {', '.join(constraints)}")
    return lines


def _schema_type_text(schema: dict[str, Any]) -> str:
    if "anyOf" in schema:
        return " | ".join(_schema_type_text(part) for part in schema["anyOf"])
    schema_type = schema.get("type")
    if schema_type == "array":
        item_schema = schema.get("items") or {}
        return f"list[{_schema_type_text(item_schema)}]"
    if isinstance(schema_type, list):
        return " | ".join(str(item) for item in schema_type)
    return str(schema_type or "object")


def _constraint_bits(schema: dict[str, Any]) -> list[str]:
    bits: list[str] = []
    for key in ("minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems", "default"):
        if key in schema:
            bits.append(f"{key}={schema[key]}")
    return bits

