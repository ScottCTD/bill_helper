import type { AgentChangeItem, Entity, EntryKind } from "../../../lib/types";

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

function buildSimplePatch<TRecord extends TagRecord | EntityRecord>(
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

  return {
    kind: effectiveRecord.kind,
    date: effectiveRecord.date,
    name: effectiveRecord.name,
    amountMajor: amountMinorToMajor(effectiveRecord.amount_minor),
    currencyCode: effectiveRecord.currency_code,
    fromEntity: effectiveRecord.from_entity,
    toEntity: effectiveRecord.to_entity,
    tags: effectiveRecord.tags,
    markdownNotes: effectiveRecord.markdown_notes ?? ""
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
