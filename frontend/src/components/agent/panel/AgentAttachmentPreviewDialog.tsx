import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../../ui/dialog";
import type { DraftAttachmentPreview } from "./types";

interface AgentAttachmentPreviewDialogProps {
  preview: DraftAttachmentPreview | null;
  onClose: () => void;
}

export function AgentAttachmentPreviewDialog(props: AgentAttachmentPreviewDialogProps) {
  const { preview, onClose } = props;

  return (
    <Dialog
      open={Boolean(preview)}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) {
          onClose();
        }
      }}
    >
      <DialogContent className="agent-attachment-preview-dialog">
        <DialogHeader>
          <DialogTitle>{preview?.file.name ?? "Attachment preview"}</DialogTitle>
        </DialogHeader>
        {preview ? <img src={preview.url} alt={preview.file.name} className="agent-attachment-preview-image" /> : null}
      </DialogContent>
    </Dialog>
  );
}
