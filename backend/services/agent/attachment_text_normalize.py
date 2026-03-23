# CALLING SPEC:
# - Purpose: normalize extracted attachment text lines for stable model-facing output.
# - Inputs: plain strings from tests or future extractors.
# - Outputs: normalized strings.
# - Side effects: none.
from __future__ import annotations


def normalize_pdf_text_lines(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        normalized_lines.append(" ".join(line.split()))
    return "\n".join(normalized_lines).strip()
