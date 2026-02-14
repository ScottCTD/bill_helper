import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createAccount,
  createSnapshot,
  getRuntimeSettings,
  getReconciliation,
  listAccounts,
  listCurrencies,
  listUsers,
  listSnapshots,
  updateAccount
} from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateAccountReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";

export function AccountsPage() {
  const queryClient = useQueryClient();
  const accountsQuery = useQuery({ queryKey: queryKeys.accounts.all, queryFn: listAccounts });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [createForm, setCreateForm] = useState({
    owner_user_id: "",
    name: "",
    institution: "",
    account_type: "",
    currency_code: "CAD"
  });
  const [editForm, setEditForm] = useState({
    owner_user_id: "",
    name: "",
    institution: "",
    account_type: "",
    currency_code: "CAD",
    is_active: true
  });
  const [snapshotForm, setSnapshotForm] = useState({
    snapshot_at: new Date().toISOString().slice(0, 10),
    balance_major: "",
    note: ""
  });
  const [createCurrencyInitialized, setCreateCurrencyInitialized] = useState(false);

  useEffect(() => {
    if (!selectedAccountId && accountsQuery.data && accountsQuery.data.length > 0) {
      setSelectedAccountId(accountsQuery.data[0].id);
    }
  }, [accountsQuery.data, selectedAccountId]);

  const selectedAccount = accountsQuery.data?.find((account) => account.id === selectedAccountId);
  const currentUserId = usersQuery.data?.find((user) => user.is_current_user)?.id ?? "";
  const defaultCurrencyCode = (runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase();
  const currencies = useMemo(() => {
    const codes = new Set((currenciesQuery.data ?? []).map((currency) => currency.code));
    if (createForm.currency_code) {
      codes.add(createForm.currency_code.toUpperCase());
    }
    if (editForm.currency_code) {
      codes.add(editForm.currency_code.toUpperCase());
    }
    return Array.from(codes).sort();
  }, [createForm.currency_code, currenciesQuery.data, editForm.currency_code]);

  useEffect(() => {
    if (!currentUserId) {
      return;
    }
    setCreateForm((state) => (state.owner_user_id ? state : { ...state, owner_user_id: currentUserId }));
  }, [currentUserId]);

  useEffect(() => {
    if (createCurrencyInitialized) {
      return;
    }
    if (!defaultCurrencyCode) {
      return;
    }
    setCreateForm((state) => ({ ...state, currency_code: defaultCurrencyCode }));
    setCreateCurrencyInitialized(true);
  }, [createCurrencyInitialized, defaultCurrencyCode]);

  useEffect(() => {
    if (!selectedAccount) {
      return;
    }
    setEditForm({
      owner_user_id: selectedAccount.owner_user_id ?? currentUserId,
      name: selectedAccount.name,
      institution: selectedAccount.institution ?? "",
      account_type: selectedAccount.account_type ?? "",
      currency_code: selectedAccount.currency_code,
      is_active: selectedAccount.is_active
    });
  }, [currentUserId, selectedAccount]);

  const snapshotsQuery = useQuery({
    queryKey: queryKeys.accounts.snapshots(selectedAccountId),
    queryFn: () => listSnapshots(selectedAccountId),
    enabled: Boolean(selectedAccountId)
  });

  const reconciliationQuery = useQuery({
    queryKey: queryKeys.accounts.reconciliation(selectedAccountId),
    queryFn: () => getReconciliation(selectedAccountId),
    enabled: Boolean(selectedAccountId)
  });

  const createAccountMutation = useMutation({
    mutationFn: createAccount,
    onSuccess: () => {
      invalidateAccountReadModels(queryClient);
      setCreateForm({
        owner_user_id: currentUserId,
        name: "",
        institution: "",
        account_type: "",
        currency_code: defaultCurrencyCode
      });
    }
  });

  const updateAccountMutation = useMutation({
    mutationFn: () => updateAccount(selectedAccountId, editForm),
    onSuccess: () => {
      invalidateAccountReadModels(queryClient, selectedAccountId);
    }
  });

  const createSnapshotMutation = useMutation({
    mutationFn: () =>
      createSnapshot(selectedAccountId, {
        snapshot_at: snapshotForm.snapshot_at,
        balance_minor: Math.round(Number(snapshotForm.balance_major) * 100),
        note: snapshotForm.note || undefined
      }),
    onSuccess: () => {
      invalidateAccountReadModels(queryClient, selectedAccountId);
      setSnapshotForm((state) => ({ ...state, balance_major: "", note: "" }));
    }
  });

  function onCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAccountMutation.mutate({
      owner_user_id: createForm.owner_user_id || undefined,
      name: createForm.name,
      institution: createForm.institution || undefined,
      account_type: createForm.account_type || undefined,
      currency_code: createForm.currency_code.toUpperCase(),
      is_active: true
    });
  }

  return (
    <div className="stack-lg">
      <section className="card">
        <h2>Create Account</h2>
        <form className="form-grid" onSubmit={onCreateAccount}>
          <label>
            Owner
            <select
              value={createForm.owner_user_id}
              onChange={(event) => setCreateForm((state) => ({ ...state, owner_user_id: event.target.value }))}
            >
              <option value="">(none)</option>
              {usersQuery.data?.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.name}
                  {user.is_current_user ? " (Current User)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input
              required
              value={createForm.name}
              onChange={(event) => setCreateForm((state) => ({ ...state, name: event.target.value }))}
            />
          </label>
          <label>
            Institution
            <input
              value={createForm.institution}
              onChange={(event) => setCreateForm((state) => ({ ...state, institution: event.target.value }))}
            />
          </label>
          <label>
            Type
            <input
              value={createForm.account_type}
              onChange={(event) => setCreateForm((state) => ({ ...state, account_type: event.target.value }))}
            />
          </label>
          <label>
            Currency
            <select
              value={createForm.currency_code}
              onChange={(event) => setCreateForm((state) => ({ ...state, currency_code: event.target.value }))}
            >
              {currencies.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={createAccountMutation.isPending}>
            {createAccountMutation.isPending ? "Creating..." : "Create Account"}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Accounts</h2>
        {accountsQuery.isLoading ? <p>Loading accounts...</p> : null}
        {accountsQuery.data?.length ? (
          <div className="account-picker">
            {accountsQuery.data.map((account) => (
              <button
                key={account.id}
                type="button"
                className={account.id === selectedAccountId ? "selected" : ""}
                onClick={() => setSelectedAccountId(account.id)}
              >
                {account.name}
              </button>
            ))}
          </div>
        ) : (
          <p className="muted">No accounts yet.</p>
        )}
      </section>

      {selectedAccount ? (
        <section className="grid-2">
          <section className="card">
            <h3>Edit Account</h3>
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                updateAccountMutation.mutate();
              }}
            >
              <label>
                Owner
                <select
                  value={editForm.owner_user_id}
                  onChange={(event) => setEditForm((state) => ({ ...state, owner_user_id: event.target.value }))}
                >
                  <option value="">(none)</option>
                  {usersQuery.data?.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                      {user.is_current_user ? " (Current User)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Name
                <input value={editForm.name} onChange={(event) => setEditForm((state) => ({ ...state, name: event.target.value }))} />
              </label>
              <label>
                Institution
                <input
                  value={editForm.institution}
                  onChange={(event) => setEditForm((state) => ({ ...state, institution: event.target.value }))}
                />
              </label>
              <label>
                Type
                <input
                  value={editForm.account_type}
                  onChange={(event) => setEditForm((state) => ({ ...state, account_type: event.target.value }))}
                />
              </label>
              <label>
                Currency
                <select
                  value={editForm.currency_code}
                  onChange={(event) => setEditForm((state) => ({ ...state, currency_code: event.target.value }))}
                >
                  {currencies.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Active
                <input
                  type="checkbox"
                  checked={editForm.is_active}
                  onChange={(event) => setEditForm((state) => ({ ...state, is_active: event.target.checked }))}
                />
              </label>
              <button type="submit" disabled={updateAccountMutation.isPending}>
                Save account
              </button>
            </form>

            <h3>Reconciliation</h3>
            {reconciliationQuery.data ? (
              <ul className="key-value-list">
                <li>
                  <span>Ledger</span>
                  <strong>{formatMinor(reconciliationQuery.data.ledger_balance_minor, reconciliationQuery.data.currency_code)}</strong>
                </li>
                <li>
                  <span>Snapshot</span>
                  <strong>
                    {reconciliationQuery.data.snapshot_balance_minor === null
                      ? "-"
                      : formatMinor(reconciliationQuery.data.snapshot_balance_minor, reconciliationQuery.data.currency_code)}
                  </strong>
                </li>
                <li>
                  <span>Delta</span>
                  <strong>
                    {reconciliationQuery.data.delta_minor === null
                      ? "-"
                      : formatMinor(reconciliationQuery.data.delta_minor, reconciliationQuery.data.currency_code)}
                  </strong>
                </li>
              </ul>
            ) : (
              <p className="muted">No reconciliation data.</p>
            )}
          </section>

          <section className="card">
            <h3>Add Balance Snapshot</h3>
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                createSnapshotMutation.mutate();
              }}
            >
              <label>
                Snapshot date
                <input
                  type="date"
                  value={snapshotForm.snapshot_at}
                  onChange={(event) => setSnapshotForm((state) => ({ ...state, snapshot_at: event.target.value }))}
                />
              </label>
              <label>
                Balance
                <input
                  type="number"
                  step="0.01"
                  value={snapshotForm.balance_major}
                  onChange={(event) => setSnapshotForm((state) => ({ ...state, balance_major: event.target.value }))}
                />
              </label>
              <label className="full-row">
                Note
                <input
                  value={snapshotForm.note}
                  onChange={(event) => setSnapshotForm((state) => ({ ...state, note: event.target.value }))}
                />
              </label>
              <button type="submit" disabled={createSnapshotMutation.isPending}>
                Add snapshot
              </button>
            </form>

            <h3>Snapshot History</h3>
            {snapshotsQuery.data?.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Balance</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshotsQuery.data.map((snapshot) => (
                    <tr key={snapshot.id}>
                      <td>{snapshot.snapshot_at}</td>
                      <td>{formatMinor(snapshot.balance_minor, selectedAccount.currency_code)}</td>
                      <td>{snapshot.note ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">No snapshots yet.</p>
            )}
          </section>
        </section>
      ) : null}
    </div>
  );
}
