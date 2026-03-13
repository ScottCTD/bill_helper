/**
 * CALLING SPEC:
 * - Purpose: expose account, snapshot, and reconciliation API calls for the frontend.
 * - Inputs: account ids, snapshot ids, and account mutation payloads.
 * - Outputs: account-domain read models or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type { Account, Reconciliation, Snapshot } from "../types";
import { request } from "./core";

export function listAccounts(): Promise<Account[]> {
  return request<Account[]>("/api/v1/accounts");
}

export function createAccount(payload: {
  owner_user_id: string;
  name: string;
  markdown_body?: string | null;
  currency_code: string;
  is_active?: boolean;
}): Promise<Account> {
  return request<Account>("/api/v1/accounts", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAccount(accountId: string, payload: Partial<Account>): Promise<Account> {
  return request<Account>(`/api/v1/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteAccount(accountId: string): Promise<void> {
  return request<void>(`/api/v1/accounts/${accountId}`, {
    method: "DELETE"
  });
}

export function createSnapshot(
  accountId: string,
  payload: { snapshot_at: string; balance_minor: number; note?: string }
): Promise<Snapshot> {
  return request<Snapshot>(`/api/v1/accounts/${accountId}/snapshots`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listSnapshots(accountId: string): Promise<Snapshot[]> {
  return request<Snapshot[]>(`/api/v1/accounts/${accountId}/snapshots`);
}

export function deleteSnapshot(accountId: string, snapshotId: string): Promise<void> {
  return request<void>(`/api/v1/accounts/${accountId}/snapshots/${snapshotId}`, {
    method: "DELETE"
  });
}

export function getReconciliation(accountId: string, asOf?: string): Promise<Reconciliation> {
  const params = new URLSearchParams();
  if (asOf) {
    params.set("as_of", asOf);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";
  return request<Reconciliation>(`/api/v1/accounts/${accountId}/reconciliation${suffix}`);
}
