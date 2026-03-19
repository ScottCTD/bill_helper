/**
 * CALLING SPEC:
 * - Purpose: render authenticated inline image previews for persisted agent message attachments.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentMessageAttachmentImage.tsx` and pass module-defined props.
 * - Outputs: React components exported by `AgentMessageAttachmentImage`.
 * - Side effects: authenticated attachment fetches through `useAgentAttachmentObjectUrl`.
 */
import { FileImage } from "lucide-react";

import { AgentAttachmentImageCard } from "./AgentAttachmentImageCard";
import { useAgentAttachmentObjectUrl } from "./useAgentAttachmentObjectUrl";

interface AgentMessageAttachmentImageProps {
  alt: string;
  attachmentUrl: string;
}

export function AgentMessageAttachmentImage({ alt, attachmentUrl }: AgentMessageAttachmentImageProps) {
  const { objectUrl, hasFailed } = useAgentAttachmentObjectUrl(attachmentUrl);

  if (objectUrl) {
    return <AgentAttachmentImageCard alt={alt} previewUrl={objectUrl} />;
  }

  if (hasFailed) {
    return (
      <div className="agent-message-attachment-file" role="img" aria-label={`${alt} preview unavailable`}>
        <FileImage className="h-4 w-4" />
        <span>{alt}</span>
      </div>
    );
  }

  return <div className="agent-message-attachment-image agent-message-attachment-image-loading" aria-hidden="true" />;
}
