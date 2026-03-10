from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.models_agent import AgentMessage
from backend.services.agent import attachment_content
from backend.services.taxonomy import list_term_name_description_pairs


def _compose_user_feedback_text(
    message: AgentMessage,
    *,
    review_results_prefix: str | None,
    interruption_prefix: str | None,
) -> str:
    prefixes = [
        prefix
        for prefix in (interruption_prefix, review_results_prefix)
        if isinstance(prefix, str) and prefix.strip()
    ]
    if not prefixes:
        return message.content_markdown
    feedback = message.content_markdown.strip() or "(none)"
    return f"{'\n\n'.join(prefixes)}\n\nUser feedback:\n{feedback}"


def build_entity_category_context(db: Session) -> str | None:
    records = list_term_name_description_pairs(db, taxonomy_key="entity_category")
    if not records:
        return None

    lines: list[str] = []
    for name, description in records:
        if description:
            lines.append(f"- {name}: {description}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def build_user_content(
    message: AgentMessage,
    *,
    review_results_prefix: str | None = None,
    interruption_prefix: str | None = None,
    include_pdf_page_images: bool = True,
) -> str | list[dict[str, Any]]:
    content_text = _compose_user_feedback_text(
        message,
        review_results_prefix=review_results_prefix,
        interruption_prefix=interruption_prefix,
    )
    if not message.attachments:
        return content_text

    parts = attachment_content.assemble_attachment_parts(
        message.attachments,
        options=attachment_content.AttachmentAssemblyOptions(
            include_pdf_page_images=include_pdf_page_images,
            pdf_text_extractor=attachment_content.extract_pdf_text_for_model,
            pdf_page_image_renderer=attachment_content.pdf_page_image_data_urls,
        ),
    )

    if content_text.strip():
        parts.append({"type": "text", "text": content_text})
    if parts:
        return parts
    return content_text or "User sent attachments."
