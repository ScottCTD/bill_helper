import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Checkbox } from "../components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../components/ui/dialog";
import { FormField } from "../components/ui/form-field";
import { Input } from "../components/ui/input";
import { NativeSelect } from "../components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  createAccount,
  createSnapshot,
  getRuntimeSettings,
  getReconciliation,
  listAccounts,
  listCurrencies,
  listSnapshots,
  listUsers,
  updateAccount
} from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateAccountReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { Account } from "../lib/types";

interface AccountFormState {
  owner_user_id: string;
  name: string;
  institution: string;
  account_type: string;
  currency_code: string;
  is_active: boolean;
}

const TODAY_ISO = new Date().toISOString().slice(0, 10);

const ACCOUNT_FORM_DEFAULTS: AccountFormState = {
  owner_user_id: "",
  name: "",
  institution: "",
  account_type: "",
  currency_code: "CAD",
  is_active: true
};

function toDateLabel(value: string) {
  if (!value) {
    return "-";
  }
  return value.slice(0, 10);
}

function normalizeOptionalText(value: string): string | undefined {
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

function normalizeNullableText(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function buildEditForm(account: Account, fallbackOwnerUserId: string): AccountFormState {
  return {
    owner_user_id: account.owner_user_id ?? fallbackOwnerUserId,
    name: account.name,
    institution: account.institution ?? "",
    account_type: account.account_type ?? "",
    currency_code: account.currency_code,
    is_active: account.is_active
  };
}

export function AccountsPage() {
  const queryClient = useQueryClient();
  const accountsQuery = useQuery({ queryKey: queryKeys.accounts.all, queryFn: listAccounts });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });

  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [accountSearch, setAccountSearch] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<AccountFormState>(ACCOUNT_FORM_DEFAULTS);
  const [editForm, setEditForm] = useState<AccountFormState>(ACCOUNT_FORM_DEFAULTS);
  const [snapshotForm, setSnapshotForm] = useState({
    snapshot_at: TODAY_ISO,
    balance_major: "",
    note: ""
  });
  const [snapshotFormError, setSnapshotFormError] = useState<string | null>(null);
  const [createCurrencyInitialized, setCreateCurrencyInitialized] = useState(false);

  const selectedAccount = accountsQuery.data?.find((account) => account.id === selectedAccountId) ?? null;
  const editingAccount = accountsQuery.data?.find((account) => account.id === editingAccountId) ?? null;
  const currentUserId = usersQuery.data?.find((user) => user.is_current_user)?.id ?? "";
  const defaultCurrencyCode = (runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase();

  const ownerNamesById = useMemo(
    () => new Map((usersQuery.data ?? []).map((user) => [user.id, user.name])),
    [usersQuery.data]
  );

  const currencies = useMemo(() => {
    const codes = new Set<string>();
    (currenciesQuery.data ?? []).forEach((currency) => codes.add(currency.code.toUpperCase()));
    (accountsQuery.data ?? []).forEach((account) => codes.add(account.currency_code.toUpperCase()));
    if (createForm.currency_code) {
      codes.add(createForm.currency_code.toUpperCase());
    }
    if (editForm.currency_code) {
      codes.add(editForm.currency_code.toUpperCase());
    }
    return Array.from(codes).sort();
  }, [accountsQuery.data, createForm.currency_code, currenciesQuery.data, editForm.currency_code]);

  const filteredAccounts = useMemo(() => {
    const query = accountSearch.trim().toLowerCase();
    const accounts = accountsQuery.data ?? [];
    if (!query) {
      return accounts;
    }

    return accounts.filter((account) => {
      const ownerName = account.owner_user_id ? ownerNamesById.get(account.owner_user_id) ?? "" : "";
      return [account.name, account.institution ?? "", account.account_type ?? "", account.currency_code, ownerName]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [accountSearch, accountsQuery.data, ownerNamesById]);

  useEffect(() => {
    const accounts = accountsQuery.data ?? [];
    if (!accounts.length) {
      if (selectedAccountId) {
        setSelectedAccountId("");
      }
      return;
    }

    const hasSelected = accounts.some((account) => account.id === selectedAccountId);
    if (!selectedAccountId || !hasSelected) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accountsQuery.data, selectedAccountId]);

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
    if (!editingAccount) {
      return;
    }
    setEditForm(buildEditForm(editingAccount, currentUserId));
  }, [currentUserId, editingAccount]);

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
    onSuccess: (createdAccount) => {
      invalidateAccountReadModels(queryClient, createdAccount.id);
      setSelectedAccountId(createdAccount.id);
      setCreateDialogOpen(false);
      setCreateForm({
        ...ACCOUNT_FORM_DEFAULTS,
        owner_user_id: currentUserId,
        currency_code: defaultCurrencyCode
      });
    }
  });

  const updateAccountMutation = useMutation({
    mutationFn: ({ accountId, payload }: { accountId: string; payload: Partial<Account> }) => updateAccount(accountId, payload),
    onSuccess: (_, variables) => {
      invalidateAccountReadModels(queryClient, variables.accountId);
      setEditingAccountId(null);
    }
  });

  const createSnapshotMutation = useMutation({
    mutationFn: (payload: { accountId: string; snapshot_at: string; balance_minor: number; note?: string }) =>
      createSnapshot(payload.accountId, {
        snapshot_at: payload.snapshot_at,
        balance_minor: payload.balance_minor,
        note: payload.note
      }),
    onSuccess: (_, variables) => {
      invalidateAccountReadModels(queryClient, variables.accountId);
      setSnapshotForm((state) => ({ ...state, balance_major: "", note: "" }));
      setSnapshotFormError(null);
    }
  });

  function onCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAccountMutation.mutate({
      owner_user_id: createForm.owner_user_id || undefined,
      name: createForm.name.trim(),
      institution: normalizeOptionalText(createForm.institution),
      account_type: normalizeOptionalText(createForm.account_type),
      currency_code: createForm.currency_code.toUpperCase(),
      is_active: true
    });
  }

  function onUpdateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingAccountId) {
      return;
    }

    updateAccountMutation.mutate({
      accountId: editingAccountId,
      payload: {
        owner_user_id: editForm.owner_user_id || null,
        name: editForm.name.trim(),
        institution: normalizeNullableText(editForm.institution),
        account_type: normalizeNullableText(editForm.account_type),
        currency_code: editForm.currency_code.toUpperCase(),
        is_active: editForm.is_active
      }
    });
  }

  function onCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAccountId) {
      return;
    }

    if (!snapshotForm.balance_major.trim()) {
      setSnapshotFormError("Balance is required.");
      return;
    }

    const parsedBalance = Number(snapshotForm.balance_major);
    if (!Number.isFinite(parsedBalance)) {
      setSnapshotFormError("Balance must be a valid number.");
      return;
    }

    setSnapshotFormError(null);
    createSnapshotMutation.mutate({
      accountId: selectedAccountId,
      snapshot_at: snapshotForm.snapshot_at,
      balance_minor: Math.round(parsedBalance * 100),
      note: normalizeOptionalText(snapshotForm.note)
    });
  }

  const createAccountError = createAccountMutation.isError ? (createAccountMutation.error as Error).message : null;
  const updateAccountError = updateAccountMutation.isError ? (updateAccountMutation.error as Error).message : null;
  const createSnapshotError = createSnapshotMutation.isError ? (createSnapshotMutation.error as Error).message : null;
  const accountTableError = accountsQuery.isError ? (accountsQuery.error as Error).message : null;
  const reconciliationError = reconciliationQuery.isError ? (reconciliationQuery.error as Error).message : null;
  const snapshotsError = snapshotsQuery.isError ? (snapshotsQuery.error as Error).message : null;

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="table-shell-header">
            <div>
              <h2 className="table-shell-title">Accounts</h2>
              <p className="table-shell-subtitle">Select a row to manage snapshots and reconciliation.</p>
            </div>
          </div>

          <div className="table-toolbar filter-row">
            <div className="table-toolbar-filters">
              <label className="field min-w-[240px] grow">
                <span>Search</span>
                <Input
                  value={accountSearch}
                  onChange={(event) => setAccountSearch(event.target.value)}
                  placeholder="Name, institution, owner, or currency"
                />
              </label>
            </div>
            <div className="table-toolbar-action filter-action">
              <Button type="button" size="icon" variant="outline" aria-label="Create account" onClick={() => setCreateDialogOpen(true)}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="table-shell">
            {accountsQuery.isLoading ? <p>Loading accounts...</p> : null}
            {accountTableError ? <p className="error">{accountTableError}</p> : null}

            {accountsQuery.data ? (
              filteredAccounts.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Institution</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Owner</TableHead>
                      <TableHead>Currency</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAccounts.map((account) => (
                      <TableRow
                        key={account.id}
                        className="cursor-pointer"
                        data-state={account.id === selectedAccountId ? "selected" : undefined}
                        onClick={() => setSelectedAccountId(account.id)}
                      >
                        <TableCell className="font-medium">{account.name}</TableCell>
                        <TableCell>{account.institution ?? "-"}</TableCell>
                        <TableCell>{account.account_type ?? "-"}</TableCell>
                        <TableCell>
                          {account.owner_user_id ? (ownerNamesById.get(account.owner_user_id) ?? "(unknown user)") : "(none)"}
                        </TableCell>
                        <TableCell>{account.currency_code}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              account.is_active
                                ? "border-success/45 bg-success/15 text-success-foreground"
                                : "border-border/80 bg-muted/45 text-muted-foreground"
                            }
                          >
                            {account.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell>{toDateLabel(account.updated_at)}</TableCell>
                        <TableCell>
                          <div className="table-actions">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelectedAccountId(account.id);
                                setEditingAccountId(account.id);
                              }}
                            >
                              Edit
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="muted">{accountSearch.trim() ? "No accounts match this search." : "No accounts yet."}</p>
              )
            ) : null}
          </div>
        </CardContent>
      </Card>

      <section className="grid-2">
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
                {reconciliationQuery.isLoading ? <p>Loading reconciliation...</p> : null}
                {reconciliationError ? <p className="error">{reconciliationError}</p> : null}
                {reconciliationQuery.data ? (
                  <ul className="key-value-list">
                    <li>
                      <span>As of</span>
                      <strong>{reconciliationQuery.data.as_of}</strong>
                    </li>
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
                      <span>Snapshot date</span>
                      <strong>{reconciliationQuery.data.snapshot_at ?? "-"}</strong>
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
                ) : null}
              </>
            ) : (
              <p className="muted">Select an account from the table to view reconciliation details.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="table-shell-header">
              <div>
                <h3 className="table-shell-title text-base">Snapshots</h3>
                <p className="table-shell-subtitle">
                  A snapshot is a balance checkpoint copied from your bank on a specific day. Add one each time you want a fresh reference point.
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
                      onChange={(event) => setSnapshotForm((state) => ({ ...state, snapshot_at: event.target.value }))}
                    />
                  </FormField>
                  <FormField label={`Balance (${selectedAccount.currency_code})`}>
                    <Input
                      type="number"
                      step="0.01"
                      required
                      value={snapshotForm.balance_major}
                      onChange={(event) => setSnapshotForm((state) => ({ ...state, balance_major: event.target.value }))}
                    />
                  </FormField>
                  <FormField label="Note" className="full-row">
                    <Input value={snapshotForm.note} onChange={(event) => setSnapshotForm((state) => ({ ...state, note: event.target.value }))} />
                  </FormField>
                  <div className="full-row flex justify-end">
                    <Button type="submit" disabled={createSnapshotMutation.isPending}>
                      {createSnapshotMutation.isPending ? "Adding..." : "Add snapshot"}
                    </Button>
                  </div>
                </form>

                {snapshotFormError ? <p className="error">{snapshotFormError}</p> : null}
                {createSnapshotError ? <p className="error">{createSnapshotError}</p> : null}
                {snapshotsError ? <p className="error">{snapshotsError}</p> : null}
                {snapshotsQuery.isLoading ? <p>Loading snapshots...</p> : null}

                {snapshotsQuery.data?.length ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Balance</TableHead>
                        <TableHead>Note</TableHead>
                        <TableHead>Added</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {snapshotsQuery.data.map((snapshot) => (
                        <TableRow key={snapshot.id}>
                          <TableCell>{snapshot.snapshot_at}</TableCell>
                          <TableCell>{formatMinor(snapshot.balance_minor, selectedAccount.currency_code)}</TableCell>
                          <TableCell>{snapshot.note ?? "-"}</TableCell>
                          <TableCell>{toDateLabel(snapshot.created_at)}</TableCell>
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
      </section>

      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          setCreateDialogOpen(open);
          if (!open) {
            createAccountMutation.reset();
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create Account</DialogTitle>
            <DialogDescription>New accounts are active by default and immediately available for snapshot tracking.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={onCreateAccount}>
            <div className="form-grid">
              <FormField label="Owner">
                <NativeSelect
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
                </NativeSelect>
              </FormField>
              <FormField label="Name">
                <Input
                  required
                  value={createForm.name}
                  onChange={(event) => setCreateForm((state) => ({ ...state, name: event.target.value }))}
                />
              </FormField>
              <FormField label="Institution">
                <Input
                  value={createForm.institution}
                  onChange={(event) => setCreateForm((state) => ({ ...state, institution: event.target.value }))}
                />
              </FormField>
              <FormField label="Type">
                <Input
                  value={createForm.account_type}
                  onChange={(event) => setCreateForm((state) => ({ ...state, account_type: event.target.value }))}
                />
              </FormField>
              <FormField label="Currency">
                <NativeSelect
                  value={createForm.currency_code}
                  onChange={(event) => setCreateForm((state) => ({ ...state, currency_code: event.target.value }))}
                >
                  {currencies.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            </div>
            {createAccountError ? <p className="error">{createAccountError}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAccountMutation.isPending}>
                {createAccountMutation.isPending ? "Creating..." : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(editingAccountId)}
        onOpenChange={(open) => {
          if (!open) {
            setEditingAccountId(null);
            updateAccountMutation.reset();
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Account</DialogTitle>
            <DialogDescription>Update account metadata and active status from the selected table row.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={onUpdateAccount}>
            <div className="form-grid">
              <FormField label="Owner">
                <NativeSelect
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
                </NativeSelect>
              </FormField>
              <FormField label="Name">
                <Input required value={editForm.name} onChange={(event) => setEditForm((state) => ({ ...state, name: event.target.value }))} />
              </FormField>
              <FormField label="Institution">
                <Input
                  value={editForm.institution}
                  onChange={(event) => setEditForm((state) => ({ ...state, institution: event.target.value }))}
                />
              </FormField>
              <FormField label="Type">
                <Input
                  value={editForm.account_type}
                  onChange={(event) => setEditForm((state) => ({ ...state, account_type: event.target.value }))}
                />
              </FormField>
              <FormField label="Currency">
                <NativeSelect
                  value={editForm.currency_code}
                  onChange={(event) => setEditForm((state) => ({ ...state, currency_code: event.target.value }))}
                >
                  {currencies.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField label="Active">
                <label className="inline-flex h-9 items-center gap-2 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-sm">
                  <Checkbox
                    checked={editForm.is_active}
                    onCheckedChange={(checked) => setEditForm((state) => ({ ...state, is_active: checked === true }))}
                  />
                  <span>{editForm.is_active ? "Active account" : "Inactive account"}</span>
                </label>
              </FormField>
            </div>
            {updateAccountError ? <p className="error">{updateAccountError}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditingAccountId(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateAccountMutation.isPending || !editingAccount}>
                {updateAccountMutation.isPending ? "Saving..." : "Save changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
