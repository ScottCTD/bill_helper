import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createAccount,
  createSnapshot,
  deleteAccount,
  deleteSnapshot,
  getRuntimeSettings,
  getReconciliation,
  listAccounts,
  listCurrencies,
  listSnapshots,
  listUsers,
  updateAccount
} from "../../lib/api";
import { invalidateAccountReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { Account } from "../../lib/types";
import { buildEditForm, buildSnapshotDeletionImpact, normalizeNullableMarkdown, normalizeOptionalText } from "./helpers";
import { ACCOUNT_FORM_DEFAULTS, TODAY_ISO, type AccountFormState, type SnapshotFormState } from "./types";

export function useAccountsPageModel() {
  const queryClient = useQueryClient();

  const accountsQuery = useQuery({ queryKey: queryKeys.accounts.all, queryFn: listAccounts });
  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });

  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [accountSearch, setAccountSearch] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);
  const [deletingAccountId, setDeletingAccountId] = useState<string | null>(null);
  const [deletingSnapshotId, setDeletingSnapshotId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<AccountFormState>(ACCOUNT_FORM_DEFAULTS);
  const [editForm, setEditForm] = useState<AccountFormState>(ACCOUNT_FORM_DEFAULTS);
  const [snapshotForm, setSnapshotForm] = useState<SnapshotFormState>({
    snapshot_at: TODAY_ISO,
    balance_major: "",
    note: ""
  });
  const [snapshotFormError, setSnapshotFormError] = useState<string | null>(null);
  const [createCurrencyInitialized, setCreateCurrencyInitialized] = useState(false);

  const selectedAccount = accountsQuery.data?.find((account) => account.id === selectedAccountId) ?? null;
  const editingAccount = accountsQuery.data?.find((account) => account.id === editingAccountId) ?? null;
  const deletingAccount = accountsQuery.data?.find((account) => account.id === deletingAccountId) ?? null;
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
      const ownerName = ownerNamesById.get(account.owner_user_id) ?? "";
      return [account.name, account.currency_code, ownerName].join(" ").toLowerCase().includes(query);
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
    setEditForm(buildEditForm(editingAccount));
  }, [editingAccount]);

  useEffect(() => {
    if (!editingAccountId) {
      setSnapshotForm({
        snapshot_at: TODAY_ISO,
        balance_major: "",
        note: ""
      });
      setSnapshotFormError(null);
      return;
    }
    setSnapshotForm({
      snapshot_at: TODAY_ISO,
      balance_major: "",
      note: ""
    });
    setSnapshotFormError(null);
  }, [editingAccountId]);

  const snapshotsQuery = useQuery({
    queryKey: queryKeys.accounts.snapshots(editingAccountId ?? ""),
    queryFn: () => listSnapshots(editingAccountId ?? ""),
    enabled: Boolean(editingAccountId)
  });
  const deletingSnapshot = snapshotsQuery.data?.find((snapshot) => snapshot.id === deletingSnapshotId) ?? null;

  const reconciliationQuery = useQuery({
    queryKey: queryKeys.accounts.reconciliation(editingAccountId ?? ""),
    queryFn: () => getReconciliation(editingAccountId ?? ""),
    enabled: Boolean(editingAccountId)
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

  const deleteAccountMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: (_data, deletedAccountId) => {
      invalidateAccountReadModels(queryClient, deletedAccountId);
      if (selectedAccountId === deletedAccountId) {
        setSelectedAccountId("");
      }
      if (editingAccountId === deletedAccountId) {
        setEditingAccountId(null);
      }
      setDeletingAccountId(null);
    }
  });

  const deleteSnapshotMutation = useMutation({
    mutationFn: ({ accountId, snapshotId }: { accountId: string; snapshotId: string }) => deleteSnapshot(accountId, snapshotId),
    onSuccess: (_data, variables) => {
      invalidateAccountReadModels(queryClient, variables.accountId);
      setDeletingSnapshotId(null);
    }
  });

  function onCreateAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAccountMutation.mutate({
      owner_user_id: createForm.owner_user_id,
      name: createForm.name.trim(),
      markdown_body: normalizeNullableMarkdown(createForm.markdown_body),
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
        owner_user_id: editForm.owner_user_id,
        name: editForm.name.trim(),
        markdown_body: normalizeNullableMarkdown(editForm.markdown_body),
        currency_code: editForm.currency_code.toUpperCase(),
        is_active: editForm.is_active
      }
    });
  }

  function onCreateSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingAccountId) {
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
      accountId: editingAccountId,
      snapshot_at: snapshotForm.snapshot_at,
      balance_minor: Math.round(parsedBalance * 100),
      note: normalizeOptionalText(snapshotForm.note)
    });
  }

  function openCreateDialog() {
    setCreateDialogOpen(true);
  }

  function editAccount(accountId: string) {
    setSelectedAccountId(accountId);
    setEditingAccountId(accountId);
  }

  function ownerNameForId(ownerUserId: string): string {
    return ownerNamesById.get(ownerUserId) ?? "(unknown user)";
  }

  function onEditDialogOpenChange(open: boolean) {
    if (!open) {
      setEditingAccountId(null);
      createSnapshotMutation.reset();
    }
  }

  function openDeleteDialog(accountId: string) {
    setDeletingAccountId(accountId);
  }

  function onDeleteDialogOpenChange(open: boolean) {
    if (!open) {
      setDeletingAccountId(null);
      deleteAccountMutation.reset();
    }
  }

  function confirmDeleteAccount() {
    if (!deletingAccountId) {
      return;
    }
    deleteAccountMutation.mutate(deletingAccountId);
  }

  function openDeleteSnapshotDialog(snapshotId: string) {
    setDeletingSnapshotId(snapshotId);
  }

  function onDeleteSnapshotDialogOpenChange(open: boolean) {
    if (!open) {
      setDeletingSnapshotId(null);
      deleteSnapshotMutation.reset();
    }
  }

  function confirmDeleteSnapshot() {
    if (!deletingSnapshot || !deletingSnapshotId) {
      return;
    }
    deleteSnapshotMutation.mutate({
      accountId: deletingSnapshot.account_id,
      snapshotId: deletingSnapshotId
    });
  }

  const deleteSnapshotImpactWarnings =
    deletingSnapshot && snapshotsQuery.data
      ? buildSnapshotDeletionImpact(snapshotsQuery.data, deletingSnapshot.id)
      : [
          "This action cannot be undone.",
          "Reconciliation history will update immediately after the snapshot is removed."
        ];

  return {
    selectedAccountId,
    selectedAccount,
    setSelectedAccountId,
    accountSearch,
    setAccountSearch,
    createDialogOpen,
    setCreateDialogOpen,
    editingAccountId,
    editingAccount,
    deletingAccountId,
    deletingAccount,
    deletingSnapshotId,
    deletingSnapshot,
    createForm,
    setCreateForm,
    editForm,
    setEditForm,
    snapshotForm,
    setSnapshotForm,
    snapshotFormError,
    currencies,
    filteredAccounts,
    ownerNameForId,
    queries: {
      accountsQuery,
      usersQuery,
      currenciesQuery,
      reconciliationQuery,
      snapshotsQuery
    },
    deleteSnapshotImpactWarnings,
    mutations: {
      createAccountMutation,
      updateAccountMutation,
      createSnapshotMutation,
      deleteAccountMutation,
      deleteSnapshotMutation
    },
    actions: {
      onCreateAccount,
      onUpdateAccount,
      onCreateSnapshot,
      openCreateDialog,
      editAccount,
      onEditDialogOpenChange,
      openDeleteDialog,
      onDeleteDialogOpenChange,
      confirmDeleteAccount,
      openDeleteSnapshotDialog,
      onDeleteSnapshotDialogOpenChange,
      confirmDeleteSnapshot
    }
  };
}
