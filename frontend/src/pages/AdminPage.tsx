/**
 * CALLING SPEC:
 * - Purpose: render the `AdminPage` React UI module.
 * - Inputs: callers that import `frontend/src/pages/AdminPage.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `AdminPage`.
 * - Side effects: React rendering and user event wiring.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Checkbox } from "../components/ui/checkbox";
import { FormField } from "../components/ui/form-field";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { useAuth } from "../features/auth";
import {
  createAdminUser,
  deleteAdminSession,
  deleteAdminUser,
  listAdminSessions,
  listAdminUsers,
  loginAsAdminUser,
  resetAdminUserPassword,
  updateAdminUser
} from "../lib/api";
import { invalidateUserReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { User } from "../lib/types";

interface UserDraft {
  name: string;
  is_admin: boolean;
  reset_password: string;
}

export function AdminPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [createName, setCreateName] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createIsAdmin, setCreateIsAdmin] = useState(false);
  const [userDrafts, setUserDrafts] = useState<Record<string, UserDraft>>({});

  const usersQuery = useQuery({
    queryKey: queryKeys.admin.users,
    queryFn: listAdminUsers,
    enabled: auth.status === "authenticated" && Boolean(auth.session?.user.is_admin)
  });
  const sessionsQuery = useQuery({
    queryKey: queryKeys.admin.sessions,
    queryFn: listAdminSessions,
    enabled: auth.status === "authenticated" && Boolean(auth.session?.user.is_admin)
  });

  useEffect(() => {
    if (!usersQuery.data) {
      return;
    }
    setUserDrafts((state) => {
      const nextState = { ...state };
      for (const user of usersQuery.data) {
        nextState[user.id] ??= {
          name: user.name,
          is_admin: user.is_admin,
          reset_password: ""
        };
      }
      return nextState;
    });
  }, [usersQuery.data]);

  const createUserMutation = useMutation({
    mutationFn: createAdminUser,
    onSuccess: () => {
      setCreateName("");
      setCreatePassword("");
      setCreateIsAdmin(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
      invalidateUserReadModels(queryClient);
    }
  });

  const updateUserMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: string; payload: { name?: string; is_admin?: boolean } }) =>
      updateAdminUser(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
      invalidateUserReadModels(queryClient);
    }
  });

  const resetPasswordMutation = useMutation({
    mutationFn: ({ userId, newPassword }: { userId: string; newPassword: string }) =>
      resetAdminUserPassword(userId, { new_password: newPassword }),
    onSuccess: (_user, variables) => {
      setUserDrafts((state) => ({
        ...state,
        [variables.userId]: {
          ...(state[variables.userId] ?? { name: "", is_admin: false, reset_password: "" }),
          reset_password: ""
        }
      }));
    }
  });

  const deleteUserMutation = useMutation({
    mutationFn: deleteAdminUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.sessions });
      invalidateUserReadModels(queryClient);
    }
  });

  const loginAsMutation = useMutation({
    mutationFn: loginAsAdminUser,
    onSuccess: (response) => {
      auth.adoptLoginResponse(response);
      navigate("/", { replace: true });
    }
  });

  const deleteSessionMutation = useMutation({
    mutationFn: deleteAdminSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.sessions });
    }
  });

  if (auth.status === "loading") {
    return <p>Loading admin tools...</p>;
  }

  if (auth.status !== "authenticated") {
    return <Navigate to="/login" replace />;
  }

  if (!auth.session?.user.is_admin) {
    return <Navigate to="/" replace />;
  }

  const users = usersQuery.data ?? [];

  function draftFor(user: User): UserDraft {
    return (
      userDrafts[user.id] ?? {
        name: user.name,
        is_admin: user.is_admin,
        reset_password: ""
      }
    );
  }

  function patchDraft(userId: string, patch: Partial<UserDraft>) {
    setUserDrafts((state) => ({
      ...state,
      [userId]: {
        ...(state[userId] ?? { name: "", is_admin: false, reset_password: "" }),
        ...patch
      }
    }));
  }

  return (
    <div className="stack-lg">
      <Card>
        <CardHeader>
          <CardTitle>Admin</CardTitle>
          <CardDescription>Create users, rotate passwords, inspect active sessions, and start impersonation sessions.</CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Create User</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-[2fr_2fr_auto_auto]"
            onSubmit={(event) => {
              event.preventDefault();
              createUserMutation.mutate({
                name: createName,
                password: createPassword,
                is_admin: createIsAdmin
              });
            }}
          >
            <FormField label="Name">
              <Input
                aria-label="New user name"
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="e.g. alice"
              />
            </FormField>
            <FormField label="Password">
              <Input
                aria-label="New user password"
                type="password"
                value={createPassword}
                onChange={(event) => setCreatePassword(event.target.value)}
                placeholder="Set an initial password"
              />
            </FormField>
            <FormField label="Admin">
              <div className="flex h-10 items-center gap-2 rounded-md border border-input px-3">
                <Checkbox
                  checked={createIsAdmin}
                  onCheckedChange={(checked) => setCreateIsAdmin(checked === true)}
                  id="create-admin-checkbox"
                />
                <label htmlFor="create-admin-checkbox" className="text-sm">
                  Grant admin access
                </label>
              </div>
            </FormField>
            <div className="flex items-end">
              <Button type="submit" disabled={createUserMutation.isPending}>
                {createUserMutation.isPending ? "Creating..." : "Create user"}
              </Button>
            </div>
          </form>
          {createUserMutation.error ? <p className="error mt-3">{(createUserMutation.error as Error).message}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
          <CardDescription>Edits apply immediately to the selected account owner.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {usersQuery.isLoading ? <p>Loading users...</p> : null}
          {usersQuery.error ? <p className="error">{(usersQuery.error as Error).message}</p> : null}
          {users.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Accounts</TableHead>
                  <TableHead>Entries</TableHead>
                  <TableHead>Update</TableHead>
                  <TableHead>Reset Password</TableHead>
                  <TableHead>Session</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => {
                  const draft = draftFor(user);
                  return (
                    <TableRow key={user.id}>
                      <TableCell className="align-top">
                        <div className="grid gap-2">
                          <Input
                            value={draft.name}
                            onChange={(event) => patchDraft(user.id, { name: event.target.value })}
                            aria-label={`${user.name} display name`}
                          />
                          <div className="flex items-center gap-2">
                            {user.is_current_user ? <Badge variant="secondary">Current</Badge> : null}
                            {auth.session?.user.id === user.id ? <Badge variant="outline">This session</Badge> : null}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="align-top">
                        <div className="flex h-10 items-center gap-2">
                          <Checkbox
                            checked={draft.is_admin}
                            onCheckedChange={(checked) => patchDraft(user.id, { is_admin: checked === true })}
                            id={`user-admin-${user.id}`}
                          />
                          <label htmlFor={`user-admin-${user.id}`} className="text-sm">
                            Admin
                          </label>
                        </div>
                      </TableCell>
                      <TableCell className="align-top">{user.account_count ?? 0}</TableCell>
                      <TableCell className="align-top">{user.entry_count ?? 0}</TableCell>
                      <TableCell className="align-top">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={updateUserMutation.isPending}
                            onClick={() =>
                              updateUserMutation.mutate({
                                userId: user.id,
                                payload: {
                                  name: draft.name,
                                  is_admin: draft.is_admin
                                }
                              })
                            }
                          >
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            disabled={deleteUserMutation.isPending || user.is_current_user}
                            onClick={() => deleteUserMutation.mutate(user.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell className="align-top">
                        <div className="grid gap-2">
                          <Input
                            type="password"
                            value={draft.reset_password}
                            onChange={(event) => patchDraft(user.id, { reset_password: event.target.value })}
                            placeholder="New password"
                            aria-label={`Reset password for ${user.name}`}
                          />
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={resetPasswordMutation.isPending || !draft.reset_password.trim()}
                            onClick={() =>
                              resetPasswordMutation.mutate({
                                userId: user.id,
                                newPassword: draft.reset_password
                              })
                            }
                          >
                            Reset password
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell className="align-top">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={loginAsMutation.isPending || auth.session?.user.id === user.id}
                          onClick={() => loginAsMutation.mutate(user.id)}
                        >
                          Log in as
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : null}
          {updateUserMutation.error ? <p className="error">{(updateUserMutation.error as Error).message}</p> : null}
          {resetPasswordMutation.error ? <p className="error">{(resetPasswordMutation.error as Error).message}</p> : null}
          {deleteUserMutation.error ? <p className="error">{(deleteUserMutation.error as Error).message}</p> : null}
          {loginAsMutation.error ? <p className="error">{(loginAsMutation.error as Error).message}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
          <CardDescription>Revoke stale bearer tokens without touching the owning user.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {sessionsQuery.isLoading ? <p>Loading sessions...</p> : null}
          {sessionsQuery.error ? <p className="error">{(sessionsQuery.error as Error).message}</p> : null}
          {(sessionsQuery.data ?? []).length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Flags</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(sessionsQuery.data ?? []).map((session) => (
                  <TableRow key={session.id}>
                    <TableCell>{session.user_name}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {session.is_admin ? <Badge variant="secondary">Admin</Badge> : null}
                        {session.is_admin_impersonation ? <Badge variant="outline">Impersonation</Badge> : null}
                        {session.is_current ? <Badge variant="secondary">Current</Badge> : null}
                      </div>
                    </TableCell>
                    <TableCell>{new Date(session.created_at).toLocaleString()}</TableCell>
                    <TableCell>{session.expires_at ? new Date(session.expires_at).toLocaleString() : "Never"}</TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={deleteSessionMutation.isPending}
                        onClick={() => deleteSessionMutation.mutate(session.id)}
                      >
                        Revoke
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
          {deleteSessionMutation.error ? <p className="error">{(deleteSessionMutation.error as Error).message}</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
