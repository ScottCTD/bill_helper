/**
 * CALLING SPEC:
 * - Purpose: render a compact attachment row with an open action.
 * - Inputs: callers that import `frontend/src/features/agent/panel/AgentAttachmentFileRow.tsx` and pass row metadata.
 * - Outputs: React components exported by `AgentAttachmentFileRow`.
 * - Side effects: may open a browser tab/window when the action is pressed.
 */
import type { LucideIcon } from "lucide-react";

import { Button } from "../../../components/ui/button";

interface AgentAttachmentFileRowProps {
  fileLabel: string;
  icon: LucideIcon;
  onOpen?: () => void;
}

export function AgentAttachmentFileRow({ fileLabel, icon: Icon, onOpen }: AgentAttachmentFileRowProps) {
  return (
    <div className="agent-message-attachment-row">
      <div className="agent-message-attachment-row-meta">
        <Icon className="h-4 w-4" />
        <span>{fileLabel}</span>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="agent-message-attachment-open-button"
        onClick={onOpen}
        disabled={!onOpen}
        aria-label={`Open ${fileLabel}`}
      >
        Open
      </Button>
    </div>
  );
}
