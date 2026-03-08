import { Pencil, Plus, Trash2 } from "lucide-react";

import { DeleteIconButton } from "./DeleteIconButton";
import { GroupGraphView } from "./GroupGraphView";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { formatMinor } from "../lib/format";
import type { GroupGraph, GroupNode, GroupSummary } from "../lib/types";

interface GroupDetailModalProps {
  isOpen: boolean;
  groupSummary: GroupSummary | null;
  parentGroupName: string | null;
  groupGraph: GroupGraph | null;
  isLoading: boolean;
  loadError?: string | null;
  deleteGroupError?: string | null;
  deleteMemberError?: string | null;
  isDeletingGroup: boolean;
  isDeletingMember: boolean;
  onClose: () => void;
  onRename: () => void;
  onDelete: () => void;
  onAddMember: () => void;
  onRemoveMember: (membershipId: string) => void;
}

function groupRangeLabel(summary: GroupSummary): string {
  if (!summary.first_occurred_at || !summary.last_occurred_at) {
    return "No entries yet";
  }
  if (summary.first_occurred_at === summary.last_occurred_at) {
    return summary.first_occurred_at;
  }
  return `${summary.first_occurred_at} to ${summary.last_occurred_at}`;
}

function memberContextLabel(node: GroupNode): string {
  if (node.node_type === "ENTRY") {
    const tone = node.kind === "INCOME" ? "Income" : node.kind === "TRANSFER" ? "Transfer" : "Expense";
    return `${node.occurred_at ?? node.representative_occurred_at ?? "No date"} · ${tone}`;
  }

  if (node.first_occurred_at && node.last_occurred_at) {
    if (node.first_occurred_at === node.last_occurred_at) {
      return `${node.group_type ?? "GROUP"} · ${node.first_occurred_at}`;
    }
    return `${node.group_type ?? "GROUP"} · ${node.first_occurred_at} to ${node.last_occurred_at}`;
  }

  return `${node.group_type ?? "GROUP"} · No entries yet`;
}

function memberTypeLabel(node: GroupNode): string {
  if (node.node_type === "GROUP") {
    return `${node.group_type ?? "GROUP"} GROUP`;
  }
  return node.kind ?? "ENTRY";
}

function groupDetailMeta(summary: GroupSummary): string {
  const directMemberLabel = summary.direct_member_count === 1 ? "1 direct member" : `${summary.direct_member_count} direct members`;
  const descendantLabel = summary.descendant_entry_count === 1 ? "1 descendant entry" : `${summary.descendant_entry_count} descendant entries`;
  return `${directMemberLabel} · ${descendantLabel} · ${groupRangeLabel(summary)}`;
}

interface GroupStat {
  label: string;
  value: string;
  detail: string;
}

function isEntryNode(node: GroupNode): node is GroupNode & { node_type: "ENTRY"; amount_minor: number; currency_code: string } {
  return node.node_type === "ENTRY" && node.amount_minor !== null && typeof node.currency_code === "string" && node.currency_code.length > 0;
}

function hasNodeKind(node: GroupNode): node is GroupNode & { kind: NonNullable<GroupNode["kind"]> } {
  return node.kind !== null;
}

function amountStatLabel(nodes: GroupNode[], variant: "total" | "average"): string {
  const kinds = Array.from(new Set(nodes.filter(hasNodeKind).map((node) => node.kind)));
  if (kinds.length !== 1) {
    return variant === "total" ? "Direct total" : "Average amount";
  }

  if (kinds[0] === "EXPENSE") {
    return variant === "total" ? "Total cost" : "Average cost";
  }
  if (kinds[0] === "INCOME") {
    return variant === "total" ? "Total income" : "Average income";
  }
  return variant === "total" ? "Total moved" : "Average transfer";
}

