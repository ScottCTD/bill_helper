import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import { DeleteIconButton } from "../../components/DeleteIconButton";
import type { Account, Snapshot } from "../../lib/types";
import { Button } from "../../components/ui/button";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { formatMinor } from "../../lib/format";
import { toDateLabel } from "./helpers";
import type { SnapshotFormState } from "./types";

interface SnapshotsSectionProps {
  selectedAccount: Account | null;
  snapshotForm: SnapshotFormState;
  onSnapshotFormChange: (next: SnapshotFormState) => void;
  onCreateSnapshot: (event: FormEvent<HTMLFormElement>) => void;
  onDeleteSnapshot: (snapshotId: string) => void;
  snapshots: Snapshot[] | undefined;
  isLoading: boolean;
  errorMessage: string | null;
  formErrorMessage: string | null;
  createErrorMessage: string | null;
  isCreating: boolean;
}

export function SnapshotsSection(props: SnapshotsSectionProps) {
  const {
    selectedAccount,
    snapshotForm,
    onSnapshotFormChange,
    onCreateSnapshot,
    onDeleteSnapshot,
    snapshots,
    isLoading,
    errorMessage,
    formErrorMessage,
    createErrorMessage,
    isCreating
  } = props;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h3 className="text-base font-semibold">Snapshots</h3>
        <p className="text-sm text-muted-foreground">
          Record bank balance checkpoints here. Reconciliation compares tracked entry changes between consecutive
          snapshots, so you only need an opening checkpoint and then new checkpoints whenever you want to verify a period.
        </p>
      </div>

      <div className="rounded-lg border border-border/75 bg-muted/25 p-3 text-sm">
        <p className="font-medium">How to use snapshots</p>
        <dl className="mt-2 grid gap-1.5 text-muted-foreground">
          <div>
            <dt className="inline font-medium text-foreground">Snapshot date:</dt>
            <dd className="inline"> the day the bank balance is true for.</dd>
          </div>
          <div>
            <dt className="inline font-medium text-foreground">Balance:</dt>
            <dd className="inline"> the exact amount shown by your bank on that day.</dd>
          </div>
          <div>
            <dt className="inline font-medium text-foreground">Note:</dt>
            <dd className="inline"> optional context like statement name, pending transfers, or cutoff timing.</dd>
          </div>
        </dl>
      </div>

      {selectedAccount ? (
        <>
          <form className="form-grid" onSubmit={onCreateSnapshot}>
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
            <div className="full-row flex flex-col gap-3 md:flex-row md:items-end">
              <FormField label="Note" className="min-w-0 flex-1">
                <Input
                  value={snapshotForm.note}
                  onChange={(event) => onSnapshotFormChange({ ...snapshotForm, note: event.target.value })}
                />
              </FormField>
              <Button type="submit" variant="outline" disabled={isCreating}>
                <Plus className="mr-2 h-4 w-4" />
                {isCreating ? "Adding..." : "Add snapshot"}
              </Button>
            </div>
          </form>

          {formErrorMessage ? <p className="error">{formErrorMessage}</p> : null}
          {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
          {errorMessage ? <p className="error">{errorMessage}</p> : null}
          {isLoading ? <p>Loading snapshots...</p> : null}

          {snapshots?.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Balance</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead>Added</TableHead>
                  <TableHead className="icon-action-column">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshots.map((snapshot) => (
                  <TableRow key={snapshot.id}>
                    <TableCell>{snapshot.snapshot_at}</TableCell>
                    <TableCell>{formatMinor(snapshot.balance_minor, selectedAccount.currency_code)}</TableCell>
                    <TableCell>{snapshot.note ?? "-"}</TableCell>
                    <TableCell>{toDateLabel(snapshot.created_at)}</TableCell>
                    <TableCell className="icon-action-column">
                      <div className="table-actions">
                        <DeleteIconButton label={`Delete snapshot ${snapshot.snapshot_at}`} onClick={() => onDeleteSnapshot(snapshot.id)} />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="muted">No snapshots yet.</p>
          )}
        </>
      ) : (
        <p className="muted">Open an account to add or review snapshots.</p>
      )}
    </div>
  );
}
