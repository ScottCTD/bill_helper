import type { FormEvent } from "react";

import type { Account, User } from "../../lib/types";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
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
import type { AccountFormState } from "./types";

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
  users: User[] | undefined;
  currencies: string[];
  editingAccount: Account | null;
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
    users,
    currencies,
    editingAccount,
    createErrorMessage,
    updateErrorMessage,
    isCreating,
    isUpdating,
    onResetCreateMutationError,
    onResetUpdateMutationError
  } = props;

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
              <FormField label="Owner">
                <NativeSelect
                  value={createForm.owner_user_id}
                  onChange={(event) => onCreateFormChange({ ...createForm, owner_user_id: event.target.value })}
                >
                  <option value="">(none)</option>
                  {users?.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                      {user.is_current_user ? " (Current User)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField label="Name">
                <Input required value={createForm.name} onChange={(event) => onCreateFormChange({ ...createForm, name: event.target.value })} />
              </FormField>
              <FormField label="Institution">
                <Input
                  value={createForm.institution}
                  onChange={(event) => onCreateFormChange({ ...createForm, institution: event.target.value })}
                />
              </FormField>
              <FormField label="Type">
                <Input
                  value={createForm.account_type}
                  onChange={(event) => onCreateFormChange({ ...createForm, account_type: event.target.value })}
                />
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
                  onChange={(event) => onEditFormChange({ ...editForm, owner_user_id: event.target.value })}
                >
                  <option value="">(none)</option>
                  {users?.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name}
                      {user.is_current_user ? " (Current User)" : ""}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
              <FormField label="Name">
                <Input required value={editForm.name} onChange={(event) => onEditFormChange({ ...editForm, name: event.target.value })} />
              </FormField>
              <FormField label="Institution">
                <Input
                  value={editForm.institution}
                  onChange={(event) => onEditFormChange({ ...editForm, institution: event.target.value })}
                />
              </FormField>
              <FormField label="Type">
                <Input
                  value={editForm.account_type}
                  onChange={(event) => onEditFormChange({ ...editForm, account_type: event.target.value })}
                />
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
                <label className="inline-flex h-9 items-center gap-2 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-sm">
                  <Checkbox
                    checked={editForm.is_active}
                    onCheckedChange={(checked) => onEditFormChange({ ...editForm, is_active: checked === true })}
                  />
                  <span>{editForm.is_active ? "Active account" : "Inactive account"}</span>
                </label>
              </FormField>
            </div>
            {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onEditDialogOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isUpdating || !editingAccount}>
                {isUpdating ? "Saving..." : "Save changes"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
