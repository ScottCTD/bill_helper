import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { DeleteIconButton } from "../components/DeleteIconButton";
import { GroupEditorModal } from "../components/GroupEditorModal";
import { GroupGraphView } from "../components/GroupGraphView";
import { GroupMemberEditorModal } from "../components/GroupMemberEditorModal";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { addGroupMember, createGroup, deleteGroup, deleteGroupMember, getGroup, listEntries, listGroups, updateGroup } from "../lib/api";
import { invalidateGroupReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { GroupMemberRole, GroupNode, GroupSummary } from "../lib/types";

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

function nodeMetaLabel(node: GroupNode): string {
  if (node.node_type === "ENTRY") {
    return node.occurred_at ?? node.representative_occurred_at ?? "No date";
  }
  if (node.first_occurred_at && node.last_occurred_at) {
    if (node.first_occurred_at === node.last_occurred_at) {
      return node.first_occurred_at;
    }
    return `${node.first_occurred_at} to ${node.last_occurred_at}`;
  }
  return "No entries yet";
}

export function GroupsPage() {
  const queryClient = useQueryClient();
  const [groupSearch, setGroupSearch] = useState("");
  const deferredGroupSearch = useDeferredValue(groupSearch);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [isCreateGroupOpen, setIsCreateGroupOpen] = useState(false);
  const [isRenameGroupOpen, setIsRenameGroupOpen] = useState(false);
  const [isAddMemberOpen, setIsAddMemberOpen] = useState(false);

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
    enabled: Boolean(selectedGroupId)
  });

  useEffect(() => {
    if (!groupsQuery.data || groupsQuery.data.length === 0) {
      if (selectedGroupId) {
        setSelectedGroupId("");
      }
      return;
    }

    const selectionStillExists = groupsQuery.data.some((group) => group.id === selectedGroupId);
    if (!selectionStillExists) {
      setSelectedGroupId(groupsQuery.data[0].id);
    }
  }, [groupsQuery.data, selectedGroupId]);

  const createGroupMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: (group) => {
      invalidateGroupReadModels(queryClient);
      setSelectedGroupId(group.id);
      setIsCreateGroupOpen(false);
    }
  });

  const renameGroupMutation = useMutation({
    mutationFn: (payload: { name: string }) => updateGroup(selectedGroupId, payload),
    onSuccess: () => {
      invalidateGroupReadModels(queryClient, undefined, selectedGroupId);
      setIsRenameGroupOpen(false);
    }
  });

  const deleteGroupMutation = useMutation({
    mutationFn: (groupId: string) => deleteGroup(groupId),
    onSuccess: () => {
      invalidateGroupReadModels(queryClient);
      setSelectedGroupId("");
    }
  });

  const addGroupMemberMutation = useMutation({
    mutationFn: (payload: { entry_id?: string; child_group_id?: string; member_role?: GroupMemberRole }) =>
      addGroupMember(selectedGroupId, payload),
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

  const selectedGroupSummary = useMemo(
    () => groupsQuery.data?.find((group) => group.id === selectedGroupId) ?? null,
    [groupsQuery.data, selectedGroupId]
  );
  const totalGroupCount = groupsQuery.data?.length ?? 0;
  const topLevelGroupCount = useMemo(
    () => (groupsQuery.data ?? []).filter((group) => group.parent_group_id === null).length,
    [groupsQuery.data]
  );
  const childGroupCount = totalGroupCount - topLevelGroupCount;

  const selectedParentGroup = useMemo(() => {
    if (!selectedGroupSummary?.parent_group_id) {
      return null;
    }
    return groupsQuery.data?.find((group) => group.id === selectedGroupSummary.parent_group_id) ?? null;
  }, [groupsQuery.data, selectedGroupSummary]);

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

  const selectedGroupError = groupGraphQuery.isError ? (groupGraphQuery.error as Error).message : null;
  const groupsError = groupsQuery.isError ? (groupsQuery.error as Error).message : null;
  const createGroupError = createGroupMutation.isError ? (createGroupMutation.error as Error).message : null;
  const renameGroupError = renameGroupMutation.isError ? (renameGroupMutation.error as Error).message : null;
  const addMemberError = addGroupMemberMutation.isError ? (addGroupMemberMutation.error as Error).message : null;
  const deleteGroupError = deleteGroupMutation.isError ? (deleteGroupMutation.error as Error).message : null;
  const deleteMemberError = deleteGroupMemberMutation.isError ? (deleteGroupMemberMutation.error as Error).message : null;

  return (
    <div className="stack-lg">
      <Card className="groups-hero-card">
        <CardHeader className="groups-hero-header">
          <div>
            <CardTitle>Entry Groups</CardTitle>
            <CardDescription>
              Organize entries with one direct-group assignment, nested child groups where needed, and graph layouts derived from the selected group type.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="groups-hero-content">
          <div className="groups-hero-metrics">
            <div className="groups-metric-card">
              <span className="groups-metric-label">All groups</span>
              <strong className="groups-metric-value">{totalGroupCount}</strong>
              <span className="groups-metric-detail">{topLevelGroupCount} top level</span>
            </div>
            <div className="groups-metric-card">
              <span className="groups-metric-label">Child groups</span>
              <strong className="groups-metric-value">{childGroupCount}</strong>
              <span className="groups-metric-detail">Shared parents are blocked</span>
            </div>
            <div className="groups-metric-card">
              <span className="groups-metric-label">Eligible entries</span>
              <strong className="groups-metric-value">{entryOptions.length}</strong>
              <span className="groups-metric-detail">Ungrouped direct entries</span>
            </div>
          </div>
          <div className="groups-hero-actions">
            <Button type="button" size="sm" onClick={() => setIsCreateGroupOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New group
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="groups-layout">
        <Card className="groups-list-card">
          <CardHeader className="groups-sidebar-header">
            <div>
              <CardTitle>Browse Groups</CardTitle>
              <CardDescription>Search by name or type, then switch the detail panel.</CardDescription>
            </div>
            <Badge variant="outline">{filteredGroups.length} visible</Badge>
          </CardHeader>
          <CardContent className="groups-list-content">
            <label className="field min-w-0">
              <span>Search groups</span>
              <Input value={groupSearch} onChange={(event) => setGroupSearch(event.target.value)} placeholder="e.g. rent or bundle" />
            </label>

            {groupsQuery.isLoading ? <p>Loading groups...</p> : null}
            {groupsError ? <p className="error">{groupsError}</p> : null}

            {!groupsQuery.isLoading && !groupsError && filteredGroups.length === 0 ? (
              <p className="muted">No groups found for this filter.</p>
            ) : null}

            {filteredGroups.length > 0 ? (
              <div className="groups-list">
                {filteredGroups.map((group) => {
                  const isSelected = group.id === selectedGroupId;
                  return (
                    <button
                      key={group.id}
                      type="button"
                      className={isSelected ? "groups-list-item groups-list-item-selected" : "groups-list-item"}
                      onClick={() => setSelectedGroupId(group.id)}
                    >
                      <div className="groups-list-item-header">
                        <div className="min-w-0">
                          <p className="groups-list-item-name">{group.name}</p>
                          <p className="groups-summary-id">{group.id.slice(0, 8)}</p>
                        </div>
                        <Badge variant={isSelected ? "secondary" : "outline"}>{group.group_type}</Badge>
                      </div>
                      <p className="groups-list-item-range">{groupRangeLabel(group)}</p>
                      <div className="groups-list-item-stats">
                        <span>{group.direct_member_count} direct</span>
                        <span>{group.descendant_entry_count} entries</span>
                        <span>{group.parent_group_id ? "Child group" : "Top level"}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="stack-lg">
          <Card className="groups-detail-card">
            <CardHeader className="groups-detail-header">
              <div>
                <div className="groups-detail-title-row">
                  <CardTitle>{selectedGroupSummary ? selectedGroupSummary.name : "Select a Group"}</CardTitle>
                  {selectedGroupSummary ? <Badge variant="secondary">{selectedGroupSummary.group_type}</Badge> : null}
                  {selectedParentGroup ? <Badge variant="outline">Parent: {selectedParentGroup.name}</Badge> : null}
                </div>
                <CardDescription>
                  {selectedGroupSummary
                    ? "Review the current structure first, then edit direct members below."
                    : "Pick a group from the left to inspect and manage it."}
                </CardDescription>
              </div>
              {selectedGroupSummary ? (
                <div className="groups-detail-actions">
                  <Button type="button" size="sm" variant="outline" onClick={() => setIsRenameGroupOpen(true)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Rename
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => deleteGroupMutation.mutate(selectedGroupSummary.id)}
                    disabled={deleteGroupMutation.isPending}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              ) : null}
            </CardHeader>
            <CardContent className="groups-detail-content">
              {deleteGroupError ? <p className="error">{deleteGroupError}</p> : null}
              {!selectedGroupSummary ? (
                <div className="groups-empty-state">
                  <p className="groups-empty-title">No group selected</p>
                  <p className="muted">Use the left column to choose a group or create a new one.</p>
                </div>
              ) : (
                <div className="groups-overview-grid">
                  <div className="groups-overview-card">
                    <span className="groups-overview-label">Direct members</span>
                    <strong className="groups-overview-value">{selectedGroupSummary.direct_member_count}</strong>
                    <span className="groups-overview-detail">
                      {selectedGroupSummary.direct_entry_count} entries · {selectedGroupSummary.direct_child_group_count} child groups
                    </span>
                  </div>
                  <div className="groups-overview-card">
                    <span className="groups-overview-label">Descendant entries</span>
                    <strong className="groups-overview-value">{selectedGroupSummary.descendant_entry_count}</strong>
                    <span className="groups-overview-detail">Includes entries inside child groups</span>
                  </div>
                  <div className="groups-overview-card">
                    <span className="groups-overview-label">Date range</span>
                    <strong className="groups-overview-value">{groupRangeLabel(selectedGroupSummary)}</strong>
                    <span className="groups-overview-detail">
                      {selectedGroupSummary.parent_group_id ? "Nested in a parent group" : "Top-level group"}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="groups-subsection-header">
              <div>
                <CardTitle>Derived Graph</CardTitle>
                <CardDescription>Layout changes by group type. Edges are read-only and derived from direct membership.</CardDescription>
              </div>
              {selectedGroupSummary ? <Badge variant="outline">{selectedGroupSummary.group_type} layout</Badge> : null}
            </CardHeader>
            <CardContent>
              {!selectedGroupId ? <p className="muted">Select a group from the list.</p> : null}
              {selectedGroupId && groupGraphQuery.isLoading ? <p>Loading group graph...</p> : null}
              {selectedGroupId && selectedGroupError ? <p className="error">{selectedGroupError}</p> : null}
              {selectedGroupId && groupGraphQuery.data ? <GroupGraphView graph={groupGraphQuery.data} /> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="groups-subsection-header">
              <div>
                <CardTitle>Direct Members</CardTitle>
                <CardDescription>
                  Manage the top-level members of the selected group. Entry relationships are derived from this list and the group type.
                </CardDescription>
              </div>
              {selectedGroupSummary ? (
                <Button type="button" size="sm" variant="outline" onClick={() => setIsAddMemberOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add member
                </Button>
              ) : null}
            </CardHeader>
            <CardContent>
              {deleteMemberError ? <p className="error">{deleteMemberError}</p> : null}
              {!groupGraphQuery.data ? (
                <p className="muted">Select a group to manage its members.</p>
              ) : groupGraphQuery.data.nodes.length === 0 ? (
                <div className="groups-empty-state">
                  <p className="groups-empty-title">No direct members yet</p>
                  <p className="muted">Add entries or child groups to define this group's structure.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Member</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Context</TableHead>
                      <TableHead className="icon-action-column">
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {groupGraphQuery.data.nodes.map((node) => (
                      <TableRow key={node.membership_id}>
                        <TableCell>
                          <div className="space-y-1">
                            <p className="font-medium">{node.name}</p>
                            <p className="groups-summary-id">{node.subject_id.slice(0, 8)}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{node.node_type === "ENTRY" ? node.kind ?? "ENTRY" : `${node.group_type} GROUP`}</Badge>
                        </TableCell>
                        <TableCell>{node.member_role ? <Badge variant="secondary">{node.member_role}</Badge> : "-"}</TableCell>
                        <TableCell>{nodeMetaLabel(node)}</TableCell>
                        <TableCell className="icon-action-column">
                          <DeleteIconButton
                            label={`Remove member ${node.name}`}
                            disabled={deleteGroupMemberMutation.isPending}
                            onClick={() => deleteGroupMemberMutation.mutate(node.membership_id)}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

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
    </div>
  );
}
