import type { AgentChangeItem, GroupMemberRole } from "../../../../lib/types";

import { asRecord, asString, normalizeReferenceId, recordsEqual } from "./common";
import type { GroupMembershipReviewDraft, JsonRecord, ReviewOverrideState } from "./types";

interface GroupMembershipRecord {
  action: "add";
  group_ref: JsonRecord;
  target: JsonRecord;
  member_role: GroupMemberRole | null;
}

function normalizeGroupMembershipTarget(target: JsonRecord): JsonRecord {
  const normalizedTarget = asRecord(target);
  if (normalizedTarget.target_type === "child_group") {
    return {
      target_type: "child_group",
      group_ref: asRecord(normalizedTarget.group_ref)
    };
  }
  return {
    target_type: "entry",
    entry_ref: asRecord(normalizedTarget.entry_ref)
  };
}

function normalizeGroupMembershipRecord(record: GroupMembershipRecord): GroupMembershipRecord {
  return {
    action: "add",
    group_ref: asRecord(record.group_ref),
    target: normalizeGroupMembershipTarget(record.target),
    member_role: record.member_role ?? null
  };
}

function buildCreateGroupMembershipRecord(payload: JsonRecord): GroupMembershipRecord {
  return normalizeGroupMembershipRecord({
    action: "add",
    group_ref: asRecord(payload.group_ref),
    target: asRecord(payload.target),
    member_role: (payload.member_role === "PARENT" || payload.member_role === "CHILD" ? payload.member_role : null) as
      | GroupMemberRole
      | null
  });
}

export function buildGroupMembershipReviewDraft(item: AgentChangeItem): GroupMembershipReviewDraft {
  const record = buildCreateGroupMembershipRecord(item.payload_json);
  const target = normalizeGroupMembershipTarget(record.target);
  const isEntryTarget = target.target_type === "entry";
  const entryRef = isEntryTarget ? asRecord(target.entry_ref) : null;
  const childGroupRef = isEntryTarget ? null : asRecord(target.group_ref);
  return {
    groupId: typeof record.group_ref.group_id === "string" ? record.group_ref.group_id : "",
    entryId: entryRef && typeof entryRef.entry_id === "string" ? entryRef.entry_id : "",
    childGroupId: childGroupRef && typeof childGroupRef.group_id === "string" ? childGroupRef.group_id : "",
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
  const target = normalizeGroupMembershipTarget(baseRecord.target);
  const targetRecord = { ...target };

  if (groupRef.create_group_proposal_id == null) {
    const nextGroupId = normalizeReferenceId(draft.groupId);
    if (!nextGroupId) {
      return { hasChanges: false, validationError: "Group ID is required." };
    }
    groupRef.group_id = nextGroupId;
  }

  if (target.target_type === "entry") {
    const entryRef = { ...asRecord(target.entry_ref) };
    if (entryRef.create_entry_proposal_id == null) {
      const nextEntryId = normalizeReferenceId(draft.entryId);
      if (!nextEntryId) {
        return { hasChanges: false, validationError: "Entry ID is required." };
      }
      entryRef.entry_id = nextEntryId;
    }
    targetRecord.entry_ref = entryRef;
  } else {
    const childGroupRef = { ...asRecord(target.group_ref) };
    if (childGroupRef.create_group_proposal_id == null) {
      const nextChildGroupId = normalizeReferenceId(draft.childGroupId);
      if (!nextChildGroupId) {
        return { hasChanges: false, validationError: "Child group ID is required." };
      }
      childGroupRef.group_id = nextChildGroupId;
    }
    targetRecord.group_ref = childGroupRef;
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
    target: targetRecord,
    member_role: normalizedRole === "PARENT" || normalizedRole === "CHILD" ? normalizedRole : null
  });
  const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
  return {
    hasChanges,
    payloadOverride: hasChanges
      ? {
          action: "add",
          group_ref: normalizedRecord.group_ref,
          target: normalizedRecord.target,
          member_role: normalizedRecord.member_role
        }
      : undefined,
    validationError: null
  };
}
