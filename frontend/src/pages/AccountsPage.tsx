import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { AccountDialogs } from "../features/accounts/AccountDialogs";
import { AccountsTableSection } from "../features/accounts/AccountsTableSection";
import { useAccountsPageModel } from "../features/accounts/useAccountsPageModel";
import { DeleteConfirmDialog } from "../components/DeleteConfirmDialog";

export function AccountsPage() {
  const model = useAccountsPageModel();

  const createAccountError =
    model.mutations.createAccountMutation.isError ? (model.mutations.createAccountMutation.error as Error).message : null;
  const updateAccountError =
    model.mutations.updateAccountMutation.isError ? (model.mutations.updateAccountMutation.error as Error).message : null;
  const createSnapshotError =
    model.mutations.createSnapshotMutation.isError ? (model.mutations.createSnapshotMutation.error as Error).message : null;
  const accountTableError = model.queries.accountsQuery.isError ? (model.queries.accountsQuery.error as Error).message : null;
  const reconciliationError =
    model.queries.reconciliationQuery.isError ? (model.queries.reconciliationQuery.error as Error).message : null;
  const snapshotsError = model.queries.snapshotsQuery.isError ? (model.queries.snapshotsQuery.error as Error).message : null;

  return (
    <div className="page stack-lg">
      <PageHeader
        title="Accounts"
        description="Accounts, snapshots, and reconciliation."
      />

      <WorkspaceSection>
        <AccountsTableSection
          accountSearch={model.accountSearch}
          onAccountSearchChange={model.setAccountSearch}
          onOpenCreateDialog={model.actions.openCreateDialog}
          accounts={model.queries.accountsQuery.data}
          filteredAccounts={model.filteredAccounts}
          selectedAccountId={model.selectedAccountId}
          onSelectAccount={model.setSelectedAccountId}
          onEditAccount={model.actions.editAccount}
          onDeleteAccount={model.actions.openDeleteDialog}
          ownerNameForId={model.ownerNameForId}
          isLoading={model.queries.accountsQuery.isLoading}
          errorMessage={accountTableError}
        />
      </WorkspaceSection>

      <AccountDialogs
        createDialogOpen={model.createDialogOpen}
        onCreateDialogOpenChange={model.setCreateDialogOpen}
        editDialogOpen={Boolean(model.editingAccountId)}
        onEditDialogOpenChange={model.actions.onEditDialogOpenChange}
        createForm={model.createForm}
        onCreateFormChange={model.setCreateForm}
        editForm={model.editForm}
        onEditFormChange={model.setEditForm}
        onCreateAccount={model.actions.onCreateAccount}
        onUpdateAccount={model.actions.onUpdateAccount}
        currencies={model.currencies}
        editingAccount={model.editingAccount}
        reconciliation={model.queries.reconciliationQuery.data}
        reconciliationErrorMessage={reconciliationError}
        reconciliationIsLoading={model.queries.reconciliationQuery.isLoading}
        snapshots={model.queries.snapshotsQuery.data}
        snapshotsErrorMessage={snapshotsError}
        snapshotsIsLoading={model.queries.snapshotsQuery.isLoading}
        snapshotForm={model.snapshotForm}
        onSnapshotFormChange={model.setSnapshotForm}
        onCreateSnapshot={model.actions.onCreateSnapshot}
        onDeleteSnapshot={model.actions.openDeleteSnapshotDialog}
        snapshotFormErrorMessage={model.snapshotFormError}
        snapshotCreateErrorMessage={createSnapshotError}
        snapshotIsCreating={model.mutations.createSnapshotMutation.isPending}
        createErrorMessage={createAccountError}
        updateErrorMessage={updateAccountError}
        isCreating={model.mutations.createAccountMutation.isPending}
        isUpdating={model.mutations.updateAccountMutation.isPending}
        onResetCreateMutationError={() => model.mutations.createAccountMutation.reset()}
        onResetUpdateMutationError={() => model.mutations.updateAccountMutation.reset()}
      />

      <DeleteConfirmDialog
        open={Boolean(model.deletingAccountId)}
        onOpenChange={model.actions.onDeleteDialogOpenChange}
        title={model.deletingAccount ? `Delete ${model.deletingAccount.name}?` : "Delete account?"}
        description="This removes the account root. Snapshots are deleted, and existing entries stay in the ledger with a missing-entity marker where preserved labels remain."
        confirmLabel="Delete account"
        isPending={model.mutations.deleteAccountMutation.isPending}
        errorMessage={model.mutations.deleteAccountMutation.isError ? (model.mutations.deleteAccountMutation.error as Error).message : null}
        warnings={[
          "Ledger entries are preserved; their account link is cleared.",
          "If the account name appears in from/to fields, the visible label stays but is marked as missing.",
          "Snapshot history for this account is deleted."
        ]}
        onConfirm={model.actions.confirmDeleteAccount}
      />

      <DeleteConfirmDialog
        open={Boolean(model.deletingSnapshotId)}
        onOpenChange={model.actions.onDeleteSnapshotDialogOpenChange}
        title={model.deletingSnapshot ? `Delete snapshot from ${model.deletingSnapshot.snapshot_at}?` : "Delete snapshot?"}
        description="This removes a stored balance checkpoint from the account history."
        confirmLabel="Delete snapshot"
        isPending={model.mutations.deleteSnapshotMutation.isPending}
        errorMessage={
          model.mutations.deleteSnapshotMutation.isError ? (model.mutations.deleteSnapshotMutation.error as Error).message : null
        }
        warnings={model.deleteSnapshotImpactWarnings}
        onConfirm={model.actions.confirmDeleteSnapshot}
      />
    </div>
  );
}
