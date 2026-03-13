/**
 * CALLING SPEC:
 * - Purpose: provide the `entries` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/drafts/entries.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `entries`.
 * - Side effects: module-local frontend behavior only.
 */
import type { AgentChangeItem, Entity, EntryKind } from "../../../../lib/types";

import {
  amountMinorToMajor,
  asEntryKind,
  asNullableString,
  asPositiveInt,
  asRecord,
  asString,
  normalizeOptionalText,
  normalizeRequiredText,
  normalizeTags,
  recordsEqual
} from "./common";
import type { EntryReviewDraft, JsonRecord, ReviewOverrideState } from "./types";

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
    const target = asRecord(payload.target);
    return normalizeEntryRecord({
      kind: asEntryKind(target.kind),
      date: asString(target.date),
      name: asString(target.name),
      amount_minor: asPositiveInt(target.amount_minor),
      currency_code: asString(target.currency_code, defaultCurrencyCode || "USD"),
      from_entity: asString(target.from_entity),
      to_entity: asString(target.to_entity),
      tags: Array.isArray(target.tags) ? (target.tags as unknown[]).filter((value): value is string => typeof value === "string") : [],
      markdown_notes: asNullableString(target.markdown_notes)
    });
  }
  return buildCreateEntryRecord(payload, defaultCurrencyCode);
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

export function buildEntryReviewDraft(item: AgentChangeItem, defaultCurrencyCode: string): EntryReviewDraft {
  const effectiveRecord =
    item.change_type === "update_entry"
      ? buildUpdateEntryTargetRecord(item.payload_json)
      : buildCreateEntryRecord(item.payload_json, defaultCurrencyCode);

  return buildEntryReviewDraftFromRecord(effectiveRecord, defaultCurrencyCode);
}

export function buildEntryReviewDraftFromPreview(preview: JsonRecord, defaultCurrencyCode: string): EntryReviewDraft {
  return buildEntryReviewDraftFromRecord(buildCreateEntryRecord(preview, defaultCurrencyCode), defaultCurrencyCode);
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
