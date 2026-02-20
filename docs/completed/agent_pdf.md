# Completed: Agent PDF Attachment Support

## Goal

Enable agent attachments to accept PDF files in addition to images, then expose PDF contents to the model in a multimodal-compatible way.

## Implemented Behavior

1. Backend accepts `application/pdf` attachments (plus existing image attachments).
2. Each PDF is parsed to text using MarkItDown and included in the user message context.
3. If the selected model supports vision, each PDF page is rendered to an image and also attached to the model input.
4. Frontend upload validation now accepts both images and PDFs.
5. Frontend attachment UI supports:
   - image thumbnail previews
   - PDF chips in composer/timeline
   - PDF preview dialog rendering in an iframe

## Affected Files

- Backend:
  - `backend/routers/agent.py`
  - `backend/services/agent/message_history.py`
  - `backend/tests/test_agent.py`
  - `pyproject.toml`
  - `uv.lock`
- Frontend:
  - `frontend/src/components/agent/AgentPanel.tsx`
  - `frontend/src/components/agent/panel/types.ts`
  - `frontend/src/components/agent/panel/useAgentDraftAttachments.ts`
  - `frontend/src/components/agent/panel/AgentComposer.tsx`
  - `frontend/src/components/agent/panel/AgentAttachmentPreviewDialog.tsx`
  - `frontend/src/components/agent/panel/AgentTimeline.tsx`
  - `frontend/src/pages/SettingsPage.tsx`
  - `frontend/src/styles.css`

## Operational Impact

1. New backend dependencies:
   - `markitdown[pdf]`
   - `pymupdf`
2. Existing agent attachment limits still apply:
   - `BILL_HELPER_AGENT_MAX_ATTACHMENTS_PER_MESSAGE`
   - `BILL_HELPER_AGENT_MAX_ATTACHMENT_SIZE_MB`
3. Validation/tests run with:
   - `uv run --extra dev pytest`
   - `cd frontend && npm run test`
   - `cd frontend && npm run build`
   - `uv run python scripts/check_docs_sync.py`

## Constraints

1. PDFs are treated as attachments only (no change to external API shape beyond accepted MIME types).
2. If vision is not supported for the current model, only parsed PDF text is sent to the model.




