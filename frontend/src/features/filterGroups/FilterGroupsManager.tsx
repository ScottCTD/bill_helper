/**
 * CALLING SPEC:
 * - Purpose: render the `FilterGroupsManager` React UI module.
 * - Inputs: callers that import `frontend/src/features/filterGroups/FilterGroupsManager.tsx` and pass module-defined arguments or framework events.
 * - Outputs: React components and UI helpers exported by `FilterGroupsManager`.
 * - Side effects: React rendering and user event wiring.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listTags, createFilterGroup, deleteFilterGroup, listFilterGroups, updateFilterGroup } from "../../lib/api";
import { invalidateFilterGroupReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { FilterGroup } from "../../lib/types";
import { DiscardChangesDialog } from "./DiscardChangesDialog";
import {
  createExistingEditorSession,
  createNewEditorSession,
  isEditorSessionDirty,
  isSameEditorTarget,
  pickNextFilterGroupId,
  toFilterGroupSubmitPayload,
  updateSessionFormState,
  type FilterGroupEditorSession,
  type FilterGroupEditorTarget
} from "./filterGroupEditorState";
import { FilterGroupEditorPanel } from "./FilterGroupEditorPanel";
import { FilterGroupsSidebar } from "./FilterGroupsSidebar";

function serializeSession(session: FilterGroupEditorSession | null): string {
  if (!session) {
    return "null";
  }
  return JSON.stringify(session);
}

export function FilterGroupsManager() {
  const queryClient = useQueryClient();
  const filterGroupsQuery = useQuery({
    queryKey: queryKeys.filterGroups.list,
    queryFn: listFilterGroups
  });
  const tagsQuery = useQuery({
    queryKey: queryKeys.properties.tags,
    queryFn: listTags
  });
  const [session, setSession] = useState<FilterGroupEditorSession | null>(null);
  const [pendingTarget, setPendingTarget] = useState<FilterGroupEditorTarget | null>(null);
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);
  const [activeUpdateId, setActiveUpdateId] = useState<string | null>(null);
  const [activeDeleteId, setActiveDeleteId] = useState<string | null>(null);
  const filterGroups = filterGroupsQuery.data ?? [];
  const tags = tagsQuery.data ?? [];
  const preferredTagName = tags[0]?.name;

  const createMutation = useMutation({
    mutationFn: createFilterGroup,
    onSuccess: (filterGroup) => {
      setSession(createExistingEditorSession(filterGroup));
      invalidateFilterGroupReadModels(queryClient);
    }
  });
  const updateMutation = useMutation({
    mutationFn: ({ filterGroupId, payload }: { filterGroupId: string; payload: Parameters<typeof updateFilterGroup>[1] }) =>
      updateFilterGroup(filterGroupId, payload),
    onSuccess: (filterGroup) => {
      setActiveUpdateId(null);
      setSession(createExistingEditorSession(filterGroup));
      invalidateFilterGroupReadModels(queryClient);
    },
    onError: () => {
      setActiveUpdateId(null);
    }
  });
  const deleteMutation = useMutation({
    mutationFn: deleteFilterGroup,
    onSuccess: (_result, filterGroupId) => {
      const nextFilterGroupId = pickNextFilterGroupId(filterGroups, filterGroupId);
      setActiveDeleteId(null);
      if (nextFilterGroupId) {
        const nextFilterGroup = filterGroups.find((filterGroup) => filterGroup.id === nextFilterGroupId) ?? null;
        setSession(nextFilterGroup ? createExistingEditorSession(nextFilterGroup) : null);
      } else {
        setSession(null);
      }
      invalidateFilterGroupReadModels(queryClient);
    },
    onError: () => {
      setActiveDeleteId(null);
    }
  });

  function resetMutations() {
    createMutation.reset();
    updateMutation.reset();
    deleteMutation.reset();
    setActiveUpdateId(null);
    setActiveDeleteId(null);
  }

  function applyTarget(nextTarget: FilterGroupEditorTarget) {
    resetMutations();
    if (nextTarget.kind === "new") {
      setSession(createNewEditorSession());
      return;
    }
    const filterGroup = filterGroups.find((candidate) => candidate.id === nextTarget.filterGroupId);
    if (!filterGroup) {
      return;
    }
    setSession(createExistingEditorSession(filterGroup));
  }

  function requestTarget(nextTarget: FilterGroupEditorTarget) {
    if (isSameEditorTarget(session, nextTarget)) {
      return;
    }
    if (session && isEditorSessionDirty(session)) {
      setPendingTarget(nextTarget);
      setDiscardDialogOpen(true);
      return;
    }
    applyTarget(nextTarget);
  }

  function confirmDiscardChanges() {
    const nextTarget = pendingTarget;
    setPendingTarget(null);
    setDiscardDialogOpen(false);
    if (!nextTarget) {
      return;
    }
    applyTarget(nextTarget);
  }

  function handleDiscardDialogOpenChange(open: boolean) {
    setDiscardDialogOpen(open);
    if (!open) {
      setPendingTarget(null);
    }
  }

  useEffect(() => {
    if (!session) {
      if (filterGroups.length > 0) {
        setSession(createExistingEditorSession(filterGroups[0]));
      }
      return;
    }

    if (session.kind === "new") {
      return;
    }

    const matchingFilterGroup = filterGroups.find((filterGroup) => filterGroup.id === session.filterGroupId);
    if (!matchingFilterGroup) {
      setSession(filterGroups[0] ? createExistingEditorSession(filterGroups[0]) : null);
      return;
    }

    if (isEditorSessionDirty(session)) {
      return;
    }

    const nextSession = createExistingEditorSession(matchingFilterGroup);
    if (serializeSession(nextSession) !== serializeSession(session)) {
      setSession(nextSession);
    }
  }, [filterGroups, session]);

  const selectedTarget: FilterGroupEditorTarget | null = session
    ? session.kind === "new"
      ? { kind: "new" }
      : { kind: "existing", filterGroupId: session.filterGroupId }
    : null;

  const mutationError =
    (createMutation.error as Error | null)?.message ??
    (updateMutation.error as Error | null)?.message ??
    (deleteMutation.error as Error | null)?.message ??
    null;

  const currentEditorPending =
    createMutation.isPending ||
    (session?.kind === "existing" && (activeUpdateId === session.filterGroupId || activeDeleteId === session.filterGroupId));

  function handleSubmit() {
    if (!session) {
      return;
    }
    const payload = toFilterGroupSubmitPayload(session.formState);
    if (session.kind === "new") {
      createMutation.mutate(payload);
      return;
    }
    setActiveUpdateId(session.filterGroupId);
    updateMutation.mutate({
      filterGroupId: session.filterGroupId,
      payload
    });
  }

  function handleDelete(filterGroupId: string) {
    setActiveDeleteId(filterGroupId);
    deleteMutation.mutate(filterGroupId);
  }

  return (
    <>
      <div className="grid gap-4">
        <p className="muted text-sm">
          These rules drive dashboard classification and the saved group shortcut in entries. Pick a group on the left, edit it on the right, and use advanced mode only when you need nested logic.
        </p>

        {filterGroupsQuery.isError ? <p className="error">Failed to load filter groups: {(filterGroupsQuery.error as Error).message}</p> : null}

        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div className="xl:sticky xl:top-6 xl:self-start">
            <FilterGroupsSidebar
              filterGroups={filterGroups}
              selectedTarget={selectedTarget}
              onCreateNew={() => requestTarget({ kind: "new" })}
              onSelectExisting={(filterGroupId) => requestTarget({ kind: "existing", filterGroupId })}
            />
          </div>

          <div className="min-w-0">
            {filterGroupsQuery.isLoading && !session ? <p>Loading filter groups...</p> : null}

            {session ? (
              <FilterGroupEditorPanel
                key={session.kind === "new" ? "new" : session.filterGroupId}
                session={session}
                tags={tags}
                preferredTagName={preferredTagName}
                isDirty={isEditorSessionDirty(session)}
                isPending={Boolean(currentEditorPending)}
                mutationError={mutationError}
                tagLoadError={tagsQuery.isError ? (tagsQuery.error as Error).message : null}
                onChange={(nextFormState) => setSession((current) => (current ? updateSessionFormState(current, nextFormState) : current))}
                onSubmit={handleSubmit}
                onDelete={session.kind === "existing" && !session.isDefault ? () => handleDelete(session.filterGroupId) : undefined}
              />
            ) : (
              <div className="rounded-2xl border border-dashed border-border bg-secondary/25 p-6 text-sm text-muted-foreground">
                No filter groups are available yet.
              </div>
            )}
          </div>
        </div>
      </div>

      <DiscardChangesDialog open={discardDialogOpen} onOpenChange={handleDiscardDialogOpenChange} onConfirm={confirmDiscardChanges} />
    </>
  );
}
