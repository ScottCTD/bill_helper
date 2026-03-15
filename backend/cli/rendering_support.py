"""Shared helpers for `bh` compact/text renderers.

CALLING SPEC:
    render_status_compact(payload) -> str
    render_status_text(payload) -> str
    render_workspace_status_compact(payload) -> str
    render_workspace_status_text(payload) -> str
    render_compact_fallback(payload) -> str
    render_text_fallback(payload) -> str
    compact_table(...) -> str
    text_table(...) -> str
    detail_block(...) -> str
    unique_short_ids(ids) -> dict[str, str]
    compact_row(values) -> str
    escape_compact(value) -> str
    bool_text(value) -> str

Inputs:
    - decoded API payloads and scalar/list values
Outputs:
    - shared compact/text strings and reusable formatting primitives
Side effects:
    - none
"""

from __future__ import annotations

import json
from typing import Any

from backend.cli.reference import compact_schema_for

_SHORT_ID_LENGTH = 8


def render_compact_fallback(payload: dict[str, Any]) -> str:
    lines = ["OK"]
    summary = payload.get("summary")
    if summary:
        lines.append(f"summary: {summary}")
    lines.extend(f"{key}: {scalar_text(value)}" for key, value in payload.items() if key != "summary")
    return "\n".join(lines)


def render_text_fallback(payload: dict[str, Any]) -> str:
    lines = []
    summary = payload.get("summary")
    if summary:
        lines.append(str(summary))
        lines.append("")
    for key, value in payload.items():
        if key == "summary":
            continue
        lines.append(f"{key}: {scalar_text(value)}")
    return "\n".join(lines).strip()


def render_status_compact(payload: dict[str, Any]) -> str:
    auth = payload.get("auth") or {}
    workspace = payload.get("workspace") or {}
    context = payload.get("context") or {}
    return "\n".join(
        [
            "OK",
            "schema: user|workspace_status|ide_ready|thread_id|run_id|api_base_url",
            compact_row(
                [
                    auth.get("name") or auth.get("user_name") or "-",
                    workspace.get("status") or "-",
                    bool_text(workspace.get("ide_ready")),
                    context.get("thread_id") or "-",
                    context.get("run_id") or "-",
                    context.get("api_base_url") or "-",
                ]
            ),
        ]
    )


def render_status_text(payload: dict[str, Any]) -> str:
    auth = payload.get("auth") or {}
    workspace = payload.get("workspace") or {}
    context = payload.get("context") or {}
    return "\n".join(
        [
            "CLI Status",
            "",
            f"User: {auth.get('name') or auth.get('user_name') or '-'}",
            f"Workspace: {workspace.get('status') or '-'}",
            f"IDE Ready: {bool_text(workspace.get('ide_ready'))}",
            f"Thread: {context.get('thread_id') or '-'}",
            f"Run: {context.get('run_id') or '-'}",
            f"API Base URL: {context.get('api_base_url') or '-'}",
        ]
    )


def render_workspace_status_compact(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "OK",
            "schema: status|workspace_enabled|starts_on_login|ide_ready|container|volume|degraded_reason",
            compact_row(
                [
                    payload.get("status") or "-",
                    bool_text(payload.get("workspace_enabled")),
                    bool_text(payload.get("starts_on_login")),
                    bool_text(payload.get("ide_ready")),
                    payload.get("container_name") or "-",
                    payload.get("volume_name") or "-",
                    payload.get("degraded_reason") or "-",
                ]
            ),
        ]
    )


def render_workspace_status_text(payload: dict[str, Any]) -> str:
    return detail_block(
        "Workspace",
        [
            ("Status", payload.get("status")),
            ("Workspace Enabled", bool_text(payload.get("workspace_enabled"))),
            ("Starts On Login", bool_text(payload.get("starts_on_login"))),
            ("IDE Ready", bool_text(payload.get("ide_ready"))),
            ("Container", payload.get("container_name") or "-"),
            ("Volume", payload.get("volume_name") or "-"),
            ("Reason", payload.get("degraded_reason") or "-"),
        ],
    )


def compact_table(*, summary: str, schema_key: str, rows: list[list[Any]]) -> str:
    lines = ["OK", f"summary: {summary}"]
    schema = compact_schema_for(schema_key)
    if schema is not None:
        lines.append(f"schema: {schema}")
    if rows:
        lines.extend(compact_row(row) for row in rows)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def text_table(*, title: str, headers: list[str], rows: list[list[Any]], empty_text: str) -> str:
    if not rows:
        return f"{title}\n\n{empty_text}"
    table_rows = [[scalar_text(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in table_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    separator_line = "  ".join("-" * widths[index] for index in range(len(headers)))
    value_lines = [
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in table_rows
    ]
    return "\n".join([title, "", header_line, separator_line, *value_lines])


def detail_block(title: str, items: list[tuple[str, Any]]) -> str:
    lines = [title, ""]
    for label, value in items:
        lines.append(f"{label}: {scalar_text(value)}")
    return "\n".join(lines)


def unique_short_ids(ids: Any) -> dict[str, str]:
    full_ids = [str(value) for value in ids if isinstance(value, str) and value]
    counts: dict[str, int] = {}
    for value in full_ids:
        counts[value[:_SHORT_ID_LENGTH]] = counts.get(value[:_SHORT_ID_LENGTH], 0) + 1
    return {
        value: value if counts[value[:_SHORT_ID_LENGTH]] > 1 else value[:_SHORT_ID_LENGTH]
        for value in full_ids
    }


def compact_row(values: list[Any]) -> str:
    return "|".join(escape_compact(scalar_text(value)) for value in values)


def escape_compact(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "\\n")


def scalar_text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return bool_text(value)
    if isinstance(value, (list, tuple)):
        return ",".join(scalar_text(item) for item in value) or "-"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"

