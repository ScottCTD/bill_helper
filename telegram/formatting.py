from __future__ import annotations

from html import escape
import re

TELEGRAM_HTML_MESSAGE_LIMIT = 4096

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MARKDOWN_BLOCKQUOTE_PATTERN = re.compile(r"^\s*>\s?", re.MULTILINE)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:[a-zA-Z0-9_+.-]+)?\n?|```")


def simplify_markdown_for_telegram(text: str | None) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    simplified = _MARKDOWN_LINK_PATTERN.sub(r"\1 (\2)", normalized)
    simplified = _MARKDOWN_HEADING_PATTERN.sub("", simplified)
    simplified = _MARKDOWN_BLOCKQUOTE_PATTERN.sub("", simplified)
    simplified = _MARKDOWN_FENCE_PATTERN.sub("", simplified)
    simplified = simplified.replace("**", "").replace("__", "").replace("~~", "").replace("`", "")
    simplified = re.sub(r"\n{3,}", "\n\n", simplified).strip()
    return simplified


def chunk_telegram_html(text: str, *, max_chars: int = TELEGRAM_HTML_MESSAGE_LIMIT) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    normalized = _normalize_text(text)
    if not normalized:
        return []
    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > max_chars:
        split_index = _find_split_index(remaining, max_chars)
        chunks.append(remaining[:split_index].rstrip())
        remaining = remaining[split_index:].lstrip()
    chunks.append(remaining)
    return chunks


def format_status_html(title: str, body: str | None = None) -> str:
    escaped_title = escape(_normalize_text(title), quote=False)
    escaped_body = escape(_normalize_text(body), quote=False)
    return f"<b>{escaped_title}</b>\n{escaped_body}" if escaped_body else f"<b>{escaped_title}</b>"


def render_telegram_reply_chunks(text: str | None) -> list[str]:
    escaped = escape(_normalize_text(text), quote=False)
    return chunk_telegram_html(escaped)


def _find_split_index(text: str, max_chars: int) -> int:
    for delimiter in ("\n\n", "\n", " "):
        candidate = text.rfind(delimiter, 0, max_chars + 1)
        if candidate > 0:
            return _adjust_split_for_entity(text, candidate + len(delimiter))
    return _adjust_split_for_entity(text, max_chars)


def _adjust_split_for_entity(text: str, split_index: int) -> int:
    amp_index = text.rfind("&", 0, split_index)
    semi_index = text.rfind(";", 0, split_index)
    if amp_index <= semi_index:
        return split_index
    next_semi = text.find(";", split_index)
    if next_semi == -1 or next_semi - amp_index > 10:
        return split_index
    if amp_index > 0:
        return amp_index
    return next_semi + 1


def _normalize_text(text: str | None) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()