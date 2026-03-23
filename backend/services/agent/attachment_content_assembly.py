# CALLING SPEC:
# - Purpose: build multimodal LLM parts for agent attachments (Docling bundle layout).
# - Inputs: persisted ``AgentMessageAttachment`` rows and assembly options.
# - Outputs: OpenAI-style content part dicts.
# - Side effects: reads canonical files from disk.
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.models_agent import AgentMessageAttachment
from backend.services.agent.agent_attachment_bundle import (
    is_docling_bundle_primary_stored_path,
    workspace_uploads_prefix_for_primary_stored_path,
)

_MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def is_pdf_attachment(attachment: AgentMessageAttachment) -> bool:
    mime_type = (attachment.mime_type or "").lower()
    if mime_type == "application/pdf":
        return True
    return Path(attachment.file_path).suffix.lower() == ".pdf"


def attachment_display_name(attachment: AgentMessageAttachment) -> str:
    original_name = " ".join((attachment.original_filename or "").split()).strip()
    if original_name:
        return Path(original_name).name or original_name
    fallback_name = Path(attachment.file_path).name
    return fallback_name or "attachment"


def _vision_image_paths_for_bundle(
    bundle_dir: Path,
    md_text: str,
    *,
    primary_path: Path,
) -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for _alt, raw in _MARKDOWN_IMAGE.findall(md_text):
        base = Path(raw.strip().replace("\\", "/")).name
        candidate = bundle_dir / base
        if (
            candidate.is_file()
            and candidate.resolve() != primary_path.resolve()
            and base not in seen
        ):
            seen.add(base)
            ordered.append(candidate)
    for entry in sorted(bundle_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_file() or entry.name == "parsed.md":
            continue
        if entry.resolve() == primary_path.resolve():
            continue
        if entry.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        if entry.name in seen:
            continue
        seen.add(entry.name)
        ordered.append(entry)
    return ordered


def _assemble_docling_bundle_parts(
    attachment: AgentMessageAttachment,
    *,
    attachment_name: str,
) -> list[dict[str, Any]]:
    primary = Path(attachment.file_path)
    bundle_dir = primary.parent
    parsed_path = bundle_dir / "parsed.md"
    if not parsed_path.is_file():
        return [
            {
                "type": "text",
                "text": (
                    f"Attachment {attachment_name} is missing Docling output (parsed.md). "
                    "Re-upload the file to regenerate the bundle."
                ),
            }
        ]
    md_text = parsed_path.read_text(encoding="utf-8", errors="replace")
    stored = attachment.user_file.stored_relative_path
    prefix = workspace_uploads_prefix_for_primary_stored_path(stored)
    path_lines = ""
    image_paths = _vision_image_paths_for_bundle(bundle_dir, md_text, primary_path=primary)
    has_visual_paths = bool(image_paths) or (
        not is_pdf_attachment(attachment) and primary.suffix.lower() in _IMAGE_SUFFIXES
    )
    if prefix:
        path_lines = (
            "Workspace paths:\n"
            f"- {prefix}/{primary.name}\n"
            f"- {prefix}/parsed.md\n"
        )
        for img in image_paths:
            path_lines += f"- {prefix}/{img.name}\n"
    image_note = ""
    if has_visual_paths:
        image_note = (
            "\nRelated images are available in the workspace. "
            "Use `read_image` with the listed `/workspace/...` paths only if visual inspection is needed."
        )
    header = (
        f"Attachment {attachment_name} (Docling markdown + related workspace images).\n"
        f"{path_lines}\n"
        f"{image_note}\n"
        f"--- parsed.md ---\n{md_text}"
    )
    return [{"type": "text", "text": header}]


def _non_bundle_reupload_parts(attachment_name: str, *, is_pdf: bool) -> list[dict[str, Any]]:
    kind = "PDF" if is_pdf else "image"
    return [
        {
            "type": "text",
            "text": (
                f"Attachment {attachment_name} is not stored as a dated Docling bundle; "
                f"re-upload the {kind} so it can be parsed."
            ),
        }
    ]


def assemble_pdf_attachment_parts(
    attachment: AgentMessageAttachment,
    *,
    attachment_name: str,
) -> list[dict[str, Any]]:
    if is_docling_bundle_primary_stored_path(attachment.user_file.stored_relative_path):
        return _assemble_docling_bundle_parts(
            attachment,
            attachment_name=attachment_name,
        )
    return _non_bundle_reupload_parts(attachment_name, is_pdf=True)


def assemble_image_attachment_parts(
    attachment: AgentMessageAttachment,
    *,
    attachment_name: str,
) -> list[dict[str, Any]]:
    if is_docling_bundle_primary_stored_path(attachment.user_file.stored_relative_path):
        return _assemble_docling_bundle_parts(
            attachment,
            attachment_name=attachment_name,
        )
    return _non_bundle_reupload_parts(attachment_name, is_pdf=False)


def assemble_attachment_parts(
    attachments: list[AgentMessageAttachment],
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for attachment in attachments:
        attachment_name = attachment_display_name(attachment)
        if is_pdf_attachment(attachment):
            parts.extend(
                assemble_pdf_attachment_parts(
                    attachment,
                    attachment_name=attachment_name,
                )
            )
            continue
        parts.extend(
            assemble_image_attachment_parts(
                attachment,
                attachment_name=attachment_name,
            )
        )
    return parts
