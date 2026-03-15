/**
 * CALLING SPEC:
 * - Purpose: own query, mutation, selection, and submit state for the filters workspace page.
 * - Inputs: React callers that mount the filters route and provide framework event wiring.
 * - Outputs: a page model consumed by the filter-groups route and workspace body components.
 * - Side effects: React Query reads and mutations plus local UI state management.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createFilterGroup, deleteFilterGroup, listFilterGroups, listTags, updateFilterGroup } from "../../lib/api";
import { invalidateFilterGroupReadModels } from "../../lib/queryInvalidation";
import { queryKeys } from "../../lib/queryKeys";
import type { FilterGroup } from "../../lib/types";
import {
  createExistingEditorSession,
  createNewEditorSession,
  isEditorSessionDirty,
  isSameEditorTarget,
  isSystemUntaggedSession,
  pickNextFilterGroupId,
  toFilterGroupSubmitPayload,
  updateSessionFormState,
  type FilterGroupEditorSession,
  type FilterGroupEditorTarget
} from "./filterGroupEditorState";

function serializeSession(session: FilterGroupEditorSession | null): string {
  if (!session) {
    return "null";
  }
  return JSON.stringify(session);
}

export function useFilterGroupsPageModel() {
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
  const selectedFilterGroup =
    session?.kind === "existing"
      ? filterGroups.find((filterGroup) => filterGroup.id === session.filterGroupId) ?? null
      : null;
  const isDirty = session ? isEditorSessionDirty(session) : false;
  const isSystemUntagged = isSystemUntaggedSession(session);

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

  const isPending =
    createMutation.isPending ||
    (session?.kind === "existing" && (activeUpdateId === session.filterGroupId || activeDeleteId === session.filterGroupId));

  function handleSubmit() {
    if (!session || isSystemUntaggedSession(session)) {
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

  return {
    filterGroupsQuery,
    tagsQuery,
    filterGroups,
    tags,
    preferredTagName,
    session,
    selectedFilterGroup,
    selectedTarget,
    discardDialogOpen,
    mutationError,
    isDirty,
    isPending: Boolean(isPending),
    isSystemUntagged,
    canSubmit: Boolean(session) && !isSystemUntagged && Boolean(session?.formState.name.trim()) && isDirty && !isPending,
    showHeaderSubmit: Boolean(session) && !isSystemUntagged,
    submitLabel: session?.kind === "new" ? "Create group" : "Save changes",
    submitPendingLabel: session?.kind === "new" ? "Creating..." : "Saving...",
    requestTarget,
    confirmDiscardChanges,
    handleDiscardDialogOpenChange,
    handleSubmit,
    handleDelete,
    updateFormState: (nextFormState: FilterGroupEditorSession["formState"]) =>
      setSession((current) => (current ? updateSessionFormState(current, nextFormState) : current))
  };
}

export type FilterGroupsPageModel = ReturnType<typeof useFilterGroupsPageModel>;
