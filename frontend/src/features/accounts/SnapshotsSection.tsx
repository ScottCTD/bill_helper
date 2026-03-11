import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import { DeleteIconButton } from "../../components/DeleteIconButton";
import type { Account, Snapshot } from "../../lib/types";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
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
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title text-base">Snapshots</h3>
            <p className="table-shell-subtitle">
              A snapshot is a balance checkpoint copied from your bank on a specific day. Add one each time you want a fresh
              reference point.
            </p>
          </div>
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
              <dd className="inline"> optional context like statement name, transfer timing, or pending transactions.</dd>
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
              <div className="full-row flex items-end gap-3">
                <FormField label="Note" className="min-w-0 flex-1">
                  <Input
                    value={snapshotForm.note}
                    onChange={(event) => onSnapshotFormChange({ ...snapshotForm, note: event.target.value })}
                  />
                </FormField>
                <Button type="submit" size="icon" variant="outline" aria-label="Add snapshot" disabled={isCreating}>
                  <Plus className="h-4 w-4" />
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
                          <DeleteIconButton
                            label={`Delete snapshot ${snapshot.snapshot_at}`}
                            onClick={() => onDeleteSnapshot(snapshot.id)}
                          />
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
          <p className="muted">Select an account from the table to add or review snapshots.</p>
        )}
      </CardContent>
    </Card>
  );
}
