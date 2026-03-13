/**
 * CALLING SPEC:
 * - Purpose: define group graph and summary contracts for the frontend.
 * - Inputs: frontend modules that render group graphs, summaries, and member relationships.
 * - Outputs: group-domain interfaces.
 * - Side effects: type declarations only.
 */

import type { EntryKind, GroupMemberRole, GroupType } from "./core";

export interface GroupNode {
  graph_id: string;
  membership_id: string;
  subject_id: string;
  node_type: "ENTRY" | "GROUP";
  name: string;
  member_role: GroupMemberRole | null;
  representative_occurred_at: string | null;
  kind: EntryKind | null;
  amount_minor: number | null;
  currency_code: string | null;
  occurred_at: string | null;
  group_type: GroupType | null;
  descendant_entry_count: number | null;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
}

export interface GroupEdge {
  id: string;
  source_graph_id: string;
  target_graph_id: string;
  group_type: GroupType;
}

export interface GroupGraph {
  id: string;
  name: string;
  group_type: GroupType;
  parent_group_id: string | null;
  direct_member_count: number;
  direct_entry_count: number;
  direct_child_group_count: number;
  descendant_entry_count: number;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
  nodes: GroupNode[];
  edges: GroupEdge[];
}

export interface GroupSummary {
  id: string;
  name: string;
  group_type: GroupType;
  parent_group_id: string | null;
  direct_member_count: number;
  direct_entry_count: number;
  direct_child_group_count: number;
  descendant_entry_count: number;
  first_occurred_at: string | null;
  last_occurred_at: string | null;
}
