import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { EntryEditorModal, type EntryEditorSubmitPayload } from "../components/EntryEditorModal";
import { GroupDetailModal } from "../components/GroupDetailModal";
import { GroupEditorModal } from "../components/GroupEditorModal";
import { GroupMemberEditorModal } from "../components/GroupMemberEditorModal";
import { PageHeader } from "../components/layout/PageHeader";
import { WorkspaceSection } from "../components/layout/WorkspaceSection";
import { WorkspaceToolbar } from "../components/layout/WorkspaceToolbar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { useAuth } from "../features/auth";
import {
  addGroupMember,
  createGroup,
  deleteGroup,
  deleteGroupMember,
    getEntry,
  getGroup,
    getRuntimeSettings,
    listCurrencies,
    listEntities,
  listEntries,
  listGroups,
    listTags,
    listUsers,
    updateEntry,
  updateGroup
} from "../lib/api";
import { invalidateEntryReadModels, invalidateGroupReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { GroupMemberCreatePayload, GroupSummary } from "../lib/types";
import { cn } from "../lib/utils";

const ENTRY_PICKER_FILTERS = {
  limit: 200,
  offset: 0
} as const;

function groupRangeLabel(summary: GroupSummary): string {
  if (!summary.first_occurred_at || !summary.last_occurred_at) {
    return "No entries yet";
  }
  if (summary.first_occurred_at === summary.last_occurred_at) {
    return summary.first_occurred_at;
  }
  return `${summary.first_occurred_at} to ${summary.last_occurred_at}`;
}

function groupHierarchyLabel(summary: GroupSummary, groupsById: Map<string, GroupSummary>): string {
  if (!summary.parent_group_id) {
    return "Top level";
  }
  const parent = groupsById.get(summary.parent_group_id);
  return parent ? `Child of ${parent.name}` : "Child group";
}

function rowKeyDownHandler(event: React.KeyboardEvent<HTMLTableRowElement>, onOpen: () => void) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onOpen();
  }
}

