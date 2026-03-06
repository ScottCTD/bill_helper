from __future__ import annotations

import base64
import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import litellm
import pymupdf

from backend.models_agent import AgentMessageAttachment
from backend.services.agent.error_policy import recoverable_result

logger = logging.getLogger(__name__)

FORCED_VISION_MODEL_ALIASES = frozenset(
    {
        "openrouter/qwen/qwen3.5-27b",
        "qwen/qwen3.5-27b",
    }
)
PDF_OCR_RENDER_DPI = 300
PDF_OCR_TESSERACT_PSM = 4
PDF_OCR_TESSERACT_OEM = 3
PDF_OCR_TESSERACT_LANG = "eng"
PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS = 20
VISION_SUPPORT_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
PDF_EXTRACTION_EXCEPTIONS = (
    FileNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    pymupdf.FileDataError,
)
PDF_OCR_EXCEPTIONS = PDF_EXTRACTION_EXCEPTIONS + (subprocess.SubprocessError,)
PDF_RENDER_EXCEPTIONS = PDF_EXTRACTION_EXCEPTIONS


def _pdf_failure_code(error: Exception, *, stage: str) -> str:
    if isinstance(error, FileNotFoundError):
        return f"{stage}_file_not_found"
    if isinstance(error, PermissionError):
        return f"{stage}_permission_denied"
    if isinstance(error, subprocess.TimeoutExpired):
        return f"{stage}_timeout"
    if isinstance(error, subprocess.CalledProcessError):
        return f"{stage}_subprocess_failed"
    if isinstance(error, pymupdf.FileDataError):
        return f"{stage}_invalid_pdf_data"
    if isinstance(error, OSError):
        return f"{stage}_os_error"
    if isinstance(error, RuntimeError):
        return f"{stage}_runtime_error"
    return f"{stage}_unknown_error"


def _record_pdf_failure(
    *,
    scope: str,
    file_path: Path,
    stage: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> None:
    failure_code = _pdf_failure_code(error, stage=stage)
    metadata: dict[str, Any] = {
        "file_path": str(file_path),
        "failure_code": failure_code,
    }
    if context:
        metadata.update(context)
    recoverable_result(
        scope=scope,
        fallback=None,
        error=error,
        context=metadata,
        log=logger,
    )
    logger.warning(
        "recoverable attachment parsing failure scope=%s failure_code=%s file_path=%s error=%s",
        scope,
        failure_code,
        file_path,
        str(error),
    )


def attachment_to_data_url(file_path: str, mime_type: str) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


def is_pdf_attachment(attachment: AgentMessageAttachment) -> bool:
    mime_type = (attachment.mime_type or "").lower()
    if mime_type == "application/pdf":
        return True
    return Path(attachment.file_path).suffix.lower() == ".pdf"


def _normalize_pdf_text_lines(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        normalized_lines.append(" ".join(line.split()))
    return "\n".join(normalized_lines).strip()


def extract_pdf_text(file_path: str) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        with pymupdf.open(path) as document:
            page_texts = [_normalize_pdf_text_lines(page.get_text("text", sort=True)) for page in document]
    except PDF_EXTRACTION_EXCEPTIONS as exc:
        _record_pdf_failure(
            scope="attachments.extract_pdf_text",
            file_path=path,
            stage="extract",
            error=exc,
        )
        return None
    extracted = "\n\n".join(text for text in page_texts if text)
    return extracted or None


def extract_pdf_text_with_tesseract(file_path: str) -> str | None:
    path = Path(file_path)
    if not path.exists() or shutil.which("tesseract") is None:
        return None
    current_page_index: int | None = None
    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            with pymupdf.open(path) as document:
                page_texts: list[str] = []
                for page_index, page in enumerate(document, start=1):
                    current_page_index = page_index
                    image_path = temp_dir / f"page_{page_index:04d}.png"
                    pixmap = page.get_pixmap(dpi=PDF_OCR_RENDER_DPI, alpha=False)
                    pixmap.save(image_path)
                    result = subprocess.run(
                        [
                            "tesseract",
                            str(image_path),
                            "stdout",
                            "--psm",
                            str(PDF_OCR_TESSERACT_PSM),
                            "--oem",
                            str(PDF_OCR_TESSERACT_OEM),
                            "-l",
                            PDF_OCR_TESSERACT_LANG,
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS,
                    )
                    page_texts.append(_normalize_pdf_text_lines(result.stdout))
    except PDF_OCR_EXCEPTIONS as exc:
        _record_pdf_failure(
            scope="attachments.extract_pdf_text_with_tesseract",
            file_path=path,
            stage="ocr",
            error=exc,
            context={
                "page_index": current_page_index,
                "timeout_seconds": PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS,
            },
        )
        return None
    extracted = "\n\n".join(text for text in page_texts if text)
    return extracted or None


def extract_pdf_text_for_model(file_path: str) -> tuple[str | None, str | None]:
    native_text = extract_pdf_text(file_path)
    if native_text:
        return native_text, "parsed with PyMuPDF text extraction"
    ocr_text = extract_pdf_text_with_tesseract(file_path)
    if ocr_text:
        return ocr_text, "parsed with Tesseract OCR; expect imperfect text"
    return None, None


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


def pdf_page_image_data_urls(file_path: str) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        return []
    try:
        with pymupdf.open(path) as document:
            data_urls: list[str] = []
            for page in document:
                pixmap = page.get_pixmap(alpha=False)
                image_bytes = pixmap.tobytes("png")
                encoded = base64.b64encode(image_bytes).decode("ascii")
                data_urls.append(f"data:image/png;base64,{encoded}")
            return data_urls
    except PDF_RENDER_EXCEPTIONS as exc:
        _record_pdf_failure(
            scope="attachments.pdf_page_image_data_urls",
            file_path=path,
            stage="render",
            error=exc,
        )
        return []
