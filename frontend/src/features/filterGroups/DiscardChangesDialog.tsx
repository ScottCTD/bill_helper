/**
 * CALLING SPEC:
 * - Purpose: render the local discard-confirmation dialog used by the filters workspace.
 * - Inputs: callers that provide open state and discard/cancel handlers.
 * - Outputs: React UI for confirming unsaved-change loss.
 * - Side effects: React rendering and user event wiring.
 */
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../../components/ui/dialog";

interface DiscardChangesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

export function DiscardChangesDialog({ open, onOpenChange, onConfirm }: DiscardChangesDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Discard unsaved changes?</DialogTitle>
          <DialogDescription>Your current filter-group edits will be lost if you continue.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Keep editing
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            Discard changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
