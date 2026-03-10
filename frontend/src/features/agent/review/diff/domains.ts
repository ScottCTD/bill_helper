import type { DiffMetadata, JsonRecord, ProposalDiff } from "./types";
import { asRecord, buildRecordUpdateDiff, jsonRecordsAreEquivalent } from "./core";

export function previewName(preview: JsonRecord, fallback: string): string {
  const name = preview.name;
  return typeof name === "string" && name.trim() ? name : fallback;
}

export function buildGroupRecord(payload: JsonRecord): JsonRecord {
  return {
    name: typeof payload.name === "string" ? payload.name : "",
    group_type: typeof payload.group_type === "string" ? payload.group_type : "BUNDLE"
  };
}

export function buildAccountRecord(payload: JsonRecord): JsonRecord {
  return {
    name: typeof payload.name === "string" ? payload.name : "",
    currency_code: typeof payload.currency_code === "string" ? payload.currency_code : "",
    is_active: typeof payload.is_active === "boolean" ? payload.is_active : true,
    markdown_body:
      typeof payload.markdown_body === "string" || payload.markdown_body === null ? payload.markdown_body : null
  };
}

export function buildUpdateAccountBeforeRecord(payload: JsonRecord): JsonRecord {
  const current = asRecord(payload.current);
  return buildAccountRecord({
    name: typeof current.name === "string" ? current.name : payload.name,
    currency_code: current.currency_code,
    is_active: current.is_active,
    markdown_body: Object.prototype.hasOwnProperty.call(current, "markdown_body") ? current.markdown_body : null
  });
}

export function buildUpdateAccountAfterRecord(
  payload: JsonRecord,
  reviewerOverride?: JsonRecord
): { before: JsonRecord; after: JsonRecord; reviewerEdited: boolean } {
  const before = buildUpdateAccountBeforeRecord(payload);
  const reviewerEdited = Boolean(reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride));
  const effectivePatch = reviewerEdited ? asRecord(reviewerOverride?.patch) : asRecord(payload.patch);
  return {
    before,
    after: buildAccountRecord({
      ...before,
      ...(typeof effectivePatch.name === "string" ? { name: effectivePatch.name } : {}),
      ...(typeof effectivePatch.currency_code === "string" ? { currency_code: effectivePatch.currency_code } : {}),
      ...(typeof effectivePatch.is_active === "boolean" ? { is_active: effectivePatch.is_active } : {}),
      ...(Object.prototype.hasOwnProperty.call(effectivePatch, "markdown_body")
        ? { markdown_body: effectivePatch.markdown_body }
        : {})
    }),
    reviewerEdited
  };
}

export function buildUpdateGroupBeforeRecord(payload: JsonRecord): JsonRecord {
  const current = asRecord(payload.current);
  const target = asRecord(payload.target);
  return {
    name: typeof current.name === "string" ? current.name : typeof target.name === "string" ? target.name : "",
    group_type:
      typeof current.group_type === "string"
        ? current.group_type
        : typeof target.group_type === "string"
          ? target.group_type
          : "BUNDLE"
  };
}

export function buildUpdateGroupAfterRecord(
  payload: JsonRecord,
  reviewerOverride?: JsonRecord
): { before: JsonRecord; after: JsonRecord; reviewerEdited: boolean } {
  const before = buildUpdateGroupBeforeRecord(payload);
  const reviewerEdited = Boolean(reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride));
  const effectivePatch = reviewerEdited ? asRecord(reviewerOverride?.patch) : asRecord(payload.patch);
  return {
    before,
    after: {
      ...before,
      ...(typeof effectivePatch.name === "string" ? { name: effectivePatch.name } : {})
    },
    reviewerEdited
  };
}

function buildEntryRecordFromMemberPreview(memberPreview: JsonRecord): JsonRecord {
  const record: JsonRecord = {};
  if (typeof memberPreview.date === "string" && memberPreview.date.trim()) {
    record.date = memberPreview.date;
  }
  if (typeof memberPreview.name === "string" && memberPreview.name.trim()) {
    record.name = memberPreview.name;
  }
  if (typeof memberPreview.kind === "string" && memberPreview.kind.trim()) {
    record.kind = memberPreview.kind;
  }
  if (typeof memberPreview.amount_minor === "number") {
    record.amount_minor = memberPreview.amount_minor;
  }
  if (typeof memberPreview.currency_code === "string" && memberPreview.currency_code.trim()) {
    record.currency_code = memberPreview.currency_code;
  }
  if (typeof memberPreview.from_entity === "string" && memberPreview.from_entity.trim()) {
    record.from_entity = memberPreview.from_entity;
  }
  if (typeof memberPreview.to_entity === "string" && memberPreview.to_entity.trim()) {
    record.to_entity = memberPreview.to_entity;
  }
  if (Array.isArray(memberPreview.tags)) {
    record.tags = memberPreview.tags;
  }
  if (typeof memberPreview.markdown_notes === "string" && memberPreview.markdown_notes.trim()) {
    record.markdown_notes = memberPreview.markdown_notes;
  }
  return record;
}

function buildChildGroupRecordFromMemberPreview(memberPreview: JsonRecord): JsonRecord {
  const record: JsonRecord = {
    name: previewName(memberPreview, "Unknown group")
  };
  if (typeof memberPreview.group_type === "string" && memberPreview.group_type.trim()) {
    record.group_type = memberPreview.group_type;
  }
  return record;
}

function buildGroupMembershipSubjectRecord(payload: JsonRecord): JsonRecord {
  const entryRef = asRecord(payload.entry_ref);
  const memberPreview = asRecord(payload.member_preview);
  if (Object.keys(entryRef).length > 0) {
    return buildEntryRecordFromMemberPreview(memberPreview);
  }
  return buildChildGroupRecordFromMemberPreview(memberPreview);
}

function decorateGroupMembershipRecord(
  subjectRecord: JsonRecord,
  options: {
    groupName: string;
    memberRole: string | null;
    includeMembership: boolean;
  }
): JsonRecord {
  const { groupName, memberRole, includeMembership } = options;
  if (!includeMembership) {
    return { ...subjectRecord };
  }
  return {
    ...subjectRecord,
    group: groupName,
    ...(memberRole ? { member_role: memberRole } : {})
  };
}

export function buildGroupMembershipDiff(
  payload: JsonRecord,
  metadata: DiffMetadata[],
  action: "add" | "remove",
  reviewerOverride?: JsonRecord
): ProposalDiff {
  const reviewerEdited = Boolean(reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride));
  const effectivePayload = reviewerEdited
    ? {
        ...payload,
        ...reviewerOverride,
        group_preview: reviewerOverride?.group_preview ?? payload.group_preview,
        member_preview: reviewerOverride?.member_preview ?? payload.member_preview
      }
    : payload;
  const subjectRecord = buildGroupMembershipSubjectRecord(payload);
  const parentGroup = asRecord(effectivePayload.group_preview);
  const groupName = previewName(parentGroup, "Unknown group");
  const memberRole =
    typeof effectivePayload.member_role === "string" && effectivePayload.member_role.trim()
      ? effectivePayload.member_role
      : null;
  const before = decorateGroupMembershipRecord(subjectRecord, {
    groupName,
    memberRole,
    includeMembership: action === "remove"
  });
  const after = decorateGroupMembershipRecord(subjectRecord, {
    groupName,
    memberRole,
    includeMembership: action === "add"
  });
  return buildRecordUpdateDiff(before, after, metadata, { reviewerEdited });
}
