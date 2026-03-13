/**
 * CALLING SPEC:
 * - Purpose: define account, snapshot, and reconciliation read models for the frontend.
 * - Inputs: frontend modules that display account balances, snapshots, and reconciliation summaries.
 * - Outputs: account-domain interfaces.
 * - Side effects: type declarations only.
 */

export interface Account {
  id: string;
  owner_user_id: string;
  name: string;
  markdown_body: string | null;
  currency_code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Snapshot {
  id: string;
  account_id: string;
  snapshot_at: string;
  balance_minor: number;
  note: string | null;
  created_at: string;
}

export interface SnapshotSummary {
  id: string;
  snapshot_at: string;
  balance_minor: number;
  note: string | null;
}

export interface ReconciliationInterval {
  start_snapshot: SnapshotSummary;
  end_snapshot: SnapshotSummary | null;
  is_open: boolean;
  tracked_change_minor: number;
  bank_change_minor: number | null;
  delta_minor: number | null;
  entry_count: number;
}

export interface Reconciliation {
  account_id: string;
  account_name: string;
  currency_code: string;
  as_of: string;
  intervals: ReconciliationInterval[];
}

export interface DashboardReconciliation {
  account_id: string;
  account_name: string;
  currency_code: string;
  latest_snapshot_at: string | null;
  current_tracked_change_minor: number | null;
  last_closed_delta_minor: number | null;
  mismatched_interval_count: number;
  reconciled_interval_count: number;
}
