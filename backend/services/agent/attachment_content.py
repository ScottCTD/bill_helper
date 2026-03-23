# CALLING SPEC:
# - Purpose: attachment-related exports for message history (vision detection and assembly seam).
# - Inputs: callers that import `backend/services/agent/attachment_content.py`.
# - Outputs: vision helper, text normalization, and assembly exports.
# - Side effects: module-defined orchestration only where invoked.
from __future__ import annotations

from collections.abc import Callable

import litellm

from backend.services.agent.attachment_content_assembly import (
    assemble_attachment_parts,
    assemble_image_attachment_parts,
    assemble_pdf_attachment_parts,
    attachment_display_name,
    is_pdf_attachment,
)
from backend.services.agent.attachment_text_normalize import normalize_pdf_text_lines
from backend.services.agent.error_policy import recoverable_result

FORCED_VISION_MODEL_ALIASES = frozenset(
    {
        "openrouter/qwen/qwen3.5-27b",
        "qwen/qwen3.5-27b",
    }
)
VISION_SUPPORT_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)


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
