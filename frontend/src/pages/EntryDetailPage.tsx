import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { DeleteIconButton } from "../components/DeleteIconButton";
import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { GroupGraphView } from "../components/GroupGraphView";
import { LinkEditorModal } from "../components/LinkEditorModal";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  createLink,
  deleteLink,
  getEntry,
  getGroup,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listEntries,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateEntryLinkReadModels, invalidateEntryReadModels } from "../lib/queryInvalidation";
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

const ENTRY_LINK_PICKER_FILTERS = {
  limit: 200,
  offset: 0
} as const;

export function EntryDetailPage() {
  const { entryId } = useParams();
  const queryClient = useQueryClient();
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isLinkEditorOpen, setIsLinkEditorOpen] = useState(false);

  const entryQuery = useQuery({
    queryKey: queryKeys.entries.detail(entryId ?? ""),
    queryFn: () => getEntry(entryId!),
    enabled: Boolean(entryId)
  });

  const groupQuery = useQuery({
    queryKey: queryKeys.groups.detail(entryQuery.data?.group_id ?? ""),
    queryFn: () => getGroup(entryQuery.data!.group_id),
    enabled: Boolean(entryQuery.data?.group_id)
  });

  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });
  const entryPickerQuery = useQuery({
    queryKey: queryKeys.entries.list(ENTRY_LINK_PICKER_FILTERS),
    queryFn: () => listEntries(ENTRY_LINK_PICKER_FILTERS)
  });

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
      setIsEditorOpen(false);
    }
  });

  const createLinkMutation = useMutation({
    mutationFn: (payload: { source_entry_id: string; target_entry_id: string; link_type: string; note?: string }) =>
      createLink(payload.source_entry_id, {
        target_entry_id: payload.target_entry_id,
        link_type: payload.link_type,
        note: payload.note
      }),
    onSuccess: () => {
      invalidateEntryLinkReadModels(queryClient, entryId);
      setIsLinkEditorOpen(false);
    }
  });

  const deleteLinkMutation = useMutation({
    mutationFn: deleteLink,
    onSuccess: () => {
      invalidateEntryLinkReadModels(queryClient, entryId);
    }
  });

  const sortedLinks = useMemo(() => {
    return [...(entryQuery.data?.links ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at));
  }, [entryQuery.data]);

  const entryPickerOptions = useMemo(() => {
    return (entryPickerQuery.data?.items ?? [])
      .map((entry) => ({
        id: entry.id,
        label: `${entry.occurred_at} - ${entry.name} (${entry.id.slice(0, 8)})`
      }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [entryPickerQuery.data]);

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
        <CardHeader className="section-header">
          <CardTitle>Links</CardTitle>
          <Button type="button" size="icon" variant="outline" aria-label="Add link" onClick={() => setIsLinkEditorOpen(true)}>
            <Plus className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          {sortedLinks.length === 0 ? (
            <p className="muted">No links yet.</p>
          ) : (
            <ul className="link-list">
              {sortedLinks.map((link) => (
                <li key={link.id}>
                  <span>
                    {link.source_entry_id.slice(0, 6)}
                    {" -> "}
                    {link.target_entry_id.slice(0, 6)} ({link.link_type})
                  </span>
                  <DeleteIconButton label={`Delete link ${link.source_entry_id} to ${link.target_entry_id}`} onClick={() => deleteLinkMutation.mutate(link.id)} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Entry Group Graph</CardTitle>
          <CardDescription>
            Entry amount: {formatMinor(entry.amount_minor, entry.currency_code)} | Group: {entry.group_id}
          </CardDescription>
          <div className="table-actions">
            <Button asChild variant="outline" size="sm">
              <Link to="/groups">Open groups workspace</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {groupQuery.isLoading ? <p>Loading graph...</p> : null}
          {groupQuery.data ? <GroupGraphView graph={groupQuery.data} /> : <p className="muted">No graph data.</p>}
        </CardContent>
      </Card>

      <EntryEditorModal
        isOpen={isEditorOpen}
        mode="edit"
        entry={entry}
        currencies={currenciesQuery.data ?? []}
        entities={entitiesQuery.data ?? []}
        users={usersQuery.data ?? []}
        tags={tagsQuery.data ?? []}
        currentUserId={currentUserId}
        defaultCurrencyCode={(runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase()}
        isSaving={updateMutation.isPending}
        saveError={(updateMutation.error as Error | null)?.message ?? null}
        onClose={() => setIsEditorOpen(false)}
        onSubmit={(payload: EntryEditorSubmitPayload) => updateMutation.mutate(payload)}
      />

      <LinkEditorModal
        isOpen={isLinkEditorOpen}
        title="Create Link"
        description="Add a directional relation from this entry to another entry."
        entryOptions={entryPickerOptions}
        fixedSourceEntryId={entry.id}
        fixedSourceLabel={`${entry.occurred_at} - ${entry.name} (${entry.id.slice(0, 8)})`}
        entryOptionsLoading={entryPickerQuery.isLoading}
        entryOptionsError={entryPickerQuery.isError ? (entryPickerQuery.error as Error).message : null}
        entryOptionsNotice={
          (entryPickerQuery.data?.total ?? 0) > (entryPickerQuery.data?.items.length ?? 0)
            ? "Entry picker is limited to the first 200 entries."
            : null
        }
        isSaving={createLinkMutation.isPending}
        saveError={createLinkMutation.isError ? (createLinkMutation.error as Error).message : null}
        onClose={() => {
          setIsLinkEditorOpen(false);
          createLinkMutation.reset();
        }}
        onSubmit={(payload) => createLinkMutation.mutate(payload)}
      />
    </div>
  );
}
