import type { FormEvent } from "react";

import type { Account, Reconciliation, Snapshot } from "../../lib/types";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
import { MarkdownBlockEditor } from "../../components/MarkdownBlockEditor";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../../components/ui/dialog";
import { FormField } from "../../components/ui/form-field";
import { Input } from "../../components/ui/input";
import { NativeSelect } from "../../components/ui/native-select";
import { ReconciliationSection } from "./ReconciliationSection";
import { SnapshotCreatePanel } from "./SnapshotCreatePanel";
import { SnapshotHistoryTable } from "./SnapshotHistoryTable";
import type { AccountFormState, SnapshotFormState } from "./types";

interface AccountDialogsProps {
  createDialogOpen: boolean;
  onCreateDialogOpenChange: (open: boolean) => void;
  editDialogOpen: boolean;
  onEditDialogOpenChange: (open: boolean) => void;
  createForm: AccountFormState;
  onCreateFormChange: (next: AccountFormState) => void;
  editForm: AccountFormState;
  onEditFormChange: (next: AccountFormState) => void;
  onCreateAccount: (event: FormEvent<HTMLFormElement>) => void;
  onUpdateAccount: (event: FormEvent<HTMLFormElement>) => void;
  currencies: string[];
  editingAccount: Account | null;
  reconciliation: Reconciliation | undefined;
  reconciliationErrorMessage: string | null;
  reconciliationIsLoading: boolean;
  snapshots: Snapshot[] | undefined;
  snapshotsErrorMessage: string | null;
  snapshotsIsLoading: boolean;
  snapshotForm: SnapshotFormState;
  onSnapshotFormChange: (next: SnapshotFormState) => void;
  onCreateSnapshot: (event: FormEvent<HTMLFormElement>) => void;
  onDeleteSnapshot: (snapshotId: string) => void;
  snapshotFormErrorMessage: string | null;
  snapshotCreateErrorMessage: string | null;
  snapshotIsCreating: boolean;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
  onResetCreateMutationError: () => void;
  onResetUpdateMutationError: () => void;
}

