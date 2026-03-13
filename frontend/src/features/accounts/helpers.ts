/**
 * CALLING SPEC:
 * - Purpose: provide the `helpers` frontend module.
 * - Inputs: callers that import `frontend/src/features/accounts/helpers.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `helpers`.
 * - Side effects: module-local frontend behavior only.
 */
import type { Account, Snapshot } from "../../lib/types";
import type { AccountFormState } from "./types";

export function toDateLabel(value: string) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

export function normalizeOptionalText(value: string): string | undefined {
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

export function normalizeNullableMarkdown(value: string): string | null {
  if (value.trim().length === 0) {
    return null;
  }
  return value;
}

export function buildEditForm(account: Account): AccountFormState {
  return {
    owner_user_id: account.owner_user_id,
    name: account.name,
    markdown_body: account.markdown_body ?? "",
    currency_code: account.currency_code,
    is_active: account.is_active
  };
}

export interface SnapshotNeighbors {
  current: Snapshot;
  previous: Snapshot | null;
  next: Snapshot | null;
  total: number;
}

export function findSnapshotNeighbors(snapshots: Snapshot[], snapshotId: string): SnapshotNeighbors | null {
  const ordered = [...snapshots].sort((left, right) => {
    if (left.snapshot_at !== right.snapshot_at) {
      return left.snapshot_at.localeCompare(right.snapshot_at);
    }
    return left.created_at.localeCompare(right.created_at);
  });
  const index = ordered.findIndex((snapshot) => snapshot.id === snapshotId);
  if (index < 0) {
    return null;
  }
  return {
    current: ordered[index],
    previous: index > 0 ? ordered[index - 1] : null,
    next: index + 1 < ordered.length ? ordered[index + 1] : null,
    total: ordered.length
  };
}

export function buildSnapshotDeletionImpact(snapshots: Snapshot[], snapshotId: string): string[] {
  const neighbors = findSnapshotNeighbors(snapshots, snapshotId);
  if (!neighbors) {
    return [
      "This action cannot be undone.",
      "Reconciliation history will update immediately after the snapshot is removed."
    ];
  }

  if (neighbors.total === 1) {
    return [
      "This is the only snapshot for this account.",
      "Deleting it removes the opening balance anchor for interval reconciliation."
    ];
  }

  if (neighbors.previous && neighbors.next) {
    return [
      `Deleting ${neighbors.current.snapshot_at} merges intervals ${neighbors.previous.snapshot_at} -> ${neighbors.current.snapshot_at} and ${neighbors.current.snapshot_at} -> ${neighbors.next.snapshot_at}.`,
      `The merged interval will run ${neighbors.previous.snapshot_at} -> ${neighbors.next.snapshot_at}.`
    ];
  }

  if (neighbors.previous) {
    return [
      `Deleting ${neighbors.current.snapshot_at} makes ${neighbors.previous.snapshot_at} the new baseline for the open interval.`,
      "Tracked activity since that earlier checkpoint will remain visible."
    ];
  }

  if (neighbors.next) {
    return [
      `Deleting ${neighbors.current.snapshot_at} removes the earliest checkpoint.`,
      `${neighbors.next.snapshot_at} becomes the first remaining snapshot for this account.`
    ];
  }

  return [
    "This action cannot be undone.",
    "Reconciliation history will update immediately after the snapshot is removed."
  ];
}
