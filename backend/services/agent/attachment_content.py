# CALLING SPEC:
# - Purpose: implement focused service logic for `attachment_content`.
# - Inputs: callers that import `backend/services/agent/attachment_content.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `attachment_content`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from collections.abc import Callable
import shutil
import subprocess

import litellm
import pymupdf

from backend.services.agent import attachment_content_pdf as _attachment_content_pdf
from backend.services.agent.attachment_content_assembly import (
    AttachmentAssemblyOptions,
    assemble_attachment_parts,
    assemble_image_attachment_parts,
    assemble_pdf_attachment_parts,
    attachment_display_name,
    attachment_to_data_url,
    is_pdf_attachment,
)
from backend.services.agent.error_policy import recoverable_result

FORCED_VISION_MODEL_ALIASES = frozenset(
    {
        "openrouter/qwen/qwen3.5-27b",
        "qwen/qwen3.5-27b",
    }
)
VISION_SUPPORT_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS = _attachment_content_pdf.PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS


def _normalize_model_for_vision_check(model_name: str) -> str:
    normalized = " ".join((model_name or "").split()).strip()
    if normalized.lower().startswith("google/"):
        suffix = normalized.split("/", 1)[1]
        return f"gemini/{suffix}"
    return normalized


def model_supports_vision(
    model_name: str,
    *,
    supports_vision: Callable[[str], bool] | None = None,
) -> bool:
    normalized = _normalize_model_for_vision_check(model_name)
    if not normalized:
        return False
    candidates = [normalized]
    raw = " ".join((model_name or "").split()).strip()
    if raw and raw != normalized:
        candidates.append(raw)

    supports_vision_fn = supports_vision or litellm.supports_vision
    for candidate in candidates:
        try:
            if supports_vision_fn(candidate):
                return True
        except VISION_SUPPORT_EXCEPTIONS as exc:
            recoverable_result(
                scope="message_history.supports_vision",
                fallback=False,
                error=exc,
                context={"candidate_model": candidate},
            )
            continue
    if any(candidate.lower() in FORCED_VISION_MODEL_ALIASES for candidate in candidates):
        return True
    return False


def normalize_pdf_text_lines(text: str) -> str:
    return _attachment_content_pdf.normalize_pdf_text_lines(text)


def extract_pdf_text(file_path: str) -> str | None:
    return _attachment_content_pdf.extract_pdf_text(
        file_path,
        pymupdf_module=pymupdf,
        recoverable_fn=recoverable_result,
    )


def extract_pdf_text_with_tesseract(file_path: str) -> str | None:
    return _attachment_content_pdf.extract_pdf_text_with_tesseract(
        file_path,
        shutil_module=shutil,
        subprocess_module=subprocess,
        pymupdf_module=pymupdf,
        recoverable_fn=recoverable_result,
    )


def extract_pdf_text_for_model(file_path: str) -> tuple[str | None, str | None]:
    native_text = extract_pdf_text(file_path)
    if native_text:
        return native_text, "parsed with PyMuPDF text extraction"
    ocr_text = extract_pdf_text_with_tesseract(file_path)
    if ocr_text:
        return ocr_text, "parsed with Tesseract OCR; expect imperfect text"
    return None, None


def pdf_page_image_data_urls(file_path: str) -> list[str]:
    return _attachment_content_pdf.pdf_page_image_data_urls(
        file_path,
        pymupdf_module=pymupdf,
        recoverable_fn=recoverable_result,
    )
