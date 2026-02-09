import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { GroupGraphView } from "../components/GroupGraphView";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { NativeSelect } from "../components/ui/native-select";
import {
  createLink,
  deleteLink,
  getEntry,
  getGroup,
  listCurrencies,
  listEntities,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateEntryLinkReadModels, invalidateEntryReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";

function kindLabel(kind: string) {
  return kind === "INCOME" ? "Income" : "Expense";
}

function kindSymbol(kind: string) {
  return kind === "INCOME" ? "+" : "-";
}

export function EntryDetailPage() {
  const { entryId } = useParams();
  const queryClient = useQueryClient();
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [newLink, setNewLink] = useState({ target_entry_id: "", link_type: "RELATED", note: "" });

  const entryQuery = useQuery({
    queryKey: queryKeys.entries.detail(entryId ?? ""),
    queryFn: () => getEntry(entryId!),
    enabled: Boolean(entryId)
  });

  const groupQuery = useQuery({
    queryKey: queryKeys.entries.group(entryQuery.data?.group_id ?? ""),
    queryFn: () => getGroup(entryQuery.data!.group_id),
    enabled: Boolean(entryQuery.data?.group_id)
  });

  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });

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
    mutationFn: () => createLink(entryId!, newLink),
    onSuccess: () => {
      setNewLink({ target_entry_id: "", link_type: "RELATED", note: "" });
      invalidateEntryLinkReadModels(queryClient, entryId);
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
          <CardTitle>Links</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="stack-sm"
            onSubmit={(event) => {
              event.preventDefault();
              createLinkMutation.mutate();
            }}
          >
            <label className="field">
              <span>Target entry id</span>
              <Input
                required
                value={newLink.target_entry_id}
                onChange={(event) => setNewLink((state) => ({ ...state, target_entry_id: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Link type</span>
              <NativeSelect value={newLink.link_type} onChange={(event) => setNewLink((state) => ({ ...state, link_type: event.target.value }))}>
                <option value="RELATED">Related</option>
                <option value="RECURRING">Recurring</option>
                <option value="SPLIT">Split</option>
                <option value="BUNDLE">Bundle</option>
              </NativeSelect>
            </label>
            <label className="field">
              <span>Note</span>
              <Input value={newLink.note} onChange={(event) => setNewLink((state) => ({ ...state, note: event.target.value }))} />
            </label>
            <Button type="submit" disabled={createLinkMutation.isPending}>
              Add link
            </Button>
          </form>

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
                  <Button type="button" variant="destructive" size="sm" onClick={() => deleteLinkMutation.mutate(link.id)}>
                    Remove
                  </Button>
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
        isSaving={updateMutation.isPending}
        saveError={(updateMutation.error as Error | null)?.message ?? null}
        onClose={() => setIsEditorOpen(false)}
        onSubmit={(payload: EntryEditorSubmitPayload) => updateMutation.mutate(payload)}
      />
    </div>
  );
}
