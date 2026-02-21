import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { GroupGraphView } from "../components/GroupGraphView";
import { LinkEditorModal } from "../components/LinkEditorModal";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { createLink, deleteLink, getGroup, listEntries, listGroups } from "../lib/api";
import { formatMinor } from "../lib/format";
import { invalidateEntryLinkReadModels } from "../lib/queryInvalidation";
import { queryKeys } from "../lib/queryKeys";
import type { GroupEdge, GroupNode, GroupSummary } from "../lib/types";

const ENTRY_PICKER_FILTERS = {
  limit: 200,
  offset: 0
} as const;

function groupSummaryLabel(summary: GroupSummary): string {
  return summary.latest_entry_name || `Group ${summary.group_id.slice(0, 8)}`;
}

function groupRangeLabel(summary: GroupSummary): string {
  if (summary.first_occurred_at === summary.last_occurred_at) {
    return summary.first_occurred_at;
  }
  return `${summary.first_occurred_at} to ${summary.last_occurred_at}`;
}

function kindSymbol(kind: string): string {
  return kind === "INCOME" ? "+" : "-";
}

function nodeLabel(nodeId: string, nodeById: Map<string, GroupNode>): string {
  const node = nodeById.get(nodeId);
  if (!node) {
    return nodeId.slice(0, 8);
  }
  return `${node.name} (${node.id.slice(0, 8)})`;
}

