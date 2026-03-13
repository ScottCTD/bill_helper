/**
 * CALLING SPEC:
 * - Purpose: render the `SnapshotHistoryTable` React UI module.
 * - Inputs: callers that import `frontend/src/features/accounts/SnapshotHistoryTable.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `SnapshotHistoryTable`.
 * - Side effects: React rendering and user event wiring.
 */
import { DeleteIconButton } from "../../components/DeleteIconButton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { formatMinor } from "../../lib/format";
import type { Account, Snapshot } from "../../lib/types";
import { toDateLabel } from "./helpers";

interface SnapshotHistoryTableProps {
  selectedAccount: Account | null;
  snapshots: Snapshot[] | undefined;
  isLoading: boolean;
  errorMessage: string | null;
  onDeleteSnapshot: (snapshotId: string) => void;
}

export function SnapshotHistoryTable(props: SnapshotHistoryTableProps) {
  const { selectedAccount, snapshots, isLoading, errorMessage, onDeleteSnapshot } = props;

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Snapshot history</h3>

      {!selectedAccount ? <p className="muted">Open an account to review snapshots.</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}
      {isLoading ? <p>Loading snapshots...</p> : null}

      {selectedAccount && !errorMessage && !isLoading ? (
        snapshots?.length ? (
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
        )
      ) : null}
    </div>
  );
}
