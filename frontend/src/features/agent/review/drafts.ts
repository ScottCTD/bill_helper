import type { AgentChangeItem, Entity, EntryKind, GroupMemberRole, GroupType } from "../../../lib/types";

type JsonRecord = Record<string, unknown>;

export interface EntryReviewDraft {
  kind: EntryKind;
  date: string;
  name: string;
  amountMajor: string;
  currencyCode: string;
  fromEntity: string;
  toEntity: string;
  tags: string[];
  markdownNotes: string;
}

export interface TagReviewDraft {
  name: string;
  type: string;
}

export interface EntityReviewDraft {
  name: string;
  category: string;
}

export interface GroupReviewDraft {
  name: string;
  groupType: GroupType;
}

export interface GroupMembershipReviewDraft {
  groupId: string;
  entryId: string;
  childGroupId: string;
  memberRole: GroupMemberRole | "";
}

export interface ReviewOverrideState {
  hasChanges: boolean;
  payloadOverride?: JsonRecord;
  validationError: string | null;
}

interface EntryRecord {
  kind: EntryKind;
  date: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity: string;
  to_entity: string;
  tags: string[];
  markdown_notes: string | null;
}

interface TagRecord {
  name: string;
  type: string | null;
}

interface EntityRecord {
  name: string;
  category: string | null;
}

interface GroupRecord {
  name: string;
  group_type: GroupType;
}

interface GroupMembershipRecord {
  action: "add";
  group_ref: JsonRecord;
  entry_ref: JsonRecord | null;
  child_group_ref: JsonRecord | null;
  member_role: GroupMemberRole | null;
}

const ENTRY_UPDATE_KEYS = [
  "kind",
  "date",
  "name",
  "amount_minor",
  "currency_code",
  "from_entity",
  "to_entity",
  "tags",
  "markdown_notes"
] as const;