function formatCurrencyBucketSummary(buckets: Map<string, number>): { value: string; detail: string } {
  if (buckets.size === 0) {
    return { value: "-", detail: "No direct entry amounts yet" };
  }

  const formatted = Array.from(buckets.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currencyCode, amountMinor]) => formatMinor(amountMinor, currencyCode));
  if (formatted.length === 1) {
    return { value: formatted[0], detail: "Direct entry members only" };
  }
  return { value: "Mixed currencies", detail: formatted.join(" · ") };
}

function buildGroupStats(summary: GroupSummary, graph: GroupGraph | null): GroupStat[] {
  const entryNodes = (graph?.nodes ?? []).filter(isEntryNode);
  const totalBuckets = new Map<string, number>();
  const averageBuckets = new Map<string, number>();

  for (const node of entryNodes) {
    totalBuckets.set(node.currency_code, (totalBuckets.get(node.currency_code) ?? 0) + node.amount_minor);
  }

  for (const [currencyCode, totalMinor] of totalBuckets.entries()) {
    const count = entryNodes.filter((node) => node.currency_code === currencyCode).length;
    averageBuckets.set(currencyCode, Math.round(totalMinor / count));
  }

  const totalSummary = formatCurrencyBucketSummary(totalBuckets);
  const averageSummary = formatCurrencyBucketSummary(averageBuckets);

  const latestEntry = [...entryNodes].sort((left, right) => {
    const leftDate = left.occurred_at ?? left.representative_occurred_at ?? "";
    const rightDate = right.occurred_at ?? right.representative_occurred_at ?? "";
    return rightDate.localeCompare(leftDate);
  })[0];

  const coverageValue = summary.first_occurred_at && summary.last_occurred_at ? groupRangeLabel(summary) : "No range yet";
  const coverageDetail = summary.first_occurred_at && summary.last_occurred_at
    ? summary.first_occurred_at === summary.last_occurred_at
      ? "Single recorded date"
      : `${summary.parent_group_id ? "Nested child group" : "Top-level group"} coverage`
    : "Add dated entries to establish a range";

  return [
    {
      label: amountStatLabel(entryNodes, "total"),
      value: totalSummary.value,
      detail: totalSummary.detail,
    },
    {
      label: amountStatLabel(entryNodes, "average"),
      value: averageSummary.value,
      detail: averageSummary.detail,
    },
    {
      label: "Latest amount",
      value: latestEntry ? formatMinor(latestEntry.amount_minor, latestEntry.currency_code) : "-",
      detail: latestEntry ? `${latestEntry.occurred_at ?? latestEntry.representative_occurred_at ?? "No date"} · ${latestEntry.name}` : "No direct entry amounts yet",
    },
    {
      label: "Coverage",
      value: coverageValue,
      detail: coverageDetail,
    },
  ];
}

