/**
 * CALLING SPEC:
 * - Purpose: provide the `catalog` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/drafts/catalog.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `catalog`.
 * - Side effects: module-local frontend behavior only.
 */
import type { AgentChangeItem, GroupType } from "../../../../lib/types";

import {
  asNullableString,
  asRecord,
  asString,
  buildSimplePatch,
  normalizeOptionalText,
  normalizeRequiredText,
  recordsEqual
} from "./common";
import type {
  AccountReviewDraft,
  EntityReviewDraft,
  GroupReviewDraft,
  JsonRecord,
  ReviewOverrideState,
  SnapshotReviewDraft,
  TagReviewDraft
} from "./types";

interface TagRecord {
  name: string;
  type: string | null;
}

interface AccountRecord {
  name: string;
  currency_code: string;
  is_active: boolean;
  markdown_body: string | null;
}

interface SnapshotRecord {
  snapshot_at: string;
  balance_minor: number;
  note: string | null;
}

interface EntityRecord {
  name: string;
  category: string | null;
}

interface GroupRecord {
  name: string;
  group_type: GroupType;
}

const TAG_UPDATE_KEYS = ["name", "type"] as const;
const ACCOUNT_UPDATE_KEYS = ["name", "currency_code", "is_active", "markdown_body"] as const;
const ENTITY_UPDATE_KEYS = ["name", "category"] as const;
const GROUP_UPDATE_KEYS = ["name"] as const;

function normalizeTagRecord(record: TagRecord): TagRecord {
  return {
    name: normalizeRequiredText(record.name).toLowerCase(),
    type: normalizeOptionalText(record.type ?? "")
  };
}

function normalizeAccountRecord(record: AccountRecord): AccountRecord {
  return {
    name: normalizeRequiredText(record.name),
    currency_code: normalizeRequiredText(record.currency_code).toUpperCase(),
    is_active: record.is_active,
    markdown_body: normalizeOptionalText(record.markdown_body ?? "")
  };
}

function normalizeSnapshotRecord(record: SnapshotRecord): SnapshotRecord {
  return {
    snapshot_at: normalizeRequiredText(record.snapshot_at),
    balance_minor: record.balance_minor,
    note: normalizeOptionalText(record.note ?? "")
  };
}

function normalizeEntityRecord(record: EntityRecord): EntityRecord {
  return {
    name: normalizeRequiredText(record.name),
    category: normalizeOptionalText(record.category ?? "")
  };
}

function normalizeGroupRecord(record: GroupRecord): GroupRecord {
  return {
    name: normalizeRequiredText(record.name),
    group_type: record.group_type
  };
}

function buildCreateTagRecord(payload: JsonRecord): TagRecord {
  return normalizeTagRecord({
    name: asString(payload.name),
    type: asNullableString(payload.type)
  });
}

function buildCreateAccountRecord(payload: JsonRecord): AccountRecord {
  return normalizeAccountRecord({
    name: asString(payload.name),
    currency_code: asString(payload.currency_code),
    is_active: typeof payload.is_active === "boolean" ? payload.is_active : true,
    markdown_body: asNullableString(payload.markdown_body)
  });
}

function buildCreateSnapshotRecord(payload: JsonRecord): SnapshotRecord {
  return normalizeSnapshotRecord({
    snapshot_at: asString(payload.snapshot_at),
    balance_minor: typeof payload.balance_minor === "number" ? payload.balance_minor : 0,
    note: asNullableString(payload.note)
  });
}

function buildUpdateTagCurrentRecord(payload: JsonRecord): TagRecord {
  const current = asRecord(payload.current);
  return normalizeTagRecord({
    name: asString(current.name ?? payload.name),
    type: asNullableString(current.type)
  });
}

function buildUpdateAccountCurrentRecord(payload: JsonRecord): AccountRecord {
  const current = asRecord(payload.current);
  return normalizeAccountRecord({
    name: asString(current.name ?? payload.name),
    currency_code: asString(current.currency_code),
    is_active: typeof current.is_active === "boolean" ? current.is_active : true,
    markdown_body: asNullableString(current.markdown_body)
  });
}

