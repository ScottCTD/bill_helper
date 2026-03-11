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
        <div className="rounded-xl border border-border/70 bg-muted/25 p-3">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Intervals</p>
          <p className="mt-2 text-2xl font-semibold">{reconciliation.intervals.length}</p>
        </div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3">
          <p className="text-xs uppercase tracking-[0.2em] text-emerald-700">Reconciled</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-900">{reconciledCount}</p>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3">
          <p className="text-xs uppercase tracking-[0.2em] text-amber-700">Current Period</p>
          <p className="mt-2 text-2xl font-semibold text-amber-950">
            {openInterval ? formatMinor(openInterval.tracked_change_minor, reconciliation.currency_code) : "-"}
          </p>
          <p className="mt-1 text-xs text-amber-800">{mismatchedCount} mismatched closed interval(s)</p>
        </div>
      </div>

      <div className="space-y-3">
        {newestFirstIntervals.map((interval) => {
          const isReconciled = !interval.is_open && interval.delta_minor === 0;
          const isMismatch = !interval.is_open && interval.delta_minor !== 0;

          return (
            <article
              key={`${interval.start_snapshot.id}:${interval.end_snapshot?.id ?? "open"}`}
              className={[
                "rounded-xl border p-4",
                interval.is_open
                  ? "border-sky-200 bg-sky-50/70"
                  : isMismatch
                    ? "border-amber-200 bg-amber-50/70"
                    : "border-emerald-200 bg-emerald-50/60"
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
                <p className="mt-3 text-sm text-emerald-900">Tracked change matches the bank checkpoints for this interval.</p>
              ) : (
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Tracked</dt>
                    <dd className="mt-1 font-medium">
                      {formatMinor(interval.tracked_change_minor, reconciliation.currency_code)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Bank</dt>
                    <dd className="mt-1 font-medium">
                      {interval.bank_change_minor === null
                        ? "Waiting for next snapshot"
                        : formatMinor(interval.bank_change_minor, reconciliation.currency_code)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
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