export function GroupsPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [groupSearch, setGroupSearch] = useState("");
  const deferredGroupSearch = useDeferredValue(groupSearch);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isCreateGroupOpen, setIsCreateGroupOpen] = useState(false);
  const [isRenameGroupOpen, setIsRenameGroupOpen] = useState(false);
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);
  const [editingEntryId, setEditingEntryId] = useState("");

  const groupsQuery = useQuery({
    queryKey: queryKeys.groups.list,
    queryFn: listGroups
  });

  const entryPickerQuery = useQuery({
    queryKey: queryKeys.entries.list(ENTRY_PICKER_FILTERS),
    queryFn: () => listEntries(ENTRY_PICKER_FILTERS)
  });

  const groupGraphQuery = useQuery({
    queryKey: queryKeys.groups.detail(selectedGroupId),
    queryFn: () => getGroup(selectedGroupId),
    enabled: isDetailOpen && Boolean(selectedGroupId)
  });

  const currenciesQuery = useQuery({
    queryKey: queryKeys.properties.currencies,
    queryFn: listCurrencies,
    enabled: Boolean(editingEntryId)
  });

  const runtimeSettingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
    enabled: Boolean(editingEntryId)
  });

  const entitiesQuery = useQuery({
    queryKey: queryKeys.properties.entities,
    queryFn: listEntities,
    enabled: Boolean(editingEntryId)
  });

  const usersQuery = useQuery({
    queryKey: queryKeys.properties.users,
    queryFn: listUsers,
    enabled: Boolean(editingEntryId)
  });

  const tagsQuery = useQuery({
    queryKey: queryKeys.properties.tags,
    queryFn: listTags,
    enabled: Boolean(editingEntryId)
  });

  const editingEntryQuery = useQuery({
    queryKey: queryKeys.entries.detail(editingEntryId),
    queryFn: () => getEntry(editingEntryId),
    enabled: Boolean(editingEntryId)
  });

  useEffect(() => {
    if (!selectedGroupId) {
      return;
    }
    const selectionStillExists = (groupsQuery.data ?? []).some((group) => group.id === selectedGroupId);
    if (!selectionStillExists) {
      setSelectedGroupId("");
      setIsDetailOpen(false);
      setIsRenameGroupOpen(false);
      setIsAddMemberOpen(false);
    }
  }, [groupsQuery.data, selectedGroupId]);

  const createGroupMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: (group) => {
      queryClient.setQueryData<GroupSummary[]>(queryKeys.groups.list, (current) => {
        const existing = current ?? [];
        return [group, ...existing.filter((candidate) => candidate.id !== group.id)];
      });
      invalidateGroupReadModels(queryClient);
      setSelectedGroupId(group.id);
      setIsCreateGroupOpen(false);
      setIsDetailOpen(true);
    }
  });

  const renameGroupMutation = useMutation({
    mutationFn: (payload: { name: string }) => updateGroup(selectedGroupId, payload),
    onSuccess: (group) => {
      queryClient.setQueryData<GroupSummary[]>(queryKeys.groups.list, (current) => {
        return (current ?? []).map((candidate) => (candidate.id === group.id ? group : candidate));
      });
      invalidateGroupReadModels(queryClient, undefined, selectedGroupId);
      setIsRenameGroupOpen(false);
    }
  });

  const deleteGroupMutation = useMutation({
    mutationFn: (groupId: string) => deleteGroup(groupId),
    onSuccess: (_result, groupId) => {
      queryClient.setQueryData<GroupSummary[]>(queryKeys.groups.list, (current) => {
        return (current ?? []).filter((candidate) => candidate.id !== groupId);
      });
      invalidateGroupReadModels(queryClient);
      setSelectedGroupId("");
      setIsDetailOpen(false);
      setIsRenameGroupOpen(false);
      setIsAddMemberOpen(false);
    }
  });

  const addGroupMemberMutation = useMutation({
    mutationFn: (payload: GroupMemberCreatePayload) => addGroupMember(selectedGroupId, payload),
    onSuccess: () => {
      invalidateGroupReadModels(queryClient, undefined, selectedGroupId);
      setIsAddMemberOpen(false);
    }
  });

  const deleteGroupMemberMutation = useMutation({
    mutationFn: (membershipId: string) => deleteGroupMember(selectedGroupId, membershipId),
    onSuccess: () => {
      invalidateGroupReadModels(queryClient, undefined, selectedGroupId);
    }
  });

  const updateEntryMutation = useMutation({
    mutationFn: ({ entryId, payload }: { entryId: string; payload: EntryEditorSubmitPayload }) => updateEntry(entryId, payload),
    onSuccess: (_result, variables) => {
      invalidateEntryReadModels(queryClient, variables.entryId);
      setEditingEntryId("");
    }
  });

  const filteredGroups = useMemo(() => {
    const normalizedSearch = deferredGroupSearch.trim().toLowerCase();
    if (!normalizedSearch) {
      return groupsQuery.data ?? [];
    }
    return (groupsQuery.data ?? []).filter((group) => {
      return (
        group.name.toLowerCase().includes(normalizedSearch) ||
        group.group_type.toLowerCase().includes(normalizedSearch) ||
        group.id.toLowerCase().includes(normalizedSearch)
      );
    });
  }, [deferredGroupSearch, groupsQuery.data]);

  const groupsById = useMemo(() => {
    return new Map((groupsQuery.data ?? []).map((group) => [group.id, group]));
  }, [groupsQuery.data]);

  const selectedGroupSummary = useMemo(
    () => groupsQuery.data?.find((group) => group.id === selectedGroupId) ?? null,
    [groupsQuery.data, selectedGroupId]
  );

  const selectedParentGroup = useMemo(() => {
    if (!selectedGroupSummary?.parent_group_id) {
      return null;
    }
    return groupsById.get(selectedGroupSummary.parent_group_id) ?? null;
  }, [groupsById, selectedGroupSummary]);

  const currentUserId = auth.session?.user.id ?? usersQuery.data?.find((user) => user.is_current_user)?.id ?? "";

  const entryOptions = useMemo(() => {
    return (entryPickerQuery.data?.items ?? [])
      .filter((entry) => entry.direct_group === null)
      .map((entry) => ({
        id: entry.id,
        label: `${entry.occurred_at} · ${entry.name}`
      }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [entryPickerQuery.data]);

  const childGroupOptions = useMemo(() => {
    if (!selectedGroupSummary || selectedGroupSummary.parent_group_id) {
      return [];
    }
    return (groupsQuery.data ?? [])
      .filter((group) => group.id !== selectedGroupSummary.id)
      .filter((group) => group.parent_group_id === null)
      .filter((group) => group.direct_child_group_count === 0)
      .map((group) => ({
        id: group.id,
        label: `${group.name} · ${group.group_type}`
      }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [groupsQuery.data, selectedGroupSummary]);

  const groupsError = groupsQuery.isError ? (groupsQuery.error as Error).message : null;
  const selectedGroupError = groupGraphQuery.isError ? (groupGraphQuery.error as Error).message : null;
  const createGroupError = createGroupMutation.isError ? (createGroupMutation.error as Error).message : null;
  const renameGroupError = renameGroupMutation.isError ? (renameGroupMutation.error as Error).message : null;
  const addMemberError = addGroupMemberMutation.isError ? (addGroupMemberMutation.error as Error).message : null;
  const deleteGroupError = deleteGroupMutation.isError ? (deleteGroupMutation.error as Error).message : null;
  const deleteMemberError = deleteGroupMemberMutation.isError ? (deleteGroupMemberMutation.error as Error).message : null;
  const entryEditorLoadError = editingEntryQuery.isError ? (editingEntryQuery.error as Error).message : null;
  const entryEditorSaveError = updateEntryMutation.isError ? (updateEntryMutation.error as Error).message : null;

  function openGroupDetail(groupId: string) {
    setSelectedGroupId(groupId);
    setIsRenameGroupOpen(false);
    setIsAddMemberOpen(false);
    setIsDetailOpen(true);
  }

  function handleEntryEditorSubmit(payload: EntryEditorSubmitPayload) {
    if (!editingEntryId) {
      return;
    }
    updateEntryMutation.mutate({ entryId: editingEntryId, payload });
  }

  return (
    <div className="page stack-lg">
      <PageHeader
        title="Entry Groups"
        description="Group topology and member details."
      />

      <WorkspaceSection className="groups-browser-card">
        <WorkspaceToolbar className="filter-row">
            <div className="table-toolbar-filters">
              <label className="field min-w-[280px] grow">
                <span>Search groups</span>
                <Input value={groupSearch} onChange={(event) => setGroupSearch(event.target.value)} placeholder="Search by name or type" />
              </label>
            </div>
            <div className="table-toolbar-action filter-action">
              <Button type="button" size="icon" variant="outline" aria-label="Add group" onClick={() => setIsCreateGroupOpen(true)}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
        </WorkspaceToolbar>

        {groupsQuery.isLoading ? <p>Loading groups...</p> : null}
        {groupsError ? <p className="error">{groupsError}</p> : null}

        {!groupsQuery.isLoading && !groupsError && filteredGroups.length === 0 ? (
          <div className="groups-empty-state">
            <p className="groups-empty-title">No groups found</p>
            <p className="muted">Try another filter or create a new group.</p>
          </div>
        ) : null}

        {!groupsQuery.isLoading && !groupsError && filteredGroups.length > 0 ? (
          <div className="groups-browser-table-shell">
            <Table className="groups-browser-table">
              <TableHeader>
                <TableRow>
                  <TableHead className="groups-browser-group-column">Group</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Hierarchy</TableHead>
                  <TableHead>Descendants</TableHead>
                  <TableHead>Date range</TableHead>
                  <TableHead className="groups-browser-action-column">
                    <span className="sr-only">Open detail</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredGroups.map((group) => {
                  const isActive = isDetailOpen && group.id === selectedGroupId;
                  return (
                    <TableRow
                      key={group.id}
                      className={cn("groups-browser-row", isActive && "is-active")}
                      tabIndex={0}
                      onDoubleClick={() => openGroupDetail(group.id)}
                      onKeyDown={(event) => rowKeyDownHandler(event, () => openGroupDetail(group.id))}
                    >
                      <TableCell className="groups-browser-group-column">
                        <div className="groups-browser-group-cell">
                          <p className="groups-browser-group-name">{group.name}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{group.group_type}</Badge>
                      </TableCell>
                      <TableCell>{groupHierarchyLabel(group, groupsById)}</TableCell>
                      <TableCell>{group.descendant_entry_count} entries</TableCell>
                      <TableCell>{groupRangeLabel(group)}</TableCell>
                      <TableCell className="groups-browser-action-column">
                        <Button
                          type="button"
                          size="sm"
                          variant={isActive ? "secondary" : "ghost"}
                          onClick={(event) => {
                            event.stopPropagation();
                            openGroupDetail(group.id);
                          }}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </WorkspaceSection>

      <GroupDetailModal
        isOpen={isDetailOpen}
        groupSummary={selectedGroupSummary}
        parentGroupName={selectedParentGroup?.name ?? null}
        groupGraph={groupGraphQuery.data ?? null}
        isLoading={groupGraphQuery.isLoading}
        loadError={selectedGroupError}
        deleteGroupError={deleteGroupError}
        deleteMemberError={deleteMemberError}
        isDeletingGroup={deleteGroupMutation.isPending}
        isDeletingMember={deleteGroupMemberMutation.isPending}
        onClose={() => setIsDetailOpen(false)}
        onRename={() => setIsRenameGroupOpen(true)}
        onDelete={() => {
          if (selectedGroupSummary) {
            deleteGroupMutation.mutate(selectedGroupSummary.id);
          }
        }}
        onAddMember={() => setIsAddMemberOpen(true)}
        onOpenMember={(node) => {
          if (node.node_type === "GROUP") {
            openGroupDetail(node.subject_id);
            return;
          }
          setEditingEntryId(node.subject_id);
        }}
        onRemoveMember={(membershipId) => deleteGroupMemberMutation.mutate(membershipId)}
      />

      <GroupEditorModal
        isOpen={isCreateGroupOpen}
        mode="create"
        isSaving={createGroupMutation.isPending}
        saveError={createGroupError}
        onClose={() => setIsCreateGroupOpen(false)}
        onSubmit={(payload) => createGroupMutation.mutate(payload)}
      />

      <GroupEditorModal
        isOpen={isRenameGroupOpen}
        mode="rename"
        initialName={selectedGroupSummary?.name ?? ""}
        initialGroupType={selectedGroupSummary?.group_type ?? "BUNDLE"}
        isSaving={renameGroupMutation.isPending}
        saveError={renameGroupError}
        onClose={() => setIsRenameGroupOpen(false)}
        onSubmit={(payload) => renameGroupMutation.mutate({ name: payload.name })}
      />

      {selectedGroupSummary ? (
        <GroupMemberEditorModal
          isOpen={isAddMemberOpen}
          groupName={selectedGroupSummary.name}
          groupType={selectedGroupSummary.group_type}
          entryOptions={entryOptions}
          groupOptions={childGroupOptions}
          isSaving={addGroupMemberMutation.isPending}
          saveError={addMemberError}
          onClose={() => setIsAddMemberOpen(false)}
          onSubmit={(payload) => addGroupMemberMutation.mutate(payload)}
        />
      ) : null}

      <EntryEditorModal
        isOpen={Boolean(editingEntryId)}
        mode="edit"
        entry={editingEntryQuery.data ?? null}
        currencies={currenciesQuery.data ?? []}
        entities={entitiesQuery.data ?? []}
        groups={groupsQuery.data ?? []}
        tags={tagsQuery.data ?? []}
        currentUserId={currentUserId}
        defaultCurrencyCode={(runtimeSettingsQuery.data?.default_currency_code ?? "CAD").toUpperCase()}
        isSaving={updateEntryMutation.isPending}
        loadError={entryEditorLoadError}
        saveError={entryEditorSaveError}
        onClose={() => setEditingEntryId("")}
        onSubmit={handleEntryEditorSubmit}
      />
    </div>
  );
}
