# CALLING SPEC:
# - Purpose: build high-signal display summaries for persisted and streamed agent tool calls.
# - Inputs: tool names plus optional tool input/output payloads from runtime persistence or SSE snapshots.
# - Outputs: display labels and optional display details for client rendering.
# - Side effects: none.
from __future__ import annotations

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCallDisplay:
    label: str
    detail: str | None = None


def _normalize_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _humanize_tool_name(tool_name: str) -> str:
    normalized = " ".join(tool_name.replace("_", " ").split()).strip()
    if not normalized:
        return "Tool call"
    return normalized[:1].upper() + normalized[1:]


def _rename_thread_display(input_json: dict[str, Any] | None, _output_json: dict[str, Any] | None) -> ToolCallDisplay:
    title = _normalize_text((input_json or {}).get("title"))
    if title is None:
        return ToolCallDisplay(label="Renamed thread")
    return ToolCallDisplay(label=f'Renamed thread to "{title}"', detail=title)


def _shlex_split(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


def _unwrap_shell_command(command: str, *, depth: int = 0) -> str:
    if depth >= 3:
        return command
    tokens = _shlex_split(command)
    if not tokens:
        return command
    shell_names = {"bash", "sh", "zsh"}
    if tokens[0] not in shell_names:
        return command
    command_index: int | None = None
    for index, token in enumerate(tokens[1:], start=1):
        if token == "-c":
            command_index = index + 1
            break
        if token.startswith("-") and "c" in token[1:]:
            command_index = index + 1
            break
    if command_index is None or command_index >= len(tokens):
        return command
    inner = _normalize_text(tokens[command_index])
    if inner is None:
        return command
    return _unwrap_shell_command(inner, depth=depth + 1)


def _extract_terminal_command(input_json: dict[str, Any] | None) -> str | None:
    command = _normalize_text((input_json or {}).get("command"))
    if command is None:
        return None
    return _unwrap_shell_command(command)


def _bh_command_summary(command: str) -> str | None:
    tokens = _shlex_split(command)
    if not tokens or tokens[0] != "bh":
        return None
    summary_tokens: list[str] = []
    for token in tokens:
        if token.startswith("-") and summary_tokens:
            break
        if token.startswith("-") and not summary_tokens:
            continue
        summary_tokens.append(token)
        if len(summary_tokens) == 3:
            break
    if not summary_tokens or summary_tokens[0] != "bh":
        return None
    return " ".join(summary_tokens)


def _terminal_display(input_json: dict[str, Any] | None, _output_json: dict[str, Any] | None) -> ToolCallDisplay:
    command = _extract_terminal_command(input_json)
    if command is None:
        return ToolCallDisplay(label="Ran terminal command")
    bh_summary = _bh_command_summary(command)
    if bh_summary is not None:
        return ToolCallDisplay(label=bh_summary)
    return ToolCallDisplay(label="Ran terminal command")


def _count_label(prefix: str, count: int, singular: str, plural: str) -> str:
    noun = singular if count == 1 else plural
    return f"{prefix} {count} {noun}"


def _add_user_memory_display(input_json: dict[str, Any] | None, output_json: dict[str, Any] | None) -> ToolCallDisplay:
    added_count = (output_json or {}).get("added_count")
    if isinstance(added_count, int) and added_count >= 0:
        return ToolCallDisplay(label=_count_label("Added", added_count, "memory item", "memory items"))
    memory_items = (input_json or {}).get("memory_items")
    if isinstance(memory_items, list) and all(isinstance(item, str) for item in memory_items):
        return ToolCallDisplay(label=_count_label("Added", len(memory_items), "memory item", "memory items"))
    return ToolCallDisplay(label="Added memory item")


def _read_image_display(input_json: dict[str, Any] | None, output_json: dict[str, Any] | None) -> ToolCallDisplay:
    image_count = (output_json or {}).get("image_count")
    if isinstance(image_count, int) and image_count >= 0:
        return ToolCallDisplay(label=_count_label("Loaded", image_count, "image", "images"))
    paths = (input_json or {}).get("paths")
    if isinstance(paths, list) and all(isinstance(path, str) for path in paths):
        return ToolCallDisplay(label=_count_label("Loaded", len(paths), "image", "images"))
    return ToolCallDisplay(label="Loaded image")


_DISPLAY_BUILDERS: dict[str, Callable[[dict[str, Any] | None, dict[str, Any] | None], ToolCallDisplay]] = {
    "add_user_memory": _add_user_memory_display,
    "rename_thread": _rename_thread_display,
    "read_image": _read_image_display,
    "terminal": _terminal_display,
}


def build_tool_call_display(
    tool_name: str,
    *,
    input_json: dict[str, Any] | None = None,
    output_json: dict[str, Any] | None = None,
) -> ToolCallDisplay:
    builder = _DISPLAY_BUILDERS.get(tool_name)
    if builder is None:
        return ToolCallDisplay(label=_humanize_tool_name(tool_name))
    return builder(input_json, output_json)
