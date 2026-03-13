/**
 * CALLING SPEC:
 * - Purpose: render the `UsersSection` React UI module.
 * - Inputs: callers that import `frontend/src/features/properties/sections/UsersSection.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `UsersSection`.
 * - Side effects: React rendering and user event wiring.
 */
import type { FormEvent } from "react";
import { Plus } from "lucide-react";

import type { User } from "../../../lib/types";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "../../../components/ui/dialog";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";

interface UsersSectionProps {
  search: string;
  onSearchChange: (value: string) => void;
  createPanelOpen: boolean;
  onToggleCreatePanel: () => void;
  onCloseCreatePanel: () => void;
  newUserName: string;
  onNewUserNameChange: (value: string) => void;
  editingUserId: string;
  editingUserName: string;
  onEditingUserNameChange: (value: string) => void;
  onStartEditUser: (user: User) => void;
  onCancelEditUser: () => void;
  onSaveUser: (userId: string) => void;
  onCreateUserSubmit: (event: FormEvent<HTMLFormElement>) => void;
  users: User[] | undefined;
  hasAnyUsers: boolean;
  isLoading: boolean;
  isError: boolean;
  queryErrorMessage: string | null;
  createErrorMessage: string | null;
  updateErrorMessage: string | null;
  isCreating: boolean;
  isUpdating: boolean;
}

export function UsersSection(props: UsersSectionProps) {
  const {
    search,
    onSearchChange,
    createPanelOpen,
    onToggleCreatePanel,
    onCloseCreatePanel,
    newUserName,
    onNewUserNameChange,
    editingUserId,
    editingUserName,
    onEditingUserNameChange,
    onStartEditUser,
    onCancelEditUser,
    onSaveUser,
    onCreateUserSubmit,
    users,
    hasAnyUsers,
    isLoading,
    isError,
    queryErrorMessage,
    createErrorMessage,
    updateErrorMessage,
    isCreating,
    isUpdating
  } = props;

  return (
    <div className="table-shell">
      <div className="table-shell-header">
        <div>
          <h3 className="table-shell-title">Users</h3>
          <p className="table-shell-subtitle">Manage owners available to accounts and entries.</p>
        </div>
      </div>
      <div className="table-toolbar">
        <div className="table-toolbar-filters">
          <label className="field min-w-[220px] grow">
            <span>Search</span>
            <Input placeholder="Filter users" value={search} onChange={(event) => onSearchChange(event.target.value)} />
          </label>
        </div>
        <div className="table-toolbar-action">
          <Button type="button" size="icon" variant="outline" aria-label="Add user" onClick={onToggleCreatePanel}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading ? <p>Loading users...</p> : null}
      {isError ? <p className="error">{queryErrorMessage}</p> : null}

      {users ? (
        users.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Current User</TableHead>
                <TableHead>Accounts</TableHead>
                <TableHead>Entries</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id} className="cursor-pointer" onDoubleClick={() => onStartEditUser(user)}>
                  <TableCell>{user.name}</TableCell>
                  <TableCell>{user.is_current_user ? <Badge variant="secondary">Current</Badge> : null}</TableCell>
                  <TableCell>{user.account_count ?? 0}</TableCell>
                  <TableCell>{user.entry_count ?? 0}</TableCell>
                  <TableCell />
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="muted">{hasAnyUsers ? "No users match the current search." : "No users yet."}</p>
        )
      ) : null}

      <Dialog
        open={createPanelOpen}
        onOpenChange={(open) => {
          if (!open) {
            onCloseCreatePanel();
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
            <DialogDescription>Add a new owner identity for account and entry assignment.</DialogDescription>
          </DialogHeader>
          <form className="grid gap-4" onSubmit={onCreateUserSubmit}>
            <FormField label="Name">
              <Input placeholder="e.g. Alice" value={newUserName} onChange={(event) => onNewUserNameChange(event.target.value)} />
            </FormField>
            {createErrorMessage ? <p className="error">{createErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCloseCreatePanel}>
                Cancel
              </Button>
              <Button type="submit" disabled={isCreating}>
                {isCreating ? "Creating..." : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(editingUserId)}
        onOpenChange={(open) => {
          if (!open) {
            onCancelEditUser();
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>Update the display name used in owner assignments.</DialogDescription>
          </DialogHeader>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (!editingUserId) {
                return;
              }
              onSaveUser(editingUserId);
            }}
          >
            <FormField label="Name">
              <Input
                placeholder="e.g. Alice"
                value={editingUserName}
                onChange={(event) => onEditingUserNameChange(event.target.value)}
              />
            </FormField>
            {updateErrorMessage ? <p className="error">{updateErrorMessage}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onCancelEditUser}>
                Cancel
              </Button>
              <Button type="submit" disabled={isUpdating || !editingUserId}>
                {isUpdating ? "Saving..." : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
