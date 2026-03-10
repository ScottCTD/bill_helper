import type { AgentChangeItem, GroupMemberRole } from "../../../../lib/types";

import { asRecord, asString, normalizeReferenceId, recordsEqual } from "./common";
import type { GroupMembershipReviewDraft, JsonRecord, ReviewOverrideState } from "./types";

interface GroupMembershipRecord {
  action: "add";
  group_ref: JsonRecord;
  entry_ref: JsonRecord | null;
  child_group_ref: JsonRecord | null;
  member_role: GroupMemberRole | null;
}

function normalizeGroupMembershipRecord(record: GroupMembershipRecord): GroupMembershipRecord {
  const normalizedGroupRef = asRecord(record.group_ref);
  const normalizedEntryRef = record.entry_ref ? asRecord(record.entry_ref) : null;
  const normalizedChildGroupRef = record.child_group_ref ? asRecord(record.child_group_ref) : null;
  return {
    action: "add",
    group_ref: normalizedGroupRef,
    entry_ref: normalizedEntryRef,
    child_group_ref: normalizedChildGroupRef,
    member_role: record.member_role ?? null
  };
}

function buildCreateGroupMembershipRecord(payload: JsonRecord): GroupMembershipRecord {
  return normalizeGroupMembershipRecord({
    action: "add",
    group_ref: asRecord(payload.group_ref),
    entry_ref: payload.entry_ref ? asRecord(payload.entry_ref) : null,
    child_group_ref: payload.child_group_ref ? asRecord(payload.child_group_ref) : null,
    member_role: (payload.member_role === "PARENT" || payload.member_role === "CHILD" ? payload.member_role : null) as
      | GroupMemberRole
      | null
  });
}

export function buildGroupMembershipReviewDraft(item: AgentChangeItem): GroupMembershipReviewDraft {
  const record = buildCreateGroupMembershipRecord(item.payload_json);
  return {
    groupId: typeof record.group_ref.group_id === "string" ? record.group_ref.group_id : "",
    entryId: record.entry_ref && typeof record.entry_ref.entry_id === "string" ? record.entry_ref.entry_id : "",
    childGroupId: record.child_group_ref && typeof record.child_group_ref.group_id === "string" ? record.child_group_ref.group_id : "",
    memberRole: record.member_role ?? ""
  };
}

export function buildGroupMembershipOverrideState(
  item: AgentChangeItem,
  draft: GroupMembershipReviewDraft
): ReviewOverrideState {
  const payload = item.payload_json;
  const baseRecord = buildCreateGroupMembershipRecord(payload);
  const groupRef = { ...baseRecord.group_ref };
  const entryRef = baseRecord.entry_ref ? { ...baseRecord.entry_ref } : null;
  const childGroupRef = baseRecord.child_group_ref ? { ...baseRecord.child_group_ref } : null;

  if (groupRef.create_group_proposal_id == null) {
    const nextGroupId = normalizeReferenceId(draft.groupId);
    if (!nextGroupId) {
      return { hasChanges: false, validationError: "Group ID is required." };
    }
    groupRef.group_id = nextGroupId;
  }

  if (entryRef) {
    if (entryRef.create_entry_proposal_id == null) {
      const nextEntryId = normalizeReferenceId(draft.entryId);
      if (!nextEntryId) {
        return { hasChanges: false, validationError: "Entry ID is required." };
      }
      entryRef.entry_id = nextEntryId;
    }
  } else if (childGroupRef) {
    if (childGroupRef.create_group_proposal_id == null) {
      const nextChildGroupId = normalizeReferenceId(draft.childGroupId);
      if (!nextChildGroupId) {
        return { hasChanges: false, validationError: "Child group ID is required." };
      }
      childGroupRef.group_id = nextChildGroupId;
    }
  }

  const groupType = asString(asRecord(payload.group_preview).group_type);
  const normalizedRole = draft.memberRole || "";
  if (groupType === "SPLIT") {
    if (normalizedRole !== "PARENT" && normalizedRole !== "CHILD") {
      return { hasChanges: false, validationError: "Split role is required." };
    }
  }

  const normalizedRecord = normalizeGroupMembershipRecord({
    action: "add",
    group_ref: groupRef,
    entry_ref: entryRef,
    child_group_ref: childGroupRef,
    member_role: normalizedRole === "PARENT" || normalizedRole === "CHILD" ? normalizedRole : null
  });
  const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
  return {
    hasChanges,
    payloadOverride: hasChanges
      ? {
          action: "add",
          group_ref: normalizedRecord.group_ref,
          entry_ref: normalizedRecord.entry_ref,
          child_group_ref: normalizedRecord.child_group_ref,
          member_role: normalizedRecord.member_role
        }
      : undefined,
    validationError: null
  };
}