export function GroupDetailModal({
  isOpen,
  groupSummary,
  parentGroupName,
  groupGraph,
  isLoading,
  loadError = null,
  deleteGroupError = null,
  deleteMemberError = null,
  isDeletingGroup,
  isDeletingMember,
  onClose,
  onRename,
  onDelete,
  onAddMember,
  onRemoveMember
}: GroupDetailModalProps) {
  const stats = groupSummary ? buildGroupStats(groupSummary, groupGraph) : [];

  return (
    <Dialog open={isOpen} onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="groups-detail-modal">
        <div className="groups-detail-modal-shell">
          <DialogHeader className="groups-detail-modal-header">
            <div className="groups-detail-modal-header-copy">
              <div className="groups-detail-modal-title-row">
                <DialogTitle>{groupSummary ? groupSummary.name : "Group detail"}</DialogTitle>
                {groupSummary ? <Badge variant="secondary">{groupSummary.group_type}</Badge> : null}
                {parentGroupName ? <Badge variant="outline">Parent: {parentGroupName}</Badge> : null}
              </div>
              <DialogDescription>
                {groupSummary
                  ? "Inspect the derived graph, then manage direct membership without squeezing the workspace."
                  : "Open a group from the table to inspect its detail."}
              </DialogDescription>
            </div>
            {groupSummary ? (
              <div className="groups-detail-modal-actions">
                <Button type="button" size="sm" variant="outline" onClick={onRename}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Rename
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={onAddMember}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add member
                </Button>
                <Button type="button" size="sm" variant="destructive" onClick={onDelete} disabled={isDeletingGroup}>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </div>
            ) : null}
          </DialogHeader>

          <div className="groups-detail-modal-body">
            {deleteGroupError ? <p className="error">{deleteGroupError}</p> : null}

            {!groupSummary ? (
              <div className="groups-empty-state">
                <p className="groups-empty-title">No group selected</p>
                <p className="muted">Choose a group from the table first.</p>
              </div>
            ) : (
              <>
                <p className="groups-detail-meta">
                  {groupDetailMeta(groupSummary)}
                  {groupSummary.direct_member_count > 0 ? (
                    <span className="groups-detail-meta-secondary">
                      {` · ${groupSummary.direct_entry_count} entries · ${groupSummary.direct_child_group_count} child groups`}
                    </span>
                  ) : null}
                </p>

                <section className="groups-detail-section">
                  <div className="groups-detail-section-header">
                    <div>
                      <h3>Statistics</h3>
                      <p>Amounts are calculated from direct entry members only. Child-group totals are not rolled up in this view.</p>
                    </div>
                  </div>
                  <div className="groups-detail-section-body">
                    <div className="groups-detail-stats-grid">
                      {stats.map((stat) => (
                        <div key={stat.label} className="groups-detail-stat-card">
                          <span className="groups-detail-stat-label">{stat.label}</span>
                          <strong className="groups-detail-stat-value">{stat.value}</strong>
                          <span className="groups-detail-stat-detail">{stat.detail}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="groups-detail-section">
                  <div className="groups-detail-section-header">
                    <div>
                      <h3>Direct members</h3>
                      <p>Manage the top-level members that define this group’s derived structure.</p>
                    </div>
                  </div>
                  <div className="groups-detail-section-body">
                    {deleteMemberError ? <p className="error">{deleteMemberError}</p> : null}
                    {!groupGraph ? (
                      <p className="muted">Group detail is not loaded yet.</p>
                    ) : groupGraph.nodes.length === 0 ? (
                      <div className="groups-empty-state">
                        <p className="groups-empty-title">No direct members yet</p>
                        <p className="muted">Add entries or child groups to define the group structure.</p>
                      </div>
                    ) : (
                      <div className="groups-detail-members-table-shell">
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
                            {groupGraph.nodes.map((node) => (
                              <TableRow key={node.membership_id}>
                                <TableCell>
                                  <div className="space-y-1">
                                    <p className="font-medium">{node.name}</p>
                                    <p className="groups-summary-id">{node.subject_id.slice(0, 8)}</p>
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="outline">{memberTypeLabel(node)}</Badge>
                                </TableCell>
                                <TableCell>{node.member_role ? <Badge variant="secondary">{node.member_role}</Badge> : "-"}</TableCell>
                                <TableCell>{memberContextLabel(node)}</TableCell>
                                <TableCell className="icon-action-column">
                                  <DeleteIconButton
                                    label={`Remove member ${node.name}`}
                                    disabled={isDeletingMember}
                                    onClick={() => onRemoveMember(node.membership_id)}
                                  />
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                </section>

                <section className="groups-detail-section">
                  <div className="groups-detail-section-header">
                    <div>
                      <h3>Derived graph</h3>
                      <p>Graph edges are read-only and derived from the current direct membership plus group type.</p>
                    </div>
                    <Badge variant="outline">{groupSummary.group_type} layout</Badge>
                  </div>
                  <div className="groups-detail-section-body">
                    {isLoading ? <p>Loading group graph...</p> : null}
                    {loadError ? <p className="error">{loadError}</p> : null}
                    {!isLoading && !loadError && groupGraph ? <GroupGraphView graph={groupGraph} /> : null}
                  </div>
                </section>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
