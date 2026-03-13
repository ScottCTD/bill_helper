/**
 * CALLING SPEC:
 * - Purpose: expose filter-group API calls for the frontend.
 * - Inputs: filter-group ids and create or update payloads.
 * - Outputs: filter-group read models or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type { FilterGroup, FilterGroupRule } from "../types";
import { request } from "./core";

export function listFilterGroups(): Promise<FilterGroup[]> {
  return request<FilterGroup[]>("/api/v1/filter-groups");
}

export function createFilterGroup(payload: {
  name: string;
  description?: string | null;
  color?: string | null;
  rule: FilterGroupRule;
}): Promise<FilterGroup> {
  return request<FilterGroup>("/api/v1/filter-groups", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateFilterGroup(
  filterGroupId: string,
  payload: {
    name?: string | null;
    description?: string | null;
    color?: string | null;
    rule?: FilterGroupRule | null;
  }
): Promise<FilterGroup> {
  return request<FilterGroup>(`/api/v1/filter-groups/${filterGroupId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteFilterGroup(filterGroupId: string): Promise<void> {
  return request<void>(`/api/v1/filter-groups/${filterGroupId}`, {
    method: "DELETE"
  });
}
