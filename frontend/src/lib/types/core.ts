/**
 * CALLING SPEC:
 * - Purpose: define shared finance and grouping primitive types for frontend domain modules.
 * - Inputs: frontend modules that import shared enum-style unions and payload primitives.
 * - Outputs: core type aliases and group member payload contracts.
 * - Side effects: type declarations only.
 */

export type EntryKind = "EXPENSE" | "INCOME" | "TRANSFER";
export type GroupType = "BUNDLE" | "SPLIT" | "RECURRING";
export type GroupMemberRole = "PARENT" | "CHILD";
export type GroupMemberTarget =
  | { target_type: "entry"; entry_id: string }
  | { target_type: "child_group"; group_id: string };

export interface GroupMemberCreatePayload {
  target: GroupMemberTarget;
  member_role?: GroupMemberRole;
}
