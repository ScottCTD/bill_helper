import type { DiffLine, DiffLineSign, DiffMetadata, DiffStats, FlatField, JsonRecord, ProposalDiff } from "./types";

type FlatFieldMap = Map<string, FlatField>;

const ENTRY_FIELD_ORDER: Record<string, number> = {
  date: 0,
  name: 1,
  kind: 2,
  amount_minor: 3,
  currency_code: 4,
  is_active: 5,
  from_entity: 6,
  to_entity: 7,
  tags: 8,
  markdown_body: 9,
  markdown_notes: 10,
  group: 11,
  group_type: 12,
  parent_group: 13,
  parent_group_ref: 14,
  member_kind: 15,
  member: 16,
  member_ref: 17,
  member_role: 18
};

const FIELD_LABELS: Record<string, string> = {
  amount_minor: "amount",
  balance_minor: "balance",
  currency_code: "currency",
  is_active: "active",
  from_entity: "from",
  snapshot_at: "date",
  to_entity: "to",
  markdown_body: "notes",
  markdown_notes: "notes",
  group_type: "group type",
  parent_group: "parent group",
  parent_group_ref: "parent group ref",
  member_kind: "member type",
  member_ref: "member ref",
  member_role: "split role"
};

export function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function normalizeForComparison(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(normalizeForComparison);
  }
  if (isRecord(value)) {
    const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
    return Object.fromEntries(entries.map(([key, child]) => [key, normalizeForComparison(child)]));
  }
  return value;
}

export function jsonRecordsAreEquivalent(left: JsonRecord, right: JsonRecord): boolean {
  const normalizedLeft = normalizeForComparison(left);
  const normalizedRight = normalizeForComparison(right);
  return JSON.stringify(normalizedLeft) === JSON.stringify(normalizedRight);
}

function lastPathSegment(path: string): string {
  const trimmed = path.split(".").at(-1) ?? path;
  return trimmed.replace(/\[\d+\]/g, "");
}

function displayPath(path: string): string {
  return path
    .split(".")
    .map((segment) => {
      const base = segment.replace(/\[\d+\]/g, "");
      const suffix = segment.slice(base.length);
      return `${FIELD_LABELS[base] ?? base}${suffix}`;
    })
    .join(".");
}

function formatMinorAmount(value: number): string {
  const sign = value < 0 ? "-" : "";
  const absoluteMajor = Math.abs(value) / 100;
  const formatted = absoluteMajor.toFixed(2).replace(/\.?0+$/, "");
  return `${sign}${formatted}`;
}

function formatArrayValue(value: unknown[], rawPath: string): string {
  if (value.length === 0) {
    return "[]";
  }
  const allSimple = value.every((item) => ["string", "number", "boolean"].includes(typeof item) || item === null);
  if (!allSimple) {
    return `${value.length} items`;
  }
  return `[${value.map((item) => formatLeafValue(item, rawPath)).join(", ")}]`;
}

function formatLeafValue(value: unknown, rawPath: string): string {
  const leafKey = lastPathSegment(rawPath);
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    if (leafKey === "amount_minor") {
      return formatMinorAmount(value);
    }
    return String(value);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    return formatArrayValue(value, rawPath);
  }
  if (isRecord(value)) {
    return `${Object.keys(value).length} fields`;
  }
  return "";
}

function fieldOrderIndex(path: string): number {
  const leaf = lastPathSegment(path);
  return ENTRY_FIELD_ORDER[leaf] ?? 999;
}

export function compareRawPaths(left: string, right: string): number {
  const orderDelta = fieldOrderIndex(left) - fieldOrderIndex(right);
  if (orderDelta !== 0) {
    return orderDelta;
  }
  return left.localeCompare(right);
}

function flattenValue(value: unknown, path: string, output: FlatField[]): void {
  if (Array.isArray(value)) {
    output.push({
      rawPath: path,
      displayPath: displayPath(path),
      value: formatArrayValue(value, path)
    });
    return;
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
    if (entries.length === 0) {
      output.push({
        rawPath: path,
        displayPath: displayPath(path),
        value: "{}"
      });
      return;
    }
    entries.forEach(([key, child]) => {
      const childPath = path ? `${path}.${key}` : key;
      flattenValue(child, childPath, output);
    });
    return;
  }

  output.push({
    rawPath: path,
    displayPath: displayPath(path),
    value: formatLeafValue(value, path)
  });
}

function flattenRecord(record: JsonRecord): FlatField[] {
  const fields: FlatField[] = [];
  const entries = Object.entries(record).sort(([left], [right]) => left.localeCompare(right));

  entries.forEach(([key, value]) => {
    flattenValue(value, key, fields);
  });

  fields.sort((left, right) => compareRawPaths(left.rawPath, right.rawPath));
  return fields;
}

function mapByPath(fields: FlatField[]): FlatFieldMap {
  const map: FlatFieldMap = new Map();
  fields.forEach((field) => {
    map.set(field.rawPath, field);
  });
  return map;
}

function sanitizeValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (isRecord(value)) {
    return `${Object.keys(value).length} field${Object.keys(value).length === 1 ? "" : "s"}`;
  }
  if (value === null) {
    return "null";
  }
  return "";
}

