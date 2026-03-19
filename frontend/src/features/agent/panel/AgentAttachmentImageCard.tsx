/**
 * CALLING SPEC:
 * - Purpose: render an inline image attachment card with browser-native open behavior.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentAttachmentImageCard.tsx` and pass a preview URL plus display name.
 * - Outputs: React components exported by `AgentAttachmentImageCard`.
 * - Side effects: may open a browser tab when clicked.
 */
import { Expand } from "lucide-react";

import { openAttachmentInNewTab } from "./attachmentBrowserOpen";

interface AgentAttachmentImageCardProps {
  alt: string;
  previewUrl: string;
}

export function AgentAttachmentImageCard({ alt, previewUrl }: AgentAttachmentImageCardProps) {
  return (
    <button
      type="button"
      className="agent-message-attachment-image-card"
      onClick={() => openAttachmentInNewTab(previewUrl)}
      aria-label={`Open ${alt}`}
      title={`Open ${alt}`}
    >
      <img className="agent-message-attachment-image" src={previewUrl} alt={alt} loading="lazy" />
      <span className="agent-message-attachment-open-chip" aria-hidden="true">
        <Expand className="h-3.5 w-3.5" />
        Open
      </span>
    </button>
  );
}
