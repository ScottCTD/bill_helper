import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { TagMultiSelect } from "../components/TagMultiSelect";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { NativeSelect } from "../components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  createEntry,
  deleteEntry,
  getEntry,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listEntries,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";
import { formatMinorCompact } from "../lib/format";
import { invalidateEntryReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";

type EditorState = { mode: "create" } | { mode: "edit"; entryId: string } | null;
const ENTRY_FLOW_LABEL_MAX_LENGTH = 18;
const MISSING_ENTITY_LABEL = "(unspecified)";

function kindSymbol(kind: string) {
  if (kind === "INCOME") return "+";
  if (kind === "TRANSFER") return "~";
  return "-";
}

function groupLabel(groupId: string) {
  const isUuidGroupId = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(groupId);
  return isUuidGroupId ? "" : groupId;
}

function normalizedCurrencyCode(currencyCode: string) {
  return currencyCode.trim().toUpperCase() || "CAD";
}

function normalizedEntityLabel(value: string | null): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function compactEntityLabel(value: string, maxLength: number = ENTRY_FLOW_LABEL_MAX_LENGTH): string {
  if (value.length <= maxLength) {
    return value;
  }

  const ellipsis = "...";
  const remainingLength = Math.max(maxLength - ellipsis.length, 2);
  const prefixLength = Math.ceil(remainingLength / 2);
  const suffixLength = Math.max(remainingLength - prefixLength, 1);
  return `${value.slice(0, prefixLength)}${ellipsis}${value.slice(-suffixLength)}`;
}

function entryFlowLabel(fromEntity: string | null, toEntity: string | null): { display: string; full: string } | null {
  const normalizedFrom = normalizedEntityLabel(fromEntity);
  const normalizedTo = normalizedEntityLabel(toEntity);
  if (!normalizedFrom && !normalizedTo) {
    return null;
  }

  const fullFrom = normalizedFrom ?? MISSING_ENTITY_LABEL;
  const fullTo = normalizedTo ?? MISSING_ENTITY_LABEL;
  return {
    display: `${compactEntityLabel(fullFrom)} -> ${compactEntityLabel(fullTo)}`,
    full: `${fullFrom} -> ${fullTo}`
  };
}

export function EntriesPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({
    kind: "",
    tags: [] as string[],
    currencies: [] as string[],
    source: ""
  });
  const [editorState, setEditorState] = useState<EditorState>(null);

  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const entryListFilters = useMemo(
    () => ({
      kind: filters.kind || undefined,
      source: filters.source || undefined,
      limit: 200,
      offset: 0
    }),
    [filters.kind, filters.source]
  );
  const entriesQuery = useQuery({
    queryKey: queryKeys.entries.list(entryListFilters),
    queryFn: () =>
      listEntries(entryListFilters)
  });

  const editingEntryId = editorState?.mode === "edit" ? editorState.entryId : "";
  const editingEntryQuery = useQuery({
    queryKey: queryKeys.entries.detail(editingEntryId),
    queryFn: () => getEntry(editingEntryId),
    enabled: Boolean(editingEntryId)
  });

  const currentUserId = useMemo(
    () => usersQuery.data?.find((user) => user.is_current_user)?.id ?? "",
    [usersQuery.data]
  );

  const createEntryMutation = useMutation({
    mutationFn: createEntry,
    onSuccess: () => {
      invalidateEntryReadModels(queryClient);
      setEditorState(null);
    }
  });

  const updateEntryMutation = useMutation({
    mutationFn: ({ entryId, payload }: { entryId: string; payload: EntryEditorSubmitPayload }) => updateEntry(entryId, payload),
    onSuccess: (_, variables) => {
      invalidateEntryReadModels(queryClient, variables.entryId);
      setEditorState(null);
    }
  });

  const deleteEntryMutation = useMutation({
    mutationFn: deleteEntry,
    onSuccess: () => {
      invalidateEntryReadModels(queryClient);
    }
  });

  const filterCurrencies = useMemo(() => {
    const codes = new Set((currenciesQuery.data ?? []).map((currency) => currency.code));
    entriesQuery.data?.items.forEach((entry) => codes.add(entry.currency_code));
    return Array.from(codes).sort();
  }, [currenciesQuery.data, entriesQuery.data]);

  const currencyFilterOptions = useMemo(
    () =>
      filterCurrencies.map((currency, index) => ({
        id: -1 - index,
        name: normalizedCurrencyCode(currency),
        color: null
      })),
    [filterCurrencies]
  );

  const filteredEntries = useMemo(() => {
    const selectedTagSet = new Set(filters.tags.map((tagName) => tagName.trim().toLowerCase()).filter(Boolean));
    const selectedCurrencySet = new Set(filters.currencies.map((currencyCode) => currencyCode.trim().toUpperCase()).filter(Boolean));
    return (entriesQuery.data?.items ?? []).filter((entry) => {
      if (selectedTagSet.size > 0) {
        const hasMatchingTag = entry.tags.some((tag) => selectedTagSet.has(tag.name.trim().toLowerCase()));
        if (!hasMatchingTag) {
          return false;
        }
      }

      if (selectedCurrencySet.size > 0) {
        const entryCurrencyCode = normalizedCurrencyCode(entry.currency_code);
        if (!selectedCurrencySet.has(entryCurrencyCode)) {
          return false;
        }
      }

      return true;
    });
  }, [entriesQuery.data?.items, filters.currencies, filters.tags]);

  function handleEditorSubmit(payload: EntryEditorSubmitPayload) {
    if (editorState?.mode === "edit") {
      updateEntryMutation.mutate({
        entryId: editorState.entryId,
        payload
      });
      return;
    }

    createEntryMutation.mutate({
      kind: payload.kind,
      occurred_at: payload.occurred_at,
      name: payload.name,
      amount_minor: payload.amount_minor,
      currency_code: payload.currency_code,
      from_entity_id: payload.from_entity_id || undefined,
      from_entity: payload.from_entity || undefined,
      to_entity_id: payload.to_entity_id || undefined,
      to_entity: payload.to_entity || undefined,
      owner_user_id: payload.owner_user_id || undefined,
      markdown_body: payload.markdown_body || undefined,
      tags: payload.tags
    });
  }

  const editorSaveError =
    editorState?.mode === "edit"
      ? (updateEntryMutation.error as Error | null)?.message ?? null
      : (createEntryMutation.error as Error | null)?.message ?? null;

  const editorLoadError = editingEntryQuery.isError ? (editingEntryQuery.error as Error).message : null;

  return (
    <div className="stack-lg">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="table-shell-header">
            <div>
              <h2 className="table-shell-title">Entries</h2>
              <p className="table-shell-subtitle">Double-click a row to open the entry editor.</p>
            </div>
          </div>

          <div className="table-toolbar filter-row">
            <div className="table-toolbar-filters">
              <label className="field min-w-[160px]">
                <span>Kind</span>
                <NativeSelect value={filters.kind} onChange={(event) => setFilters((state) => ({ ...state, kind: event.target.value }))}>
                  <option value="">All</option>
                  <option value="EXPENSE">- Expense</option>
                  <option value="INCOME">+ Income</option>
                  <option value="TRANSFER">~ Transfer</option>
                </NativeSelect>
              </label>
              <label className="field min-w-[180px]">
                <span>Tags</span>
                <TagMultiSelect
                  options={tagsQuery.data ?? []}
                  value={filters.tags}
                  ariaLabel="Tag filter"
                  placeholder="All tags"
                  allowCreate={false}
                  onChange={(nextTags) => setFilters((state) => ({ ...state, tags: nextTags }))}
                />
              </label>
              <label className="field min-w-[150px]">
                <span>Currencies</span>
                <TagMultiSelect
                  options={currencyFilterOptions}
                  value={filters.currencies}
                  ariaLabel="Currency filter"
                  placeholder="All currencies"
                  allowCreate={false}
                  onChange={(nextCurrencies) => setFilters((state) => ({ ...state, currencies: nextCurrencies }))}
                />
              </label>
              <label className="field min-w-[260px] grow">
                <span>Source text</span>
                <Input value={filters.source} onChange={(event) => setFilters((state) => ({ ...state, source: event.target.value }))} />
              </label>
            </div>
            <div className="table-toolbar-action filter-action">
              <Button type="button" size="icon" variant="outline" aria-label="Add entry" onClick={() => setEditorState({ mode: "create" })}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="table-shell">
            {entriesQuery.isLoading ? <p>Loading entries...</p> : null}
            {entriesQuery.isError ? <p className="error">{(entriesQuery.error as Error).message}</p> : null}

            {entriesQuery.data ? (
              <Table className="entries-table">
                <TableHeader>
                  <TableRow>
                    <TableHead className="entries-date-column">Date</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Kind</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Tags</TableHead>
                    <TableHead>Group</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEntries.map((entry) => {
                    const flowLabel = entryFlowLabel(entry.from_entity, entry.to_entity);

                    return (
                      <TableRow
                        key={entry.id}
                        className="entries-table-row"
                        onDoubleClick={() => setEditorState({ mode: "edit", entryId: entry.id })}
                      >
                        <TableCell className="entries-date-column">{entry.occurred_at}</TableCell>
                        <TableCell className="entries-name-cell">
                          <div className="entries-name-stack">
                            <span className="entries-name-title">{entry.name}</span>
                            {flowLabel ? (
                              <span className="entries-name-flow" title={flowLabel.full}>
                                {flowLabel.display}
                              </span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={`kind-indicator ${entry.kind === "INCOME" ? "kind-indicator-income" : entry.kind === "TRANSFER" ? "kind-indicator-transfer" : "kind-indicator-expense"}`}>
                            {kindSymbol(entry.kind)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="entries-amount-cell">
                            <span className="entries-amount-value">{formatMinorCompact(entry.amount_minor)}</span>
                            <span className="entries-amount-currency">{normalizedCurrencyCode(entry.currency_code)}</span>
                          </span>
                        </TableCell>
                        <TableCell>
                          {entry.tags.length > 0 ? (
                            <div className="entries-tag-list">
                              {entry.tags.map((tag) => (
                                <Badge key={tag.id} variant="secondary" className="entries-tag-pill">
                                  {tag.name}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <span className="entries-tag-empty">-</span>
                          )}
                        </TableCell>
                        <TableCell>{groupLabel(entry.group_id)}</TableCell>
                        <TableCell>
                          <div className="table-actions">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="entry-delete-button"
                              onClick={(event) => {
                                event.stopPropagation();
                                deleteEntryMutation.mutate(entry.id);
                              }}
                              onDoubleClick={(event) => event.stopPropagation()}
                            >
                              Delete
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            ) : null}
          </div>
      </CardContent>
      </Card>

      <EntryEditorModal
        isOpen={editorState !== null}
        mode={editorState?.mode ?? "create"}
        entry={editorState?.mode === "edit" ? editingEntryQuery.data ?? null : null}
        currencies={currenciesQuery.data ?? []}
        entities={entitiesQuery.data ?? []}
        users={usersQuery.data ?? []}
        tags={tagsQuery.data ?? []}
        currentUserId={currentUserId}
        defaultCurrencyCode={(runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase()}
        isSaving={createEntryMutation.isPending || updateEntryMutation.isPending}
        loadError={editorLoadError}
        saveError={editorSaveError}
        onClose={() => setEditorState(null)}
        onSubmit={handleEditorSubmit}
      />
    </div>
  );
}
