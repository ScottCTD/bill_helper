/**
 * CALLING SPEC:
 * - Purpose: render a small inline browser PDF preview card.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentAttachmentPdfCard.tsx` and pass a PDF URL plus display name.
 * - Outputs: React components exported by `AgentAttachmentPdfCard`.
 * - Side effects: React rendering only.
 */
import { FileText } from "lucide-react";

import { Button } from "../../../components/ui/button";
import { openAttachmentInNewTab } from "./attachmentBrowserOpen";

interface AgentAttachmentPdfCardProps {
  previewUrl: string;
  title: string;
}

export function AgentAttachmentPdfCard({ previewUrl, title }: AgentAttachmentPdfCardProps) {
  const iframeUrl = `${previewUrl}#toolbar=0&navpanes=0`;

  return (
    <div className="agent-message-attachment-pdf">
      <div className="agent-message-attachment-pdf-frame">
        <iframe
          className="agent-message-attachment-pdf-embed"
          src={iframeUrl}
          title={title}
          loading="lazy"
          tabIndex={-1}
          scrolling="auto"
        />
      </div>
      <div className="agent-message-attachment-pdf-label">
        <div className="agent-message-attachment-pdf-meta">
          <FileText className="h-4 w-4" />
          <span>{title}</span>
        </div>
        <Button type="button" variant="ghost" size="sm" className="agent-message-attachment-open-button" onClick={() => openAttachmentInNewTab(previewUrl)}>
          Open
        </Button>
      </div>
    </div>
  );
}
