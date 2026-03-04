# OCR Fallback For Redacted PDFs

## Problem

Some statement PDFs become unreadable to the backend after redaction in Apple Preview.

Observed behavior:

- the redacted PDF can still appear text-selectable in Preview
- the backend's PyMuPDF text extraction returns zero characters for every page
- the PDF pages are effectively image-only from the backend parser's perspective

This happens because Preview can expose OCR or Live Text style selection in the viewer even when the saved PDF no longer contains a normal embedded text layer that `page.get_text("text")` can read.

## User-Visible Failure Mode

The agent receives a PDF attachment, but the backend reports that text extraction returned no content.

For non-vision models, that means the agent cannot read the statement at all.

For vision-capable models, the current backend can still send rendered page images, but that path depends on model capability detection and is still weaker than having reliable extracted text for downstream parsing, search, and structured ingestion.

## Current Implementation

Relevant modules:

- `backend/services/agent/message_history.py`
  - `_extract_pdf_text()` uses PyMuPDF `page.get_text("text", sort=True)`
  - `_pdf_page_image_data_urls()` renders each page to PNG for multimodal models
  - `build_user_content()` appends extracted PDF text when available and otherwise emits a "text extraction returned no content" note
- `backend/routers/agent.py`
  - accepts PDF attachments and persists them under `.data/agent_uploads/<message_id>/...`
- `backend/tests/test_agent.py`
  - covers current PDF text extraction and page-image attachment behavior

## Proposal

Add an OCR fallback path for PDFs whose normal text extraction returns no usable content.

Suggested flow:

1. Attempt normal PyMuPDF text extraction first.
2. If extracted text is empty (or below a low threshold), render each page to an image.
3. Run OCR on the rendered page images.
4. Normalize OCR text similarly to current line normalization.
5. Append OCR-derived text into the model-visible user content with explicit labeling, for example:
   - `PDF attachment 1 (OCR fallback after no extractable text):`
6. Continue sending page images as image inputs for vision-capable models.

## Candidate Approaches

### Option A: Local OCR via macOS Vision / system tooling

Pros:

- no external API dependency
- keeps sensitive financial statements on-device
- likely best fit for local-first workflow

Cons:

- macOS-specific implementation
- may require bridging through a CLI or a small helper script

### Option B: Tesseract-based OCR

Pros:

- cross-platform
- common and well understood

Cons:

- new system dependency
- installation complexity for contributors
- OCR quality can vary significantly by statement layout

### Option C: Vision-model OCR only

Pros:

- no additional OCR library
- leverages the existing multimodal model path

Cons:

- does not help non-vision models
- harder to reuse extracted text deterministically for parsing and search
- couples OCR quality to provider/model capability metadata

## Recommended Direction

Prefer a local OCR fallback that produces explicit extracted text, not just page images.

The backend should treat OCR as a recovery path for "visually readable but not text-extractable" PDFs, especially after redaction/export workflows that flatten the original text layer.

## Operational Impact

Expected changes if implemented:

- backend dependency or platform integration for OCR
- additional processing time for PDF uploads that need fallback
- possible new configuration to enable/disable OCR fallback
- new tests for image-only PDFs and OCR fallback labeling
- backend docs updates describing primary extraction vs OCR fallback behavior

## Constraints And Risks

- OCR output may introduce recognition errors on low-quality or heavily redacted statements
- redaction overlays can confuse OCR if the page is partially flattened or recompressed
- OCR should not silently replace native text extraction when native extraction is available
- the user should be able to distinguish native extracted text from OCR-derived text in agent context

## Acceptance Criteria

- a redacted PDF that returns no text from PyMuPDF still yields usable model-visible text via OCR
- the agent can summarize or extract key statement details from an image-only PDF with a non-vision model
- OCR-derived text is clearly labeled in the composed user content
- existing native-text PDFs continue to use the faster primary extraction path
- tests cover both native extraction and OCR fallback paths
