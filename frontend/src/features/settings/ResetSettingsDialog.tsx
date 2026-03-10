import { Button } from "../../components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../../components/ui/dialog";

interface ResetSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isPending: boolean;
}

export function ResetSettingsDialog({ open, onOpenChange, onConfirm, isPending }: ResetSettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Reset all runtime overrides?</DialogTitle>
          <DialogDescription>
            This clears saved runtime overrides and restores the effective values from the server configuration.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 text-sm text-foreground">
          <p className="muted">
            This affects currencies, agent models and memory, provider overrides, bulk limits, attachment limits, and
            reliability settings.
          </p>
          <p className="muted">Use this when you want the app to follow the server defaults again.</p>
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" disabled={isPending} onClick={onConfirm}>
            {isPending ? "Resetting..." : "Reset to server defaults"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
