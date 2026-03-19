/**
 * CALLING SPEC:
 * - Purpose: render authenticated inline PDF previews for persisted agent message attachments.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentMessageAttachmentPdf.tsx` and pass module-defined props.
 * - Outputs: React components exported by `AgentMessageAttachmentPdf`.
 * - Side effects: authenticated attachment fetches through `useAgentAttachmentObjectUrl`.
 */
import { FileText } from "lucide-react";

import { AgentAttachmentPdfCard } from "./AgentAttachmentPdfCard";
import { useAgentAttachmentObjectUrl } from "./useAgentAttachmentObjectUrl";

interface AgentMessageAttachmentPdfProps {
  attachmentUrl: string;
  title: string;
}

export function AgentMessageAttachmentPdf({ attachmentUrl, title }: AgentMessageAttachmentPdfProps) {
  const { objectUrl, hasFailed } = useAgentAttachmentObjectUrl(attachmentUrl);

  if (objectUrl) {
    return <AgentAttachmentPdfCard previewUrl={objectUrl} title={title} />;
  }

  if (hasFailed) {
    return (
      <div className="agent-message-attachment-file" role="img" aria-label={`${title} preview unavailable`}>
        <FileText className="h-4 w-4" />
        <span>{title}</span>
      </div>
    );
  }

  return <div className="agent-message-attachment-pdf agent-message-attachment-pdf-loading" aria-hidden="true" />;
}
