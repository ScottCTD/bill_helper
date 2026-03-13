/**
 * CALLING SPEC:
 * - Purpose: expose entry and tag-suggestion API calls for the frontend.
 * - Inputs: entry filters, entry mutation payloads, and tag-suggestion request payloads.
 * - Outputs: entry-domain read models or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type {
  EntryDetail,
  EntryListResponse,
  EntryTagSuggestionRequest,
  EntryTagSuggestionResponse,
  GroupMemberRole
} from "../types";
import { request } from "./core";

export function listEntries(params: {
  start_date?: string;
  end_date?: string;
  kind?: string;
  tag?: string;
  currency?: string;
  source?: string;
  account_id?: string;
  filter_group_id?: string;
  limit?: number;
  offset?: number;
}): Promise<EntryListResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  return request<EntryListResponse>(`/api/v1/entries?${search.toString()}`);
}

export function createEntry(payload: {
  account_id?: string;
  kind: string;
  occurred_at: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity_id?: string;
  to_entity_id?: string;
  owner_user_id: string;
  from_entity?: string;
  to_entity?: string;
  owner?: string;
  markdown_body?: string;
  tags?: string[];
  direct_group_id?: string;
  direct_group_member_role?: GroupMemberRole | null;
}) {
  return request("/api/v1/entries", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getEntry(entryId: string): Promise<EntryDetail> {
  return request<EntryDetail>(`/api/v1/entries/${entryId}`);
}

export function updateEntry(entryId: string, payload: object) {
  return request(`/api/v1/entries/${entryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteEntry(entryId: string) {
  return request(`/api/v1/entries/${entryId}`, {
    method: "DELETE"
  });
}

export function suggestEntryTags(payload: EntryTagSuggestionRequest & { signal?: AbortSignal }): Promise<EntryTagSuggestionResponse> {
  const { signal, ...body } = payload;
  return request<EntryTagSuggestionResponse>("/api/v1/entries/tag-suggestion", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}