export function GroupsPage() {
  const queryClient = useQueryClient();
  const [groupSearch, setGroupSearch] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [isLinkEditorOpen, setIsLinkEditorOpen] = useState(false);

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

    const selectionStillExists = groupsQuery.data.some((group) => group.group_id === selectedGroupId);
    if (!selectionStillExists) {
      setSelectedGroupId(groupsQuery.data[0].group_id);
    }
  }, [groupsQuery.data, selectedGroupId]);

  const createLinkMutation = useMutation({
    mutationFn: (payload: { source_entry_id: string; target_entry_id: string; link_type: string; note?: string }) =>
      createLink(payload.source_entry_id, {
        target_entry_id: payload.target_entry_id,
        link_type: payload.link_type,
        note: payload.note
      }),
    onSuccess: () => {
      invalidateEntryLinkReadModels(queryClient);
      setIsLinkEditorOpen(false);
    }
  });

  const deleteLinkMutation = useMutation({
    mutationFn: deleteLink,
    onSuccess: () => {
      invalidateEntryLinkReadModels(queryClient);
    }
  });

  const filteredGroups = useMemo(() => {
    const normalizedSearch = groupSearch.trim().toLowerCase();
    if (!normalizedSearch) {
      return groupsQuery.data ?? [];
    }
    return (groupsQuery.data ?? []).filter((group) => {
      return (
        group.latest_entry_name.toLowerCase().includes(normalizedSearch) ||
        group.group_id.toLowerCase().includes(normalizedSearch)
      );
    });
  }, [groupSearch, groupsQuery.data]);

  const selectedGroupSummary = useMemo(
    () => groupsQuery.data?.find((group) => group.group_id === selectedGroupId) ?? null,
    [groupsQuery.data, selectedGroupId]
  );

  const selectedGroupNodeById = useMemo(() => {
    return new Map((groupGraphQuery.data?.nodes ?? []).map((node) => [node.id, node] as const));
  }, [groupGraphQuery.data]);

  const sortedGroupNodes = useMemo(() => {
    return [...(groupGraphQuery.data?.nodes ?? [])].sort((left, right) => left.occurred_at.localeCompare(right.occurred_at));
  }, [groupGraphQuery.data]);

  const sortedGroupEdges = useMemo(() => {
    return [...(groupGraphQuery.data?.edges ?? [])].sort((left, right) => left.id.localeCompare(right.id));
  }, [groupGraphQuery.data]);

  const entryPickerOptions = useMemo(() => {
    return (entryPickerQuery.data?.items ?? [])
      .map((entry) => ({
        id: entry.id,
        label: `${entry.occurred_at} - ${entry.name} (${entry.id.slice(0, 8)})`
      }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [entryPickerQuery.data]);

  const currencyByEntryId = useMemo(() => {
    return new Map((entryPickerQuery.data?.items ?? []).map((entry) => [entry.id, entry.currency_code] as const));
  }, [entryPickerQuery.data]);

  const selectedGroupError = groupGraphQuery.isError ? (groupGraphQuery.error as Error).message : null;
  const groupsError = groupsQuery.isError ? (groupsQuery.error as Error).message : null;
  const entryPickerError = entryPickerQuery.isError ? (entryPickerQuery.error as Error).message : null;
  const entryPickerIsPartial = (entryPickerQuery.data?.total ?? 0) > (entryPickerQuery.data?.items.length ?? 0);
  const linkDeleteError = deleteLinkMutation.isError ? (deleteLinkMutation.error as Error).message : null;

  return (
    <div className="stack-lg">
      <Card>
        <CardHeader>
          <CardTitle>Entry Groups</CardTitle>
          <CardDescription>
            Groups are derived graph components. Link operations reshape groups; entries are never deleted by group edits.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="groups-layout">
        <Card className="groups-list-card">
          <CardHeader>
            <CardTitle>Groups</CardTitle>
            <CardDescription>
              Derived from active entry links. Search by latest entry name or group id.
            </CardDescription>
          </CardHeader>
          <CardContent className="groups-list-content">
            <label className="field min-w-0">
              <span>Search groups</span>
              <Input value={groupSearch} onChange={(event) => setGroupSearch(event.target.value)} placeholder="e.g. rent or 6c3a..." />
            </label>

            {groupsQuery.isLoading ? <p>Loading groups...</p> : null}
            {groupsError ? <p className="error">{groupsError}</p> : null}

            {!groupsQuery.isLoading && !groupsError && filteredGroups.length === 0 ? (
              <p className="muted">No groups found for this filter.</p>
            ) : null}

            {filteredGroups.length > 0 ? (
              <Table className="groups-summary-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Group</TableHead>
                    <TableHead>Entries</TableHead>
                    <TableHead>Links</TableHead>
                    <TableHead>Date Range</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredGroups.map((group) => (
                    <TableRow
                      key={group.group_id}
                      className={group.group_id === selectedGroupId ? "groups-summary-row-selected" : "groups-summary-row"}
                      onClick={() => setSelectedGroupId(group.group_id)}
                    >
                      <TableCell>
                        <div className="space-y-1">
                          <p className="font-medium">{groupSummaryLabel(group)}</p>
                          <p className="groups-summary-id">{group.group_id.slice(0, 8)}</p>
                        </div>
                      </TableCell>
                      <TableCell className="tabular-nums">{group.entry_count}</TableCell>
                      <TableCell className="tabular-nums">{group.edge_count}</TableCell>
                      <TableCell>{groupRangeLabel(group)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </CardContent>
        </Card>

        <div className="stack-lg">
          <Card>
            <CardHeader>
              <CardTitle>{selectedGroupSummary ? groupSummaryLabel(selectedGroupSummary) : "Group Graph"}</CardTitle>
              <CardDescription>
                {selectedGroupSummary
                  ? `${selectedGroupSummary.entry_count} entries, ${selectedGroupSummary.edge_count} links, ${groupRangeLabel(selectedGroupSummary)}`
                  : "Select a group to inspect topology."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedGroupId ? <p className="muted">Select a group from the list.</p> : null}
              {selectedGroupId && groupGraphQuery.isLoading ? <p>Loading group graph...</p> : null}
              {selectedGroupId && selectedGroupError ? <p className="error">{selectedGroupError}</p> : null}
              {selectedGroupId && groupGraphQuery.data ? <GroupGraphView graph={groupGraphQuery.data} /> : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="section-header">
              <div>
                <CardTitle>Link Operations</CardTitle>
                <CardDescription>Create or remove links to merge, split, or reshape derived groups.</CardDescription>
              </div>
              <Button
                type="button"
                size="icon"
                variant="outline"
                aria-label="Add link"
                onClick={() => {
                  createLinkMutation.reset();
                  setIsLinkEditorOpen(true);
                }}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-5">
              {linkDeleteError ? <p className="error">{linkDeleteError}</p> : null}

              {groupGraphQuery.data ? (
                <div className="table-shell">
                  {sortedGroupEdges.length === 0 ? (
                    <p className="muted">No links in this group.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Source</TableHead>
                          <TableHead>Target</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Note</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sortedGroupEdges.map((edge: GroupEdge) => (
                          <TableRow key={edge.id}>
                            <TableCell>{nodeLabel(edge.source_entry_id, selectedGroupNodeById)}</TableCell>
                            <TableCell>{nodeLabel(edge.target_entry_id, selectedGroupNodeById)}</TableCell>
                            <TableCell>{edge.link_type}</TableCell>
                            <TableCell>{edge.note || "-"}</TableCell>
                            <TableCell>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={deleteLinkMutation.isPending}
                                onClick={() => deleteLinkMutation.mutate(edge.id)}
                              >
                                Remove
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              ) : (
                <p className="muted">Select a group to manage links.</p>
              )}
            </CardContent>
          </Card>

          {groupGraphQuery.data ? (
            <Card>
              <CardHeader>
                <CardTitle>Entries in Group</CardTitle>
                <CardDescription>Members currently connected by the selected graph component.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Kind</TableHead>
                      <TableHead>Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedGroupNodes.map((node) => {
                      const currencyCode = currencyByEntryId.get(node.id);
                      const amountText = currencyCode ? formatMinor(node.amount_minor, currencyCode) : `${node.amount_minor} minor units`;
                      return (
                        <TableRow key={node.id}>
                          <TableCell>{node.occurred_at}</TableCell>
                          <TableCell>
                            <div className="space-y-1">
                              <p className="font-medium">{node.name}</p>
                              <p className="groups-summary-id">{node.id.slice(0, 8)}</p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={node.kind === "INCOME" ? "kind-indicator kind-indicator-income" : "kind-indicator kind-indicator-expense"}
                            >
                              {kindSymbol(node.kind)}
                            </Badge>
                          </TableCell>
                          <TableCell>{amountText}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>

      <LinkEditorModal
        isOpen={isLinkEditorOpen}
        title="Create Link"
        description="Add a directional relation between two entries. Group membership updates automatically."
        entryOptions={entryPickerOptions}
        entryOptionsLoading={entryPickerQuery.isLoading}
        entryOptionsError={entryPickerError}
        entryOptionsNotice={entryPickerIsPartial ? "Entry picker is limited to the first 200 entries." : null}
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