const TAG_UPDATE_KEYS = ["name", "type"] as const;
const ENTITY_UPDATE_KEYS = ["name", "category"] as const;
const GROUP_UPDATE_KEYS = ["name"] as const;

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function asString(value: unknown, fallback: string = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asEntryKind(value: unknown): EntryKind {
  return value === "INCOME" || value === "TRANSFER" ? value : "EXPENSE";
}

function asPositiveInt(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.round(value) : 0;
}

function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeRequiredText(value: string): string {
  return value.trim();
}

function normalizeReferenceId(value: string): string {
  return value.trim().toLowerCase();
}

function normalizeTags(tags: string[]): string[] {
  return Array.from(
    new Set(
      tags
        .map((tag) => tag.trim().toLowerCase())
        .filter((tag) => tag.length > 0)
        .sort((left, right) => left.localeCompare(right))
    )
  );
}

function amountMinorToMajor(value: number): string {
  return value > 0 ? (value / 100).toFixed(2) : "";
}

function normalizeEntryRecord(record: EntryRecord): EntryRecord {
  return {
    kind: record.kind,
    date: normalizeRequiredText(record.date),
    name: normalizeRequiredText(record.name),
    amount_minor: Math.round(record.amount_minor),
    currency_code: normalizeRequiredText(record.currency_code).toUpperCase(),
    from_entity: normalizeRequiredText(record.from_entity),
    to_entity: normalizeRequiredText(record.to_entity),
    tags: normalizeTags(record.tags),
    markdown_notes: normalizeOptionalText(record.markdown_notes ?? "")
  };
}

function normalizeTagRecord(record: TagRecord): TagRecord {
  return {
    name: normalizeRequiredText(record.name).toLowerCase(),
    type: normalizeOptionalText(record.type ?? "")
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

function recordsEqual<T>(left: T, right: T): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function buildCreateEntryRecord(payload: JsonRecord, defaultCurrencyCode: string): EntryRecord {
  return normalizeEntryRecord({
    kind: asEntryKind(payload.kind),
    date: asString(payload.date),
    name: asString(payload.name),
    amount_minor: asPositiveInt(payload.amount_minor),
    currency_code: asString(payload.currency_code, defaultCurrencyCode || "USD"),
    from_entity: asString(payload.from_entity),
    to_entity: asString(payload.to_entity),
    tags: Array.isArray(payload.tags) ? payload.tags.filter((value): value is string => typeof value === "string") : [],
    markdown_notes: asNullableString(payload.markdown_notes)
  });
}

function buildUpdateEntryTargetRecord(payload: JsonRecord): EntryRecord {
  const target = asRecord(payload.target);
  const patch = asRecord(payload.patch);
  return normalizeEntryRecord({
    kind: asEntryKind(patch.kind ?? target.kind),
    date: asString(patch.date ?? target.date),
    name: asString(patch.name ?? target.name),
    amount_minor: asPositiveInt(patch.amount_minor ?? target.amount_minor),
    currency_code: asString(patch.currency_code ?? target.currency_code),
    from_entity: asString(patch.from_entity ?? target.from_entity),
    to_entity: asString(patch.to_entity ?? target.to_entity),
    tags: Array.isArray(patch.tags)
      ? patch.tags.filter((value): value is string => typeof value === "string")
      : Array.isArray(target.tags)
        ? target.tags.filter((value): value is string => typeof value === "string")
        : [],
    markdown_notes: asNullableString(
      Object.prototype.hasOwnProperty.call(patch, "markdown_notes") ? patch.markdown_notes : target.markdown_notes
    )
  });
}

function buildBaseEntryTargetRecord(payload: JsonRecord, defaultCurrencyCode: string): EntryRecord {
  if (payload.selector) {
    return normalizeEntryRecord({
      kind: asEntryKind(asRecord(payload.target).kind),
      date: asString(asRecord(payload.target).date),
      name: asString(asRecord(payload.target).name),
      amount_minor: asPositiveInt(asRecord(payload.target).amount_minor),
      currency_code: asString(asRecord(payload.target).currency_code, defaultCurrencyCode || "USD"),
      from_entity: asString(asRecord(payload.target).from_entity),
      to_entity: asString(asRecord(payload.target).to_entity),
      tags: Array.isArray(asRecord(payload.target).tags)
        ? (asRecord(payload.target).tags as unknown[]).filter((value): value is string => typeof value === "string")
        : [],
      markdown_notes: asNullableString(asRecord(payload.target).markdown_notes)
    });
  }
  return buildCreateEntryRecord(payload, defaultCurrencyCode);
}

function buildCreateTagRecord(payload: JsonRecord): TagRecord {
  return normalizeTagRecord({
    name: asString(payload.name),
    type: asNullableString(payload.type)
  });
}

function buildUpdateTagCurrentRecord(payload: JsonRecord): TagRecord {
  const current = asRecord(payload.current);
  return normalizeTagRecord({
    name: asString(current.name ?? payload.name),
    type: asNullableString(current.type)
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

function buildCreateEntityRecord(payload: JsonRecord): EntityRecord {
  return normalizeEntityRecord({
    name: asString(payload.name),
    category: asNullableString(payload.category)
  });
}

function buildCreateGroupRecord(payload: JsonRecord): GroupRecord {
  const rawType = asString(payload.group_type, "BUNDLE");
  const groupType: GroupType =
    rawType === "SPLIT" || rawType === "RECURRING" ? rawType : "BUNDLE";
  return normalizeGroupRecord({
    name: asString(payload.name),
    group_type: groupType
  });
}

function buildUpdateGroupCurrentRecord(payload: JsonRecord): GroupRecord {
  const current = asRecord(payload.current);
  const rawType = asString(current.group_type, "BUNDLE");
  const groupType: GroupType =
    rawType === "SPLIT" || rawType === "RECURRING" ? rawType : "BUNDLE";
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

function buildEntryPatch(target: EntryRecord, next: EntryRecord, originalPatch: JsonRecord): JsonRecord {
  const patch: JsonRecord = {};

  ENTRY_UPDATE_KEYS.forEach((key) => {
    if (!recordsEqual(target[key], next[key])) {
      patch[key] = next[key];
    }
  });

  if (Object.keys(patch).length === 0) {
    Object.keys(originalPatch).forEach((key) => {
      if (!ENTRY_UPDATE_KEYS.includes(key as (typeof ENTRY_UPDATE_KEYS)[number])) {
        return;
      }
      patch[key] = target[key as keyof EntryRecord];
    });
  }

  return patch;
}

function buildSimplePatch<TRecord extends TagRecord | EntityRecord | GroupRecord>(
  keys: readonly string[],
  current: TRecord,
  next: TRecord,
  originalPatch: JsonRecord
): JsonRecord {
  const patch: JsonRecord = {};

  keys.forEach((key) => {
    if (!recordsEqual(current[key as keyof TRecord], next[key as keyof TRecord])) {
      patch[key] = next[key as keyof TRecord];
    }
  });

  if (Object.keys(patch).length === 0) {
    Object.keys(originalPatch).forEach((key) => {
      if (!keys.includes(key)) {
        return;
      }
      patch[key] = current[key as keyof TRecord];
    });
  }

  return patch;
}

export function buildEntryReviewDraft(item: AgentChangeItem, defaultCurrencyCode: string): EntryReviewDraft {
  const payload = item.payload_json;
  const effectiveRecord =
    item.change_type === "update_entry" ? buildUpdateEntryTargetRecord(payload) : buildCreateEntryRecord(payload, defaultCurrencyCode);

  return buildEntryReviewDraftFromRecord(effectiveRecord, defaultCurrencyCode);
}

export function buildEntryReviewDraftFromPreview(preview: JsonRecord, defaultCurrencyCode: string): EntryReviewDraft {
  return buildEntryReviewDraftFromRecord(buildCreateEntryRecord(preview, defaultCurrencyCode), defaultCurrencyCode);
}

function buildEntryReviewDraftFromRecord(record: EntryRecord, defaultCurrencyCode: string): EntryReviewDraft {
  return {
    kind: record.kind,
    date: record.date,
    name: record.name,
    amountMajor: amountMinorToMajor(record.amount_minor),
    currencyCode: record.currency_code || defaultCurrencyCode || "USD",
    fromEntity: record.from_entity,
    toEntity: record.to_entity,
    tags: record.tags,
    markdownNotes: record.markdown_notes ?? ""
  };
}

export function buildTagReviewDraft(item: AgentChangeItem): TagReviewDraft {
  const record = item.change_type === "update_tag" ? buildUpdateTagEffectiveRecord(item.payload_json) : buildCreateTagRecord(item.payload_json);
  return {
    name: record.name,
    type: record.type ?? ""
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
  const record = item.change_type === "update_group" ? buildUpdateGroupEffectiveRecord(item.payload_json) : buildCreateGroupRecord(item.payload_json);
  return {
    name: record.name,
    groupType: record.group_type
  };
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

export function uniqueEntityOptionNames(entities: Entity[], draftValues: string[] = []): string[] {
  const seen = new Set<string>();
  return [...entities.map((entity) => entity.name), ...draftValues]
    .map((value) => value.trim())
    .filter((value) => {
      const normalized = value.toLowerCase();
      if (!normalized || seen.has(normalized)) {
        return false;
      }
      seen.add(normalized);
      return true;
    })
    .sort((left, right) => left.localeCompare(right));
}

export function buildEntryOverrideState(
  item: AgentChangeItem,
  draft: EntryReviewDraft,
  defaultCurrencyCode: string
): ReviewOverrideState {
  const amountMinor = Math.round(Number(draft.amountMajor) * 100);
  const normalizedRecord = normalizeEntryRecord({
    kind: draft.kind,
    date: draft.date,
    name: draft.name,
    amount_minor: amountMinor,
    currency_code: draft.currencyCode || defaultCurrencyCode,
    from_entity: draft.fromEntity,
    to_entity: draft.toEntity,
    tags: draft.tags,
    markdown_notes: normalizeOptionalText(draft.markdownNotes)
  });

  if (!normalizedRecord.date) {
    return { hasChanges: false, validationError: "Date is required." };
  }
  if (!normalizedRecord.name) {
    return { hasChanges: false, validationError: "Name is required." };
  }
  if (!Number.isFinite(amountMinor) || amountMinor <= 0) {
    return { hasChanges: false, validationError: "Amount must be greater than 0." };
  }
  if (!normalizedRecord.currency_code) {
    return { hasChanges: false, validationError: "Currency is required." };
  }
  if (!normalizedRecord.from_entity) {
    return { hasChanges: false, validationError: "From entity is required." };
  }
  if (!normalizedRecord.to_entity) {
    return { hasChanges: false, validationError: "To entity is required." };
  }

  if (item.change_type === "create_entry") {
    const baseRecord = buildCreateEntryRecord(item.payload_json, defaultCurrencyCode);
    const hasChanges = !recordsEqual(baseRecord, normalizedRecord);
    return {
      hasChanges,
      payloadOverride: hasChanges ? { ...normalizedRecord } : undefined,
      validationError: null
    };
  }

  const payload = item.payload_json;
  const currentRecord = buildBaseEntryTargetRecord(payload, defaultCurrencyCode);
  const effectiveRecord = buildUpdateEntryTargetRecord(payload);
  const hasChanges = !recordsEqual(effectiveRecord, normalizedRecord);
  if (!hasChanges) {
    return { hasChanges: false, validationError: null };
  }

  return {
    hasChanges,
    payloadOverride: {
      selector: asRecord(payload.selector),
      patch: buildEntryPatch(currentRecord, normalizedRecord, asRecord(payload.patch))
    },
    validationError: null
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