function buildUpdateTagEffectiveRecord(payload: JsonRecord): TagRecord {
  const current = buildUpdateTagCurrentRecord(payload);
  const patch = asRecord(payload.patch);
  return normalizeTagRecord({
    name: asString(patch.name ?? current.name),
    type: Object.prototype.hasOwnProperty.call(patch, "type") ? asNullableString(patch.type) : current.type
  });
}

function buildUpdateAccountEffectiveRecord(payload: JsonRecord): AccountRecord {
  const current = buildUpdateAccountCurrentRecord(payload);
  const patch = asRecord(payload.patch);
  return normalizeAccountRecord({
    name: asString(patch.name ?? current.name),
    currency_code: asString(patch.currency_code ?? current.currency_code),
    is_active: typeof patch.is_active === "boolean" ? patch.is_active : current.is_active,
    markdown_body: Object.prototype.hasOwnProperty.call(patch, "markdown_body")
      ? asNullableString(patch.markdown_body)
      : current.markdown_body
  });
}

function buildCreateEntityRecord(payload: JsonRecord): EntityRecord {
  return normalizeEntityRecord({
    name: asString(payload.name),
    category: asNullableString(payload.category)
  });
}

function buildCreateGroupRecord(payload: JsonRecord): GroupRecord {
  const rawType = asString(payload.group_type, "BUNDLE");
  const groupType: GroupType = rawType === "SPLIT" || rawType === "RECURRING" ? rawType : "BUNDLE";
  return normalizeGroupRecord({
    name: asString(payload.name),
    group_type: groupType
  });
}

function buildUpdateGroupCurrentRecord(payload: JsonRecord): GroupRecord {
  const current = asRecord(payload.current);
  const rawType = asString(current.group_type, "BUNDLE");
  const groupType: GroupType = rawType === "SPLIT" || rawType === "RECURRING" ? rawType : "BUNDLE";
  return normalizeGroupRecord({
    name: asString(current.name ?? asRecord(payload.target).name),
    group_type: groupType
  });
}

function buildUpdateGroupEffectiveRecord(payload: JsonRecord): GroupRecord {
  const current = buildUpdateGroupCurrentRecord(payload);
  const patch = asRecord(payload.patch);
  return normalizeGroupRecord({
    name: asString(patch.name ?? current.name),
    group_type: current.group_type
  });
}

function buildUpdateEntityCurrentRecord(payload: JsonRecord): EntityRecord {
  const current = asRecord(payload.current);
  return normalizeEntityRecord({
    name: asString(current.name ?? payload.name),
    category: asNullableString(current.category)
  });
}

function buildUpdateEntityEffectiveRecord(payload: JsonRecord): EntityRecord {
  const current = buildUpdateEntityCurrentRecord(payload);
  const patch = asRecord(payload.patch);
  return normalizeEntityRecord({
    name: asString(patch.name ?? current.name),
    category: Object.prototype.hasOwnProperty.call(patch, "category") ? asNullableString(patch.category) : current.category
  });
}

export function buildTagReviewDraft(item: AgentChangeItem): TagReviewDraft {
  const record = item.change_type === "update_tag" ? buildUpdateTagEffectiveRecord(item.payload_json) : buildCreateTagRecord(item.payload_json);
  return {
    name: record.name,
    type: record.type ?? ""
  };
}

export function buildAccountReviewDraft(item: AgentChangeItem): AccountReviewDraft {
  const record =
    item.change_type === "update_account"
      ? buildUpdateAccountEffectiveRecord(item.payload_json)
      : buildCreateAccountRecord(item.payload_json);
  return {
    name: record.name,
    currencyCode: record.currency_code,
    isActive: record.is_active,
    markdownBody: record.markdown_body ?? ""
  };
}

function formatBalanceMajor(balanceMinor: number): string {
  return (balanceMinor / 100).toFixed(2);
}

