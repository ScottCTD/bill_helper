/**
 * CALLING SPEC:
 * - Purpose: provide the `common` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/drafts/common.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `common`.
 * - Side effects: module-local frontend behavior only.
 */
import type { EntryKind } from "../../../../lib/types";

import type { JsonRecord } from "./types";

export function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

export function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function asEntryKind(value: unknown): EntryKind {
  return value === "INCOME" || value === "TRANSFER" ? value : "EXPENSE";
}

export function asPositiveInt(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.round(value) : 0;
}

export function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function normalizeRequiredText(value: string): string {
  return value.trim();
}

export function normalizeReferenceId(value: string): string {
  return value.trim().toLowerCase();
}

export function normalizeTags(tags: string[]): string[] {
  return Array.from(
    new Set(
      tags
        .map((tag) => tag.trim().toLowerCase())
        .filter((tag) => tag.length > 0)
        .sort((left, right) => left.localeCompare(right))
    )
  );
}

export function amountMinorToMajor(value: number): string {
  return value > 0 ? (value / 100).toFixed(2) : "";
}

export function recordsEqual<T>(left: T, right: T): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

export function buildSimplePatch<TRecord extends object>(
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