export function AccountDialogs(props: AccountDialogsProps) {
  const {
    createDialogOpen,
    onCreateDialogOpenChange,
    editDialogOpen,
    onEditDialogOpenChange,
    createForm,
    onCreateFormChange,
    editForm,
    onEditFormChange,
    onCreateAccount,
    onUpdateAccount,
    currencies,
    editingAccount,
    reconciliation,
    reconciliationErrorMessage,
    reconciliationIsLoading,
    snapshots,
    snapshotsErrorMessage,
    snapshotsIsLoading,
    snapshotForm,
    onSnapshotFormChange,
    onCreateSnapshot,
    onDeleteSnapshot,
    snapshotFormErrorMessage,
    snapshotCreateErrorMessage,
    snapshotIsCreating,
    createErrorMessage,
    updateErrorMessage,
    isCreating,
    isUpdating,
    onResetCreateMutationError,
    onResetUpdateMutationError
  } = props;

  const createMarkdownResetKey = `account-create-${createDialogOpen ? "open" : "closed"}`;
  const editMarkdownResetKey = `account-edit-${editingAccount?.id ?? "none"}-${editDialogOpen ? "open" : "closed"}`;

  return (
    <>
      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          onCreateDialogOpenChange(open);
          if (!open) {
            onResetCreateMutationError();
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
              <FormField label="Name">
                <Input required value={createForm.name} onChange={(event) => onCreateFormChange({ ...createForm, name: event.target.value })} />
              </FormField>
              <FormField label="Currency">
                <NativeSelect
                  value={createForm.currency_code}
                  onChange={(event) => onCreateFormChange({ ...createForm, currency_code: event.target.value })}
                >
                  {currencies.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            </div>
            <section className="entry-editor-markdown">
              <div className="grid gap-2 text-sm">
                <p className="text-sm font-medium leading-none">Notes</p>
                <MarkdownBlockEditor
                  markdown={createForm.markdown_body}
                  resetKey={createMarkdownResetKey}
                  disabled={isCreating}
                  onChange={(markdown) => onCreateFormChange({ ...createForm, markdown_body: markdown })}
                />
                <p className="text-xs text-muted-foreground">Optional markdown notes for account context and agent prompts.</p>
              </div>
            </section>
            {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onCreateDialogOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isCreating}>
                {isCreating ? "Creating..." : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={editDialogOpen}
        onOpenChange={(open) => {
          onEditDialogOpenChange(open);
          if (!open) {
            onResetUpdateMutationError();
          }
        }}
      >
        <DialogContent className="account-edit-dialog max-w-6xl overflow-hidden">
          <DialogHeader>
            <DialogTitle>{editingAccount ? editingAccount.name : "Edit Account"}</DialogTitle>
            <DialogDescription>Account details, reconciliation, and snapshots in one workspace.</DialogDescription>
          </DialogHeader>

          <div className="account-edit-layout">
            <form id="account-edit-form" className="account-edit-details-card" onSubmit={onUpdateAccount}>
              <div className="account-edit-details-grid">
                <FormField label="Name">
                  <Input required value={editForm.name} onChange={(event) => onEditFormChange({ ...editForm, name: event.target.value })} />
                </FormField>
                <FormField label="Currency">
                  <NativeSelect
                    value={editForm.currency_code}
                    onChange={(event) => onEditFormChange({ ...editForm, currency_code: event.target.value })}
                  >
                    {currencies.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </NativeSelect>
                </FormField>
                <FormField label="Active">
                  <label className="account-edit-active-toggle">
                    <Checkbox
                      checked={editForm.is_active}
                      onCheckedChange={(checked) => onEditFormChange({ ...editForm, is_active: checked === true })}
                    />
                    <span>{editForm.is_active ? "Active" : "Inactive"}</span>
                  </label>
                </FormField>
                <div className="account-edit-notes">
                  <div className="grid gap-2 text-sm">
                    <p className="text-sm font-medium leading-none">Notes</p>
                    <MarkdownBlockEditor
                      markdown={editForm.markdown_body}
                      resetKey={editMarkdownResetKey}
                      disabled={isUpdating || !editingAccount}
                      onChange={(markdown) => onEditFormChange({ ...editForm, markdown_body: markdown })}
                    />
                  </div>
                </div>
              </div>
            </form>

            <div className="account-edit-workspace">
              <section className="account-edit-history-column">
                <div className="account-edit-history-scroll scroll-surface">
                  <section className="account-edit-section">
                    <h3 className="text-base font-semibold">Reconciliation</h3>
                    <ReconciliationSection
                      account={editingAccount}
                      reconciliation={reconciliation}
                      isLoading={reconciliationIsLoading}
                      errorMessage={reconciliationErrorMessage}
                    />
                  </section>
                  <section className="account-edit-section">
                    <SnapshotHistoryTable
                      selectedAccount={editingAccount}
                      snapshots={snapshots}
                      isLoading={snapshotsIsLoading}
                      errorMessage={snapshotsErrorMessage}
                      onDeleteSnapshot={onDeleteSnapshot}
                    />
                  </section>
                </div>
              </section>

              <aside className="account-edit-sidebar">
                <SnapshotCreatePanel
                  selectedAccount={editingAccount}
                  snapshotForm={snapshotForm}
                  onSnapshotFormChange={onSnapshotFormChange}
                  onCreateSnapshot={onCreateSnapshot}
                  formErrorMessage={snapshotFormErrorMessage}
                  createErrorMessage={snapshotCreateErrorMessage}
                  isCreating={snapshotIsCreating}
                />
              </aside>
            </div>

            {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onEditDialogOpenChange(false)}>
                Cancel
              </Button>
              <Button form="account-edit-form" type="submit" disabled={isUpdating || !editingAccount}>
                {isUpdating ? "Saving..." : "Save changes"}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
