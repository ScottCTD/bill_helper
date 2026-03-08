import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { GroupGraphView } from "../components/GroupGraphView";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  getEntry,
  getGroup,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listGroups,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateEntryReadModels, invalidateGroupReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";

function kindLabel(kind: string) {
  if (kind === "INCOME") return "Income";
  if (kind === "TRANSFER") return "Transfer";
  return "Expense";
}

function kindSymbol(kind: string) {
  if (kind === "INCOME") return "+";
  if (kind === "TRANSFER") return "~";
  return "-";
}

export function EntryDetailPage() {
  const { entryId } = useParams();
  const queryClient = useQueryClient();
  const [isEditorOpen, setIsEditorOpen] = useState(false);

  const entryQuery = useQuery({
    queryKey: queryKeys.entries.detail(entryId ?? ""),
    queryFn: () => getEntry(entryId!),
    enabled: Boolean(entryId)
  });

  const directGroupId = entryQuery.data?.direct_group?.id ?? "";
  const groupQuery = useQuery({
    queryKey: queryKeys.groups.detail(directGroupId),
    queryFn: () => getGroup(directGroupId),
    enabled: Boolean(directGroupId)
  });

  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const groupsQuery = useQuery({
    queryKey: queryKeys.groups.list,
    queryFn: listGroups,
    enabled: isEditorOpen
  });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });

  const currentUserId = useMemo(
    () => usersQuery.data?.find((user) => user.is_current_user)?.id ?? "",
    [usersQuery.data]
  );

  const updateMutation = useMutation({
    mutationFn: (payload: EntryEditorSubmitPayload) => updateEntry(entryId!, payload),
    onSuccess: () => {
      if (!entryId) {
        return;
      }
      invalidateEntryReadModels(queryClient, entryId);
      invalidateGroupReadModels(queryClient, entryId, directGroupId || undefined);
      setIsEditorOpen(false);
    }
  });

  if (!entryId) {
    return <p>Missing entry id.</p>;
  }

  if (entryQuery.isLoading) {
    return <p>Loading entry...</p>;
  }

  if (entryQuery.isError || !entryQuery.data) {
    return <p className="error">Unable to load entry.</p>;
  }

  const entry = entryQuery.data;

  return (
    <div className="stack-lg">
      <Card>
        <CardHeader className="section-header gap-3">
          <div>
            <CardTitle>{entry.name}</CardTitle>
            <CardDescription>
              {entry.occurred_at} | {kindLabel(entry.kind)} {kindSymbol(entry.kind)} | {formatMinor(entry.amount_minor, entry.currency_code)}
            </CardDescription>
          </div>
          <div className="table-actions">
            <Button asChild variant="outline" size="sm">
              <Link to="/entries">Back to entries</Link>
            </Button>
            <Button type="button" size="sm" onClick={() => setIsEditorOpen(true)}>
              Edit in popup
            </Button>
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Entry Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm">
          <div>
            <strong>From:</strong> {entry.from_entity || "(unspecified)"}
            {entry.from_entity_missing ? (
              <span className="ml-2">
                <Badge variant="outline">Missing entity</Badge>
              </span>
            ) : null}
          </div>
          <div>
            <strong>To:</strong> {entry.to_entity || "(unspecified)"}
            {entry.to_entity_missing ? (
              <span className="ml-2">
                <Badge variant="outline">Missing entity</Badge>
              </span>
            ) : null}
          </div>
          <div>
            <strong>Owner:</strong> {entry.owner || "(none)"}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="section-header gap-3">
          <div>
            <CardTitle>Group Context</CardTitle>
            <CardDescription>
              {entry.direct_group
                ? `Direct group: ${entry.direct_group.name} (${entry.direct_group.group_type})`
                : "This entry is currently ungrouped."}
            </CardDescription>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link to="/groups">Open groups workspace</Link>
          </Button>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm">
          {entry.direct_group ? (
            <>
              <div>
                <strong>Direct group:</strong> {entry.direct_group.name}
              </div>
              <div>
                <strong>Group path:</strong> {entry.group_path.map((group) => group.name).join(" -> ")}
              </div>
            </>
          ) : (
            <p className="muted">Add this entry to a group from the groups workspace.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Direct Group Graph</CardTitle>
          <CardDescription>
            {entry.direct_group
              ? `Showing ${entry.direct_group.name} and its direct members.`
              : "Grouped entries render here once the entry has a direct group."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!entry.direct_group ? <p className="muted">No direct group assigned.</p> : null}
          {entry.direct_group && groupQuery.isLoading ? <p>Loading group graph...</p> : null}
          {entry.direct_group && groupQuery.isError ? <p className="error">Unable to load group graph.</p> : null}
          {entry.direct_group && groupQuery.data ? <GroupGraphView graph={groupQuery.data} /> : null}
        </CardContent>
      </Card>

      <EntryEditorModal
        isOpen={isEditorOpen}
        mode="edit"
        entry={entry}
        currencies={currenciesQuery.data ?? []}
        entities={entitiesQuery.data ?? []}
        users={usersQuery.data ?? []}
        groups={groupsQuery.data ?? []}
        tags={tagsQuery.data ?? []}
        currentUserId={currentUserId}
        defaultCurrencyCode={runtimeSettingsQuery.data?.default_currency_code ?? "USD"}
        isSaving={updateMutation.isPending}
        saveError={updateMutation.isError ? (updateMutation.error as Error).message : undefined}
        onClose={() => setIsEditorOpen(false)}
        onSubmit={(payload) => updateMutation.mutate(payload)}
      />
    </div>
  );
}
