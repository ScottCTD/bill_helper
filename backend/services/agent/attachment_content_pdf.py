from __future__ import annotations

import base64
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

import pymupdf

from backend.services.agent.error_policy import recoverable_result

logger = logging.getLogger(__name__)

PDF_OCR_RENDER_DPI = 300
PDF_OCR_TESSERACT_PSM = 4
PDF_OCR_TESSERACT_OEM = 3
PDF_OCR_TESSERACT_LANG = "eng"
PDF_OCR_SUBPROCESS_TIMEOUT_SECONDS = 20
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
    recoverable_fn: Callable[..., Any] = recoverable_result,
) -> None:
    failure_code = _pdf_failure_code(error, stage=stage)
    metadata: dict[str, Any] = {
        "file_path": str(file_path),
        "failure_code": failure_code,
    }
    if context:
        metadata.update(context)
    recoverable_fn(
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


def normalize_pdf_text_lines(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        normalized_lines.append(" ".join(line.split()))
    return "\n".join(normalized_lines).strip()


def extract_pdf_text(
    file_path: str,
    *,
    pymupdf_module: Any = pymupdf,
    recoverable_fn: Callable[..., Any] = recoverable_result,
) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        with pymupdf_module.open(path) as document:
            page_texts = [
                normalize_pdf_text_lines(page.get_text("text", sort=True))
                for page in document
            ]
    except PDF_EXTRACTION_EXCEPTIONS as exc:
        _record_pdf_failure(
            scope="attachments.extract_pdf_text",
            file_path=path,
            stage="extract",
            error=exc,
            recoverable_fn=recoverable_fn,
        )
        return None
    extracted = "\n\n".join(text for text in page_texts if text)
    return extracted or None


def extract_pdf_text_with_tesseract(
    file_path: str,
    *,
    shutil_module: Any = shutil,
    subprocess_module: Any = subprocess,
    pymupdf_module: Any = pymupdf,
    recoverable_fn: Callable[..., Any] = recoverable_result,
) -> str | None:
    path = Path(file_path)
    if not path.exists() or shutil_module.which("tesseract") is None:
        return None
    current_page_index: int | None = None
    try:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            with pymupdf_module.open(path) as document:
                page_texts: list[str] = []
                for page_index, page in enumerate(document, start=1):
                    current_page_index = page_index
                    image_path = temp_dir / f"page_{page_index:04d}.png"
                    pixmap = page.get_pixmap(dpi=PDF_OCR_RENDER_DPI, alpha=False)
                    pixmap.save(image_path)
                    result = subprocess_module.run(
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
                    page_texts.append(normalize_pdf_text_lines(result.stdout))
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
            recoverable_fn=recoverable_fn,
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


def pdf_page_image_data_urls(
    file_path: str,
    *,
    pymupdf_module: Any = pymupdf,
    recoverable_fn: Callable[..., Any] = recoverable_result,
) -> list[str]:
    path = Path(file_path)
    if not path.exists():
        return []
    try:
        with pymupdf_module.open(path) as document:
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
            recoverable_fn=recoverable_fn,
        )
        return []
