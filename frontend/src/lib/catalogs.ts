import type { TaxonomyTerm } from "./types";

export const ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category";
export const TAG_TYPE_TAXONOMY_KEY = "tag_type";

export function normalizeFilterValue(value: string) {
  return value.trim().toLowerCase();
}

export function includesFilter(value: string | null | undefined, query: string) {
  const normalized = normalizeFilterValue(query);
  if (!normalized) {
    return true;
  }
  return (value ?? "").toLowerCase().includes(normalized);
}

export function uniqueOptionValues(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const uniqueValues: string[] = [];
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed) {
      continue;
    }
    const normalized = trimmed.toLowerCase();
    if (seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    uniqueValues.push(trimmed);
  }
  return uniqueValues.sort((left, right) => left.localeCompare(right));
}

export function taxonomyTermNames(terms: TaxonomyTerm[] | undefined) {
  return (terms ?? []).map((term) => term.name);
}
