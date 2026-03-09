import type { AgentChangeType } from "../../../lib/types";

export type DiffLineSign = "+" | "-";

export interface DiffLine {
  sign: DiffLineSign;
  path: string;
  value: string;
}

export interface DiffMetadata {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "danger";
}

export interface DiffStats {
  added: number;
  changed: number;
  removed: number;
}

export interface ProposalDiff {
  mode: "create" | "update" | "delete" | "snapshot";
  title: string;
  lines: DiffLine[];
  stats: DiffStats;
  metadata: DiffMetadata[];
  note?: string;
}

interface FlatField {
  rawPath: string;
  displayPath: string;
  value: string;
}

type JsonRecord = Record<string, unknown>;
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
  currency_code: "currency",
  is_active: "active",
  from_entity: "from",
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

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
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

function compareRawPaths(left: string, right: string): number {
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

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function hasField(record: JsonRecord, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
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

function pushMetadata(
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

function buildSnapshotLines(record: JsonRecord, sign: DiffLineSign): DiffLine[] {
  return flattenRecord(record).map((field) => ({
    sign,
    path: field.displayPath,
    value: field.value
  }));
}

function buildDeltaLines(before: JsonRecord, after: JsonRecord): DiffLine[] {
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

function withComputedStats(diff: Omit<ProposalDiff, "stats">): ProposalDiff {
  return {
    ...diff,
    stats: buildStats(diff.lines)
  };
}

function selectorSummary(selector: JsonRecord): string {
  const date = typeof selector.date === "string" ? selector.date : null;
  const name = typeof selector.name === "string" ? selector.name : null;
  const amountMinor = typeof selector.amount_minor === "number" ? selector.amount_minor : null;

  const parts = [date, name, amountMinor !== null ? formatMinorAmount(amountMinor) : null].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "selector";
}

function buildCreateDiff(
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

function buildUpdateDiff(
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

function buildDeleteDiff(
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

function buildRecordUpdateDiff(
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

function previewName(preview: JsonRecord, fallback: string): string {
  const name = preview.name;
  return typeof name === "string" && name.trim() ? name : fallback;
}

function buildGroupRecord(payload: JsonRecord): JsonRecord {
  return {
    name: typeof payload.name === "string" ? payload.name : "",
    group_type: typeof payload.group_type === "string" ? payload.group_type : "BUNDLE"
  };
}

function buildAccountRecord(payload: JsonRecord): JsonRecord {
  return {
    name: typeof payload.name === "string" ? payload.name : "",
    currency_code: typeof payload.currency_code === "string" ? payload.currency_code : "",
    is_active: typeof payload.is_active === "boolean" ? payload.is_active : true,
    markdown_body:
      typeof payload.markdown_body === "string" || payload.markdown_body === null ? payload.markdown_body : null
  };
}

function buildUpdateAccountBeforeRecord(payload: JsonRecord): JsonRecord {
  const current = asRecord(payload.current);
  return buildAccountRecord({
    name: typeof current.name === "string" ? current.name : payload.name,
    currency_code: current.currency_code,
    is_active: current.is_active,
    markdown_body: Object.prototype.hasOwnProperty.call(current, "markdown_body") ? current.markdown_body : null
  });
}

function buildUpdateAccountAfterRecord(
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

function buildUpdateGroupBeforeRecord(payload: JsonRecord): JsonRecord {
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

function buildUpdateGroupAfterRecord(payload: JsonRecord, reviewerOverride?: JsonRecord): { before: JsonRecord; after: JsonRecord; reviewerEdited: boolean } {
  const before = buildUpdateGroupBeforeRecord(payload);
  const effectivePatch =
    reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride) ? asRecord(reviewerOverride.patch) : asRecord(payload.patch);
  return {
    before,
    after: {
      ...before,
      ...(typeof effectivePatch.name === "string" ? { name: effectivePatch.name } : {})
    },
    reviewerEdited: Boolean(reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride))
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

function buildGroupMembershipDiff(
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

export function jsonRecordsAreEquivalent(left: JsonRecord, right: JsonRecord): boolean {
  const normalizedLeft = normalizeForComparison(left);
  const normalizedRight = normalizeForComparison(right);
  return JSON.stringify(normalizedLeft) === JSON.stringify(normalizedRight);
}

export function buildProposalDiff(
  changeType: AgentChangeType,
  payload: JsonRecord,
  reviewerOverride?: JsonRecord
): ProposalDiff {
  const metadata: DiffMetadata[] = [];
  const effectivePatch =
    reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride) ? asRecord(reviewerOverride.patch) : asRecord(payload.patch);

  if (hasField(payload, "name")) {
    pushMetadata(metadata, "Target", payload.name);
  }
  if (hasField(payload, "kind")) {
    pushMetadata(metadata, "Kind", payload.kind);
  }
  if (hasField(payload, "date")) {
    pushMetadata(metadata, "Date", payload.date);
  }

  const selector = asRecord(payload.selector);
  if (Object.keys(selector).length > 0) {
    pushMetadata(metadata, "Selector", selectorSummary(selector));
  }

  if (Object.keys(effectivePatch).length > 0) {
    pushMetadata(metadata, "Patch fields", Object.keys(effectivePatch).length);
  }

  const impactPreview = asRecord(payload.impact_preview);
  if (Object.keys(impactPreview).length > 0) {
    const entryCount = typeof impactPreview.entry_count === "number" ? impactPreview.entry_count : null;
    const accountCount = typeof impactPreview.account_count === "number" ? impactPreview.account_count : null;
    const snapshotCount = typeof impactPreview.snapshot_count === "number" ? impactPreview.snapshot_count : null;
    if (entryCount !== null) {
      pushMetadata(metadata, "Impacted entries", entryCount, entryCount > 0 ? "warning" : "neutral");
    }
    if (accountCount !== null) {
      pushMetadata(metadata, "Impacted accounts", accountCount, accountCount > 0 ? "warning" : "neutral");
    }
    if (snapshotCount !== null) {
      pushMetadata(metadata, "Snapshots", snapshotCount, snapshotCount > 0 ? "warning" : "neutral");
    }
  }

  switch (changeType) {
    case "create_account":
      return buildCreateDiff(buildAccountRecord(payload), metadata, reviewerOverride ? buildAccountRecord(reviewerOverride) : undefined);
    case "create_entry":
    case "create_tag":
    case "create_entity":
      return buildCreateDiff(payload, metadata, reviewerOverride);
    case "create_group": {
      pushMetadata(metadata, "Group type", (reviewerOverride?.group_type as unknown) ?? payload.group_type);
      return buildCreateDiff(buildGroupRecord(payload), metadata, reviewerOverride ? buildGroupRecord(reviewerOverride) : undefined);
    }
    case "update_account": {
      const { before, after, reviewerEdited } = buildUpdateAccountAfterRecord(payload, reviewerOverride);
      return buildRecordUpdateDiff(before, after, metadata, { reviewerEdited });
    }
    case "update_entry":
    case "update_tag":
    case "update_entity":
      return buildUpdateDiff(payload, metadata, reviewerOverride);
    case "update_group": {
      pushMetadata(metadata, "Group ID", payload.group_id);
      pushMetadata(metadata, "Group type", asRecord(payload.current).group_type);
      const { before, after, reviewerEdited } = buildUpdateGroupAfterRecord(payload, reviewerOverride);
      return buildRecordUpdateDiff(before, after, metadata, { reviewerEdited });
    }
    case "delete_entry":
      return buildDeleteDiff(payload, metadata, selector);
    case "delete_account":
      return buildDeleteDiff(payload, metadata, asRecord(impactPreview.current));
    case "delete_group": {
      pushMetadata(metadata, "Group ID", payload.group_id);
      return buildDeleteDiff(payload, metadata, buildUpdateGroupBeforeRecord(payload));
    }
    case "delete_tag":
    case "delete_entity": {
      const identity: JsonRecord = {};
      if (hasField(payload, "name")) {
        identity.name = payload.name;
      }
      return buildDeleteDiff(payload, metadata, identity);
    }
    case "create_group_member": {
      const parentGroup = asRecord(payload.group_preview);
      const memberPreview = asRecord(payload.member_preview);
      pushMetadata(metadata, "Group", previewName(parentGroup, "Unknown group"));
      pushMetadata(metadata, "Member", previewName(memberPreview, "Unknown member"));
      pushMetadata(metadata, "Group type", parentGroup.group_type);
      if (typeof payload.member_role === "string") {
        pushMetadata(metadata, "Split role", payload.member_role);
      }
      return buildGroupMembershipDiff(payload, metadata, "add", reviewerOverride);
    }
    case "delete_group_member": {
      const parentGroup = asRecord(payload.group_preview);
      const memberPreview = asRecord(payload.member_preview);
      pushMetadata(metadata, "Group", previewName(parentGroup, "Unknown group"));
      pushMetadata(metadata, "Member", previewName(memberPreview, "Unknown member"));
      pushMetadata(metadata, "Group type", parentGroup.group_type);
      return buildGroupMembershipDiff(payload, metadata, "remove");
    }
    default:
      return withComputedStats({
        mode: "snapshot",
        title: "Payload snapshot",
        lines: buildSnapshotLines(payload, "+"),
        metadata
      });
  }
}
