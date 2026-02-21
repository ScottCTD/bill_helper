import { Plus } from "lucide-react";

import type { Account } from "../../lib/types";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { toDateLabel } from "./helpers";

interface AccountsTableSectionProps {
  accountSearch: string;
  onAccountSearchChange: (value: string) => void;
  onOpenCreateDialog: () => void;
  accounts: Account[] | undefined;
  filteredAccounts: Account[];
  selectedAccountId: string;
  onSelectAccount: (accountId: string) => void;
  onEditAccount: (accountId: string) => void;
  ownerNameForId: (ownerUserId: string | null) => string;
  isLoading: boolean;
  errorMessage: string | null;
}

export function AccountsTableSection(props: AccountsTableSectionProps) {
  const {
    accountSearch,
    onAccountSearchChange,
    onOpenCreateDialog,
    accounts,
    filteredAccounts,
    selectedAccountId,
    onSelectAccount,
    onEditAccount,
    ownerNameForId,
    isLoading,
    errorMessage
  } = props;

  return (
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
                onChange={(event) => onAccountSearchChange(event.target.value)}
                placeholder="Name, owner, or currency"
              />
            </label>
          </div>
          <div className="table-toolbar-action filter-action">
            <Button type="button" size="icon" variant="outline" aria-label="Create account" onClick={onOpenCreateDialog}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="table-shell">
          {isLoading ? <p>Loading accounts...</p> : null}
          {errorMessage ? <p className="error">{errorMessage}</p> : null}

          {accounts ? (
            filteredAccounts.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
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
                      onClick={() => onSelectAccount(account.id)}
                    >
                      <TableCell className="font-medium">{account.name}</TableCell>
                      <TableCell>{ownerNameForId(account.owner_user_id)}</TableCell>
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
                              onEditAccount(account.id);
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
  );
}