export function buildSnapshotReviewDraft(item: AgentChangeItem): SnapshotReviewDraft {
  const record = buildCreateSnapshotRecord(item.payload_json);
  return {
    snapshotAt: record.snapshot_at,
    balanceMajor: formatBalanceMajor(record.balance_minor),
    note: record.note ?? ""
  };
}

export function buildEntityReviewDraft(item: AgentChangeItem): EntityReviewDraft {
  const record =
    item.change_type === "update_entity" ? buildUpdateEntityEffectiveRecord(item.payload_json) : buildCreateEntityRecord(item.payload_json);
  return {
    name: record.name,
    category: record.category ?? ""
  };
}

export function buildGroupReviewDraft(item: AgentChangeItem): GroupReviewDraft {
  const record =
    item.change_type === "update_group" ? buildUpdateGroupEffectiveRecord(item.payload_json) : buildCreateGroupRecord(item.payload_json);
  return {
    name: record.name,
    groupType: record.group_type
  };
}

export function buildTagOverrideState(item: AgentChangeItem, draft: TagReviewDraft): ReviewOverrideState {
  const normalizedRecord = normalizeTagRecord({
    name: draft.name,
    type: draft.type
  });
  if (!normalizedRecord.name) {
    return { hasChanges: false, validationError: "Name is required." };
  }

  if (item.change_type === "create_tag") {
    if (!normalizedRecord.type) {
      return { hasChanges: false, validationError: "Type is required." };
    }
    const baseRecord = buildCreateTagRecord(item.payload_json);
    const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
    return {
      hasChanges,
      payloadOverride: hasChanges ? { name: normalizedRecord.name, type: normalizedRecord.type } : undefined,
      validationError: null
    };
  }

  const currentRecord = buildUpdateTagCurrentRecord(item.payload_json);
  const effectiveRecord = buildUpdateTagEffectiveRecord(item.payload_json);
  const hasChanges = !recordsEqual(effectiveRecord, normalizedRecord);
  if (!hasChanges) {
    return { hasChanges: false, validationError: null };
  }

  return {
    hasChanges,
    payloadOverride: {
      name: normalizeTagRecord({ name: asString(item.payload_json.name), type: null }).name,
      patch: buildSimplePatch(TAG_UPDATE_KEYS, currentRecord, normalizedRecord, asRecord(item.payload_json.patch))
    },
    validationError: null
  };
}

export function buildAccountOverrideState(item: AgentChangeItem, draft: AccountReviewDraft): ReviewOverrideState {
  const normalizedRecord = normalizeAccountRecord({
    name: draft.name,
    currency_code: draft.currencyCode,
    is_active: draft.isActive,
    markdown_body: normalizeOptionalText(draft.markdownBody)
  });
  if (!normalizedRecord.name) {
    return { hasChanges: false, validationError: "Name is required." };
  }
  if (!normalizedRecord.currency_code) {
    return { hasChanges: false, validationError: "Currency is required." };
  }

  if (item.change_type === "create_account") {
    const baseRecord = buildCreateAccountRecord(item.payload_json);
    const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
    return {
      hasChanges,
      payloadOverride: hasChanges
        ? {
            name: normalizedRecord.name,
            currency_code: normalizedRecord.currency_code,
            is_active: normalizedRecord.is_active,
            markdown_body: normalizedRecord.markdown_body
          }
        : undefined,
      validationError: null
    };
  }

  const currentRecord = buildUpdateAccountCurrentRecord(item.payload_json);
  const effectiveRecord = buildUpdateAccountEffectiveRecord(item.payload_json);
  const hasChanges = !recordsEqual(effectiveRecord, normalizedRecord);
  if (!hasChanges) {
    return { hasChanges: false, validationError: null };
  }

  return {
    hasChanges,
    payloadOverride: {
      name: asString(item.payload_json.name),
      patch: buildSimplePatch(ACCOUNT_UPDATE_KEYS, currentRecord, normalizedRecord, asRecord(item.payload_json.patch))
    },
    validationError: null
  };
}

