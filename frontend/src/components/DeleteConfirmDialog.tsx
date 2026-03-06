import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "./ui/dialog";

interface DeleteConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  isPending: boolean;
  onConfirm: () => void;
  errorMessage?: string | null;
  blockMessage?: string | null;
  warnings?: string[];
}

export function DeleteConfirmDialog(props: DeleteConfirmDialogProps) {
  const {
    open,
    onOpenChange,
    title,
    description,
    confirmLabel,
    isPending,
    onConfirm,
    errorMessage,
    blockMessage,
    warnings = []
  } = props;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 text-sm text-foreground">
          {warnings.length > 0 ? (
            <div className="grid gap-1.5">
              {warnings.map((warning) => (
                <p key={warning} className="muted">
                  {warning}
                </p>
              ))}
            </div>
          ) : null}
          {blockMessage ? <p className="error">{blockMessage}</p> : null}
          {errorMessage ? <p className="error">{errorMessage}</p> : null}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={isPending || Boolean(blockMessage)}>
            {isPending ? "Deleting..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