export function hasField(record: JsonRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

export function pushMetadata(
  target: DiffMetadata[],
  label: string,
  value: unknown,
  tone: DiffMetadata["tone"] = "neutral"
): void {
  const text = sanitizeValue(value).trim();
  if (!text) {
    return;
  }
  target.push({ label, value: text, tone });
}

export function buildSnapshotLines(record: JsonRecord, sign: DiffLineSign): DiffLine[] {
  return flattenRecord(record).map((field) => ({
    sign,
    path: field.displayPath,
    value: field.value
  }));
}

export function buildDeltaLines(before: JsonRecord, after: JsonRecord): DiffLine[] {
  const beforeMap = mapByPath(flattenRecord(before));
  const afterMap = mapByPath(flattenRecord(after));
  const allPaths = Array.from(new Set([...beforeMap.keys(), ...afterMap.keys()])).sort(compareRawPaths);

  const lines: DiffLine[] = [];
  allPaths.forEach((path) => {
    const previous = beforeMap.get(path);
    const next = afterMap.get(path);
    if (previous?.value === next?.value) {
      return;
    }
    if (previous !== undefined) {
      lines.push({ sign: "-", path: previous.displayPath, value: previous.value });
    }
    if (next !== undefined) {
      lines.push({ sign: "+", path: next.displayPath, value: next.value });
    }
  });
  return lines;
}

function buildStats(lines: DiffLine[]): DiffStats {
  const signsByPath = new Map<string, Set<DiffLineSign>>();
  lines.forEach((line) => {
    const signs = signsByPath.get(line.path) ?? new Set<DiffLineSign>();
    signs.add(line.sign);
    signsByPath.set(line.path, signs);
  });

  let changed = 0;
  let added = 0;
  let removed = 0;

  signsByPath.forEach((signs) => {
    if (signs.has("+") && signs.has("-")) {
      changed += 1;
      return;
    }
    if (signs.has("+")) {
      added += 1;
      return;
    }
    removed += 1;
  });

  return { added, changed, removed };
}

export function withComputedStats(diff: Omit<ProposalDiff, "stats">): ProposalDiff {
  return {
    ...diff,
    stats: buildStats(diff.lines)
  };
}

export function selectorSummary(selector: JsonRecord): string {
  const date = typeof selector.date === "string" ? selector.date : null;
  const name = typeof selector.name === "string" ? selector.name : null;
  const amountMinor = typeof selector.amount_minor === "number" ? selector.amount_minor : null;

  const parts = [date, name, amountMinor !== null ? formatMinorAmount(amountMinor) : null].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "selector";
}

export function buildCreateDiff(
  payload: JsonRecord,
  metadata: DiffMetadata[],
  reviewerOverride?: JsonRecord
): ProposalDiff {
  if (reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride)) {
    return withComputedStats({
      mode: "update",
      title: "Reviewer edits",
      lines: buildDeltaLines(payload, reviewerOverride),
      metadata,
      note: "Preview reflects reviewer-edited payload."
    });
  }

  return withComputedStats({
    mode: "create",
    title: "Create fields",
    lines: buildSnapshotLines(payload, "+"),
    metadata
  });
}

export function buildUpdateDiff(
  payload: JsonRecord,
  metadata: DiffMetadata[],
  reviewerOverride?: JsonRecord
): ProposalDiff {
  const overridePatch = asRecord(reviewerOverride?.patch);
  const hasReviewerEdits = Object.keys(overridePatch).length > 0 && !jsonRecordsAreEquivalent(payload, reviewerOverride ?? {});
  const patch = hasReviewerEdits ? overridePatch : asRecord(payload.patch);
  const current = asRecord(payload.current);
  const target = asRecord(payload.target);

  const before = Object.keys(current).length > 0 ? current : target;
  const after = { ...before, ...patch };
  const lines = buildDeltaLines(before, after);

  return withComputedStats({
    mode: "update",
    title: "Changed fields",
    lines,
    metadata,
    note:
      lines.length === 0
        ? "Patch did not change any visible fields."
        : hasReviewerEdits
          ? "Preview reflects reviewer-edited payload."
          : undefined
  });
}

export function buildDeleteDiff(
  payload: JsonRecord,
  metadata: DiffMetadata[],
  defaultFields: JsonRecord
): ProposalDiff {
  const target = asRecord(payload.target);
  const lines =
    Object.keys(target).length > 0
      ? buildSnapshotLines(target, "-")
      : buildSnapshotLines(Object.keys(defaultFields).length > 0 ? defaultFields : payload, "-");

  return withComputedStats({
    mode: "delete",
    title: "Removed fields",
    lines,
    metadata
  });
}

export function buildRecordUpdateDiff(
  before: JsonRecord,
  after: JsonRecord,
  metadata: DiffMetadata[],
  options: { reviewerEdited?: boolean } = {}
): ProposalDiff {
  const { reviewerEdited = false } = options;
  const lines = buildDeltaLines(before, after);
  return withComputedStats({
    mode: "update",
    title: "Changed fields",
    lines,
    metadata,
    note:
      lines.length === 0
        ? "Patch did not change any visible fields."
        : reviewerEdited
          ? "Preview reflects reviewer-edited payload."
          : undefined
  });
}
