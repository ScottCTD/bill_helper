import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { DeleteIconButton } from "../components/DeleteIconButton";
import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { TagMultiSelect } from "../components/TagMultiSelect";
import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { WorkspaceToolbar } from "../components/layout/WorkspaceToolbar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { NativeSelect } from "../components/ui/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { useAuth } from "../features/auth";
import {
  createEntry,
  deleteEntry,
  getEntry,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listEntries,
  listFilterGroups,
  listGroups,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";
import { formatMinorCompact } from "../lib/format";
import { resolveTagColor } from "../lib/tagColors";
import { invalidateEntryReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";

type EditorState = { mode: "create" } | { mode: "edit"; entryId: string } | null;
const ENTRY_FLOW_LABEL_MAX_LENGTH = 18;
const MISSING_ENTITY_LABEL = "(unspecified)";
const MISSING_ENTITY_MARKER_LABEL = "Missing entity";
const ENTRIES_PAGE_SIZE = 200;
const ENTRIES_LOAD_AHEAD_ROOT_MARGIN = "360px 0px";

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

function kindToneClass(kind: string) {
  if (kind === "INCOME") return "entries-amount-marker-income";
  if (kind === "TRANSFER") return "entries-amount-marker-transfer";
  return "entries-amount-marker-expense";
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
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const initialFilterGroupId = searchParams.get("filter_group_id") ?? "";
  const [filters, setFilters] = useState({
    kind: "",
    tags: [] as string[],
    currencies: [] as string[],
    source: "",
    filterGroupId: initialFilterGroupId
  });
  const [editorState, setEditorState] = useState<EditorState>(null);

  const currenciesQuery = useQuery({ queryKey: queryKeys.properties.currencies, queryFn: listCurrencies });
  const runtimeSettingsQuery = useQuery({ queryKey: queryKeys.settings.runtime, queryFn: getRuntimeSettings });
  const entitiesQuery = useQuery({ queryKey: queryKeys.properties.entities, queryFn: listEntities });
  const usersQuery = useQuery({ queryKey: queryKeys.properties.users, queryFn: listUsers });
  const groupsQuery = useQuery({
    queryKey: queryKeys.groups.list,
    queryFn: listGroups,
    enabled: editorState !== null
  });
  const filterGroupsQuery = useQuery({
    queryKey: queryKeys.filterGroups.list,
    queryFn: listFilterGroups
  });
  const tagsQuery = useQuery({ queryKey: queryKeys.properties.tags, queryFn: listTags });
  const entryListFilters = useMemo(
    () => ({
      kind: filters.kind || undefined,
      source: filters.source || undefined,
      filter_group_id: filters.filterGroupId || undefined
    }),
    [filters.filterGroupId, filters.kind, filters.source]
  );
  const entriesQuery = useInfiniteQuery({
    queryKey: queryKeys.entries.list(entryListFilters),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      listEntries({
        ...entryListFilters,
        limit: ENTRIES_PAGE_SIZE,
        offset: pageParam
      }),
    getNextPageParam: (lastPage, allPages) => {
      const loadedCount = allPages.reduce((total, page) => total + page.items.length, 0);
      return loadedCount < lastPage.total ? loadedCount : undefined;
    }
  });

  const editingEntryId = editorState?.mode === "edit" ? editorState.entryId : "";
  const editingEntryQuery = useQuery({
    queryKey: queryKeys.entries.detail(editingEntryId),
    queryFn: () => getEntry(editingEntryId),
    enabled: Boolean(editingEntryId)
  });

  const currentUserId = auth.session?.user.id ?? usersQuery.data?.find((user) => user.is_current_user)?.id ?? "";

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

  const loadedEntries = useMemo(
    () => entriesQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [entriesQuery.data]
  );

  const totalEntries = entriesQuery.data?.pages[entriesQuery.data.pages.length - 1]?.total ?? 0;
  const loadedEntryCount = loadedEntries.length;

  const filterCurrencies = useMemo(() => {
    const codes = new Set((currenciesQuery.data ?? []).map((currency) => currency.code));
    loadedEntries.forEach((entry) => codes.add(entry.currency_code));
    return Array.from(codes).sort();
  }, [currenciesQuery.data, loadedEntries]);

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
    return loadedEntries.filter((entry) => {
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
  }, [filters.currencies, filters.tags, loadedEntries]);

  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (
      sentinel === null ||
      !entriesQuery.hasNextPage ||
      entriesQuery.isFetchingNextPage ||
      typeof IntersectionObserver !== "function"
    ) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (!entry?.isIntersecting) {
          return;
        }
        void entriesQuery.fetchNextPage();
      },
      { rootMargin: ENTRIES_LOAD_AHEAD_ROOT_MARGIN }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [entriesQuery.fetchNextPage, entriesQuery.hasNextPage, entriesQuery.isFetchingNextPage]);

  useEffect(() => {
    const nextFilterGroupId = searchParams.get("filter_group_id") ?? "";
    setFilters((state) => (state.filterGroupId === nextFilterGroupId ? state : { ...state, filterGroupId: nextFilterGroupId }));
  }, [searchParams]);

  function updateFilterGroupSelection(nextFilterGroupId: string) {
    setFilters((state) => ({ ...state, filterGroupId: nextFilterGroupId }));
    const nextSearchParams = new URLSearchParams(searchParams);
    if (nextFilterGroupId) {
      nextSearchParams.set("filter_group_id", nextFilterGroupId);
    } else {
      nextSearchParams.delete("filter_group_id");
    }
    setSearchParams(nextSearchParams);
  }

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
      owner_user_id: payload.owner_user_id,
      direct_group_id: payload.direct_group_id || undefined,
      direct_group_member_role: payload.direct_group_member_role ?? undefined,
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
    <div className="page stack-lg">
      <PageHeader title="Entries" description="Search and edit ledger rows." />

      <WorkspaceSection>
        <WorkspaceToolbar className="filter-row">
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
              <label className="field min-w-[180px]">
                <span>Filter group</span>
                <NativeSelect value={filters.filterGroupId} onChange={(event) => updateFilterGroupSelection(event.target.value)}>
                  <option value="">All groups</option>
                  {(filterGroupsQuery.data ?? []).map((filterGroup) => (
                    <option key={filterGroup.id} value={filterGroup.id}>
                      {filterGroup.name}
                    </option>
                  ))}
                </NativeSelect>
              </label>
            </div>
            <div className="table-toolbar-action filter-action">
              <Button type="button" size="icon" variant="outline" aria-label="Add entry" onClick={() => setEditorState({ mode: "create" })}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
        </WorkspaceToolbar>

        <div className="table-shell">
          {entriesQuery.isLoading ? <p>Loading entries...</p> : null}
          {entriesQuery.isError ? <p className="error">{(entriesQuery.error as Error).message}</p> : null}

          {entriesQuery.data ? (
            <>
              <Table className="entries-table table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="entries-date-column">Date</TableHead>
                    <TableHead className="entries-name-column">Name</TableHead>
                    <TableHead className="entries-amount-column">Amount</TableHead>
                    <TableHead className="entries-tags-column">Tags</TableHead>
                    <TableHead className="entries-actions-column">
                      <span className="sr-only">Actions</span>
                    </TableHead>
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
                        <TableCell className="entries-name-column entries-name-cell">
                          <div className="entries-name-stack">
                            <span className="entries-name-title">{entry.name}</span>
                            {flowLabel ? (
                              <span className="entries-name-flow" title={flowLabel.full}>
                                {flowLabel.display}
                              </span>
                            ) : null}
                            {entry.from_entity_missing || entry.to_entity_missing ? (
                              <span>
                                <Badge variant="outline">{MISSING_ENTITY_MARKER_LABEL}</Badge>
                              </span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="entries-amount-column">
                          <span className="entries-amount-cell">
                            <span className={`entries-amount-marker ${kindToneClass(entry.kind)}`} aria-hidden="true">
                              {kindSymbol(entry.kind)}
                            </span>
                            <span className="sr-only">{kindLabel(entry.kind)}</span>
                            <span className="entries-amount-value">{formatMinorCompact(entry.amount_minor)}</span>
                            <span className="entries-amount-currency">{normalizedCurrencyCode(entry.currency_code)}</span>
                          </span>
                        </TableCell>
                        <TableCell className="entries-tags-column">
                          {entry.tags.length > 0 ? (
                            <div className="entries-tag-list">
                              {entry.tags.map((tag) => {
                                const color = resolveTagColor(tag.name, tag.color);
                                return (
                                  <Badge key={tag.id} variant="outline" className="entries-tag-pill" style={{ borderColor: color }} title={tag.name}>
                                    <span className="entries-tag-pill-color" aria-hidden="true" style={{ backgroundColor: color }} />
                                    <span className="entries-tag-pill-label">{tag.name}</span>
                                  </Badge>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="entries-tag-empty">-</span>
                          )}
                        </TableCell>
                        <TableCell className="entries-actions-column">
                          <div className="table-actions">
                            <DeleteIconButton
                              label={`Delete entry ${entry.name}`}
                              onClick={(event) => {
                                event.stopPropagation();
                                deleteEntryMutation.mutate(entry.id);
                              }}
                              onDoubleClick={(event) => event.stopPropagation()}
                            />
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              <div className="entries-load-more-shell">
                <p className="entries-load-more-status">
                  {entriesQuery.hasNextPage
                    ? `Loaded ${loadedEntryCount} of ${totalEntries} entries. Scroll to load more.`
                    : totalEntries > 0
                      ? `Loaded all ${totalEntries} entries.`
                      : "No entries found."}
                </p>
                {entriesQuery.hasNextPage ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void entriesQuery.fetchNextPage()}
                    disabled={entriesQuery.isFetchingNextPage}
                    aria-label="Load more entries"
                  >
                    {entriesQuery.isFetchingNextPage ? "Loading more..." : "Load more"}
                  </Button>
                ) : null}
                <div ref={loadMoreRef} className="entries-load-more-sentinel" aria-hidden="true" />
              </div>
            </>
          ) : null}
        </div>
      </WorkspaceSection>

      <EntryEditorModal
        isOpen={editorState !== null}
        mode={editorState?.mode ?? "create"}
        entry={editorState?.mode === "edit" ? editingEntryQuery.data ?? null : null}
        currencies={currenciesQuery.data ?? []}
        entities={entitiesQuery.data ?? []}
        groups={groupsQuery.data ?? []}
        tags={tagsQuery.data ?? []}
        currentUserId={currentUserId}
        defaultCurrencyCode={(runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase()}
        entryTaggingModel={runtimeSettingsQuery.data?.entry_tagging_model}
        isSaving={createEntryMutation.isPending || updateEntryMutation.isPending}
        loadError={editorLoadError}
        saveError={editorSaveError}
        onClose={() => setEditorState(null)}
        onSubmit={handleEditorSubmit}
      />
    </div>
  );
}
