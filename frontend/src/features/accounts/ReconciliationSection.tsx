import type { Account, Reconciliation } from "../../lib/types";
import { Card, CardContent } from "../../components/ui/card";
import { formatMinor } from "../../lib/format";

interface ReconciliationSectionProps {
  selectedAccount: Account | null;
  reconciliation: Reconciliation | undefined;
  isLoading: boolean;
  errorMessage: string | null;
}

export function ReconciliationSection(props: ReconciliationSectionProps) {
  const { selectedAccount, reconciliation, isLoading, errorMessage } = props;

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="table-shell-header">
          <div>
            <h3 className="table-shell-title text-base">Reconciliation</h3>
            <p className="table-shell-subtitle">Compare your running ledger with the latest bank checkpoint for this account.</p>
          </div>
        </div>
        <div className="rounded-lg border border-border/75 bg-muted/25 p-3 text-sm">
          <p className="font-medium">What these terms mean</p>
          <dl className="mt-2 grid gap-1.5 text-muted-foreground">
            <div>
              <dt className="inline font-medium text-foreground">As of:</dt>
              <dd className="inline"> the date this comparison is calculated for.</dd>
            </div>
            <div>
              <dt className="inline font-medium text-foreground">Ledger:</dt>
              <dd className="inline"> what your entries add up to by that date.</dd>
            </div>
            <div>
              <dt className="inline font-medium text-foreground">Snapshot:</dt>
              <dd className="inline"> the last balance you recorded from your bank, on or before that date.</dd>
            </div>
            <div>
              <dt className="inline font-medium text-foreground">Delta:</dt>
              <dd className="inline"> ledger minus snapshot. A value near 0 means things are in sync.</dd>
            </div>
          </dl>
        </div>

        {selectedAccount ? (
          <>
            {isLoading ? <p>Loading reconciliation...</p> : null}
            {errorMessage ? <p className="error">{errorMessage}</p> : null}
            {reconciliation ? (
              <ul className="key-value-list">
                <li>
                  <span>As of</span>
                  <strong>{reconciliation.as_of}</strong>
                </li>
                <li>
                  <span>Ledger</span>
                  <strong>{formatMinor(reconciliation.ledger_balance_minor, reconciliation.currency_code)}</strong>
                </li>
                <li>
                  <span>Snapshot</span>
                  <strong>
                    {reconciliation.snapshot_balance_minor === null
                      ? "-"
                      : formatMinor(reconciliation.snapshot_balance_minor, reconciliation.currency_code)}
                  </strong>
                </li>
                <li>
                  <span>Snapshot date</span>
                  <strong>{reconciliation.snapshot_at ?? "-"}</strong>
                </li>
                <li>
                  <span>Delta</span>
                  <strong>
                    {reconciliation.delta_minor === null ? "-" : formatMinor(reconciliation.delta_minor, reconciliation.currency_code)}
                  </strong>
                </li>
              </ul>
            ) : null}
          </>
        ) : (
          <p className="muted">Select an account from the table to view reconciliation details.</p>
        )}
      </CardContent>
    </Card>
  );
}
