from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.models_agent import AgentMessageAttachment
from backend.services.agent.attachment_content_pdf import (
    extract_pdf_text_for_model,
    pdf_page_image_data_urls,
)


def attachment_to_data_url(file_path: str, mime_type: str) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


@dataclass(slots=True)
class AttachmentAssemblyOptions:
    include_pdf_page_images: bool = True
    pdf_text_extractor: Callable[[str], tuple[str | None, str | None]] | None = None
    pdf_page_image_renderer: Callable[[str], list[str]] | None = None


def assemble_pdf_attachment_parts(
    attachment: AgentMessageAttachment,
    *,
    attachment_name: str,
    options: AttachmentAssemblyOptions,
) -> list[dict[str, Any]]:
    pdf_text_extractor = options.pdf_text_extractor or extract_pdf_text_for_model
    pdf_text, pdf_source = pdf_text_extractor(attachment.file_path)
    if pdf_text:
        parts: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": f"PDF file {attachment_name} ({pdf_source}):\n{pdf_text}",
            }
        ]
    else:
        parts = [
            {
                "type": "text",
                "text": f"PDF file {attachment_name} was provided, but parsing returned no content.",
            }
        ]
    if options.include_pdf_page_images:
        pdf_page_image_renderer = options.pdf_page_image_renderer or pdf_page_image_data_urls
        parts.extend(
            {"type": "image_url", "image_url": {"url": data_url}}
            for data_url in pdf_page_image_renderer(attachment.file_path)
        )
    return parts


def assemble_image_attachment_parts(
    attachment: AgentMessageAttachment,
    *,
    attachment_name: str,
) -> list[dict[str, Any]]:
    data_url = attachment_to_data_url(attachment.file_path, attachment.mime_type)
    if data_url is None:
        return [
            {
                "type": "text",
                "text": f"Image file {attachment_name} was provided, but the file could not be loaded.",
            }
        ]
    return [
        {"type": "text", "text": f"Image file {attachment_name}:"},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]


def assemble_attachment_parts(
    attachments: list[AgentMessageAttachment],
    *,
    options: AttachmentAssemblyOptions,
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for attachment in attachments:
        attachment_name = attachment_display_name(attachment)
        if is_pdf_attachment(attachment):
            parts.extend(
                assemble_pdf_attachment_parts(
                    attachment,
                    attachment_name=attachment_name,
                    options=options,
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