export function buildSnapshotOverrideState(item: AgentChangeItem, draft: SnapshotReviewDraft): ReviewOverrideState {
  const normalizedDate = normalizeRequiredText(draft.snapshotAt);
  if (!normalizedDate) {
    return { hasChanges: false, validationError: "Snapshot date is required." };
  }

  const parsedBalance = Number(draft.balanceMajor);
  if (!Number.isFinite(parsedBalance)) {
    return { hasChanges: false, validationError: "Balance must be a valid number." };
  }

  const normalizedRecord = normalizeSnapshotRecord({
    snapshot_at: normalizedDate,
    balance_minor: Math.round(parsedBalance * 100),
    note: draft.note
  });
  const baseRecord = buildCreateSnapshotRecord(item.payload_json);
  const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
  return {
    hasChanges,
    payloadOverride: hasChanges
      ? {
          account_id: asString(item.payload_json.account_id),
          account_name: asString(item.payload_json.account_name),
          currency_code: asString(item.payload_json.currency_code),
          snapshot_at: normalizedRecord.snapshot_at,
          balance_minor: normalizedRecord.balance_minor,
          note: normalizedRecord.note
        }
      : undefined,
    validationError: null
  };
}

export function buildEntityOverrideState(item: AgentChangeItem, draft: EntityReviewDraft): ReviewOverrideState {
  const normalizedRecord = normalizeEntityRecord({
    name: draft.name,
    category: draft.category
  });
  if (!normalizedRecord.name) {
    return { hasChanges: false, validationError: "Name is required." };
  }

  if (item.change_type === "create_entity") {
    if (!normalizedRecord.category) {
      return { hasChanges: false, validationError: "Category is required." };
    }
    const baseRecord = buildCreateEntityRecord(item.payload_json);
    const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
    return {
      hasChanges,
      payloadOverride: hasChanges ? { name: normalizedRecord.name, category: normalizedRecord.category } : undefined,
      validationError: null
    };
  }

  const currentRecord = buildUpdateEntityCurrentRecord(item.payload_json);
  const effectiveRecord = buildUpdateEntityEffectiveRecord(item.payload_json);
  const hasChanges = !recordsEqual(effectiveRecord, normalizedRecord);
  if (!hasChanges) {
    return { hasChanges: false, validationError: null };
  }

  return {
    hasChanges,
    payloadOverride: {
      name: asString(item.payload_json.name),
      patch: buildSimplePatch(ENTITY_UPDATE_KEYS, currentRecord, normalizedRecord, asRecord(item.payload_json.patch))
    },
    validationError: null
  };
}

export function buildGroupOverrideState(item: AgentChangeItem, draft: GroupReviewDraft): ReviewOverrideState {
  const normalizedRecord = normalizeGroupRecord({
    name: draft.name,
    group_type: draft.groupType
  });
  if (!normalizedRecord.name) {
    return { hasChanges: false, validationError: "Name is required." };
  }

  if (item.change_type === "create_group") {
    const baseRecord = buildCreateGroupRecord(item.payload_json);
    const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
    return {
      hasChanges,
      payloadOverride: hasChanges ? { name: normalizedRecord.name, group_type: normalizedRecord.group_type } : undefined,
      validationError: null
    };
  }

  const currentRecord = buildUpdateGroupCurrentRecord(item.payload_json);
  const effectiveRecord = buildUpdateGroupEffectiveRecord(item.payload_json);
  const hasChanges = !recordsEqual(effectiveRecord, normalizedRecord);
  if (!hasChanges) {
    return { hasChanges: false, validationError: null };
  }

  return {
    hasChanges,
    payloadOverride: {
      group_id: asString(item.payload_json.group_id),
      patch: buildSimplePatch(GROUP_UPDATE_KEYS, currentRecord, normalizedRecord, asRecord(item.payload_json.patch))
    },
    validationError: null
  };
}
