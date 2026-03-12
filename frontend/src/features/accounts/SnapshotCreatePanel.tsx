import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import { Button } from "../../components/ui/button";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import type { Account } from "../../lib/types";
import type { SnapshotFormState } from "./types";

interface SnapshotCreatePanelProps {
  selectedAccount: Account | null;
  snapshotForm: SnapshotFormState;
  onSnapshotFormChange: (next: SnapshotFormState) => void;
  onCreateSnapshot: (event: FormEvent<HTMLFormElement>) => void;
  formErrorMessage: string | null;
  createErrorMessage: string | null;
  isCreating: boolean;
}

export function SnapshotCreatePanel(props: SnapshotCreatePanelProps) {
  const {
    selectedAccount,
    snapshotForm,
    onSnapshotFormChange,
    onCreateSnapshot,
    formErrorMessage,
    createErrorMessage,
    isCreating
  } = props;

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Add snapshot</h3>

      {selectedAccount ? (
        <>
          <form className="grid gap-4" onSubmit={onCreateSnapshot}>
            <FormField label="Snapshot date">
              <Input
                type="date"
                required
                value={snapshotForm.snapshot_at}
                onChange={(event) => onSnapshotFormChange({ ...snapshotForm, snapshot_at: event.target.value })}
              />
            </FormField>
            <FormField label={`Balance (${selectedAccount.currency_code})`}>
              <Input
                type="number"
                step="0.01"
                required
                value={snapshotForm.balance_major}
                onChange={(event) => onSnapshotFormChange({ ...snapshotForm, balance_major: event.target.value })}
              />
            </FormField>
            <FormField label="Note">
              <Input value={snapshotForm.note} onChange={(event) => onSnapshotFormChange({ ...snapshotForm, note: event.target.value })} />
            </FormField>
            <Button type="submit" disabled={isCreating}>
              <Plus className="mr-2 h-4 w-4" />
              {isCreating ? "Adding..." : "Add snapshot"}
            </Button>
          </form>

          {formErrorMessage ? <p className="error">{formErrorMessage}</p> : null}
          {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
        </>
      ) : (
        <p className="muted">Open an account to add a snapshot.</p>
      )}
    </div>
  );
}
