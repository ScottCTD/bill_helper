import { AccountDialogs } from "../features/accounts/AccountDialogs";
import { AccountsTableSection } from "../features/accounts/AccountsTableSection";
import { ReconciliationSection } from "../features/accounts/ReconciliationSection";
import { SnapshotsSection } from "../features/accounts/SnapshotsSection";
import { useAccountsPageModel } from "../features/accounts/useAccountsPageModel";

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
    <div className="stack-lg">
      <AccountsTableSection
        accountSearch={model.accountSearch}
        onAccountSearchChange={model.setAccountSearch}
        onOpenCreateDialog={model.actions.openCreateDialog}
        accounts={model.queries.accountsQuery.data}
        filteredAccounts={model.filteredAccounts}
        selectedAccountId={model.selectedAccountId}
        onSelectAccount={model.setSelectedAccountId}
        onEditAccount={model.actions.editAccount}
        ownerNameForId={model.ownerNameForId}
        isLoading={model.queries.accountsQuery.isLoading}
        errorMessage={accountTableError}
      />

      <section className="grid-2">
        <ReconciliationSection
          selectedAccount={model.selectedAccount}
          reconciliation={model.queries.reconciliationQuery.data}
          isLoading={model.queries.reconciliationQuery.isLoading}
          errorMessage={reconciliationError}
        />

        <SnapshotsSection
          selectedAccount={model.selectedAccount}
          snapshotForm={model.snapshotForm}
          onSnapshotFormChange={model.setSnapshotForm}
          onCreateSnapshot={model.actions.onCreateSnapshot}
          snapshots={model.queries.snapshotsQuery.data}
          isLoading={model.queries.snapshotsQuery.isLoading}
          errorMessage={snapshotsError}
          formErrorMessage={model.snapshotFormError}
          createErrorMessage={createSnapshotError}
          isCreating={model.mutations.createSnapshotMutation.isPending}
        />
      </section>

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
        users={model.queries.usersQuery.data}
        currencies={model.currencies}
        editingAccount={model.editingAccount}
        createErrorMessage={createAccountError}
        updateErrorMessage={updateAccountError}
        isCreating={model.mutations.createAccountMutation.isPending}
        isUpdating={model.mutations.updateAccountMutation.isPending}
        onResetCreateMutationError={() => model.mutations.createAccountMutation.reset()}
        onResetUpdateMutationError={() => model.mutations.updateAccountMutation.reset()}
      />
    </div>
  );
}
