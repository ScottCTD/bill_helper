import { StatBlock } from "../../components/layout/StatBlock";
import { Badge } from "../../components/ui/badge";
import type { Account, Reconciliation, ReconciliationInterval } from "../../lib/types";
import { formatMinor } from "../../lib/format";

interface ReconciliationSectionProps {
  account: Account | null;
  reconciliation: Reconciliation | undefined;
  isLoading: boolean;
  errorMessage: string | null;
}

function intervalDateRange(interval: ReconciliationInterval, asOf: string): string {
  const endLabel = interval.is_open ? asOf : interval.end_snapshot?.snapshot_at ?? asOf;
  return `${interval.start_snapshot.snapshot_at} -> ${endLabel}`;
}

function deltaLabel(deltaMinor: number, currencyCode: string): string {
  if (deltaMinor === 0) {
    return "Reconciled";
  }
  const amount = formatMinor(deltaMinor, currencyCode);
  return deltaMinor > 0 ? `${amount} untracked` : `${amount} over-tracked`;
}

export function ReconciliationSection(props: ReconciliationSectionProps) {
  const { account, reconciliation, isLoading, errorMessage } = props;

  if (!account) {
    return <p className="muted">Open an account to review its reconciliation intervals.</p>;
  }

  if (isLoading) {
    return <p>Loading reconciliation...</p>;
  }

  if (errorMessage) {
    return <p className="error">{errorMessage}</p>;
  }

  if (!reconciliation || reconciliation.intervals.length === 0) {
    return (
      <div className="space-y-3">
        <p className="muted">
          Add a snapshot to establish an opening balance. Reconciliation compares entry changes between consecutive
          snapshots rather than comparing your whole ledger against one balance checkpoint.
        </p>
        <p className="text-xs text-muted-foreground">
          Entries on a snapshot date belong to the interval ending at that snapshot.
        </p>
      </div>
    );
  }

  const newestFirstIntervals = [...reconciliation.intervals].reverse();
  const closedIntervals = reconciliation.intervals.filter((interval) => !interval.is_open);
  const openInterval = reconciliation.intervals.find((interval) => interval.is_open) ?? null;
  const reconciledCount = closedIntervals.filter((interval) => interval.delta_minor === 0).length;
  const mismatchedCount = closedIntervals.length - reconciledCount;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <StatBlock label="Intervals" value={reconciliation.intervals.length} />
        <StatBlock label="Reconciled" value={reconciledCount} tone="success" />
        <StatBlock
          label="Current period"
          value={openInterval ? formatMinor(openInterval.tracked_change_minor, reconciliation.currency_code) : "-"}
          detail={`${mismatchedCount} mismatched closed interval(s)`}
          tone="warning"
        />
      </div>

      <div className="space-y-3">
        {newestFirstIntervals.map((interval) => {
          const isReconciled = !interval.is_open && interval.delta_minor === 0;
          const isMismatch = !interval.is_open && interval.delta_minor !== 0;

          return (
            <article
              key={`${interval.start_snapshot.id}:${interval.end_snapshot?.id ?? "open"}`}
              className={[
                "rounded-lg border p-4",
                interval.is_open
                  ? "border-primary/20 bg-primary/8"
                  : isMismatch
                    ? "border-warning/25 bg-warning/10"
                    : "border-success/25 bg-success/10"
              ].join(" ")}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{intervalDateRange(interval, reconciliation.as_of)}</p>
                  <p className="text-xs text-muted-foreground">
                    {interval.entry_count} entr{interval.entry_count === 1 ? "y" : "ies"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {interval.is_open ? <Badge variant="outline">Current period</Badge> : null}
                  {isReconciled ? <Badge variant="outline">Reconciled</Badge> : null}
                  {isMismatch ? <Badge variant="outline">Mismatch</Badge> : null}
                </div>
              </div>

              {isReconciled ? (
                <p className="mt-3 text-sm text-success-foreground">Tracked change matches the bank checkpoints for this interval.</p>
              ) : (
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-[12px] font-medium text-muted-foreground">Tracked</dt>
                    <dd className="mt-1 font-medium">
                      {formatMinor(interval.tracked_change_minor, reconciliation.currency_code)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[12px] font-medium text-muted-foreground">Bank</dt>
                    <dd className="mt-1 font-medium">
                      {interval.bank_change_minor === null
                        ? "Waiting for next snapshot"
                        : formatMinor(interval.bank_change_minor, reconciliation.currency_code)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[12px] font-medium text-muted-foreground">
                      {interval.is_open ? "Status" : "Delta"}
                    </dt>
                    <dd className="mt-1 font-medium">
                      {interval.delta_minor === null
                        ? "No closing bank checkpoint yet"
                        : deltaLabel(interval.delta_minor, reconciliation.currency_code)}
                    </dd>
                  </div>
                </dl>
              )}
            </article>
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        Entries on a snapshot date belong to the interval ending at that snapshot.
      </p>
    </div>
  );
}
