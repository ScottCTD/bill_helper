/**
 * CALLING SPEC:
 * - Purpose: render a compact authenticated attachment row for persisted agent message attachments.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentMessageAttachmentRow.tsx` and pass module-defined props.
 * - Outputs: React components exported by `AgentMessageAttachmentRow`.
 * - Side effects: authenticated attachment fetches through `useAgentAttachmentObjectUrl`.
 */
import { FileImage, FileText } from "lucide-react";

import { openAttachmentInNewTab } from "./attachmentBrowserOpen";
import { AgentAttachmentFileRow } from "./AgentAttachmentFileRow";
import { useAgentAttachmentObjectUrl } from "./useAgentAttachmentObjectUrl";

interface AgentMessageAttachmentRowProps {
  attachmentUrl: string;
  fileLabel: string;
  mimeType: string;
}

export function AgentMessageAttachmentRow({
  attachmentUrl,
  fileLabel,
  mimeType
}: AgentMessageAttachmentRowProps) {
  const { objectUrl } = useAgentAttachmentObjectUrl(attachmentUrl);
  const Icon = mimeType.toLowerCase().startsWith("image/") ? FileImage : FileText;

  return (
    <AgentAttachmentFileRow
      fileLabel={fileLabel}
      icon={Icon}
      onOpen={objectUrl ? () => openAttachmentInNewTab(objectUrl) : undefined}
    />
  );
}
