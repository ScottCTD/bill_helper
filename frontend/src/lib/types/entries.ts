/**
 * CALLING SPEC:
 * - Purpose: define entry and tag-suggestion contracts for the frontend.
 * - Inputs: frontend modules that list, edit, and classify ledger entries.
 * - Outputs: entry-domain interfaces and request payload types.
 * - Side effects: type declarations only.
 */

import type { EntryTag } from "./catalogs";
import type { EntryKind, GroupMemberRole, GroupType } from "./core";

export interface EntryGroupRef {
  id: string;
  name: string;
  group_type: GroupType;
}

export interface Entry {
  id: string;
  account_id: string | null;
  kind: EntryKind;
  occurred_at: string;
  name: string;
  amount_minor: number;
  currency_code: string;
  from_entity_id: string | null;
  to_entity_id: string | null;
  owner_user_id: string;
  from_entity: string | null;
  from_entity_missing: boolean;
  to_entity: string | null;
  to_entity_missing: boolean;
  owner: string | null;
  markdown_body: string | null;
  created_at: string;
  updated_at: string;
  tags: EntryTag[];
  direct_group: EntryGroupRef | null;
  direct_group_member_role: GroupMemberRole | null;
  group_path: EntryGroupRef[];
}

export interface EntryDetail extends Entry {}

export interface EntryListResponse {
  items: Entry[];
  total: number;
  limit: number;
  offset: number;
}

export interface EntryTagSuggestionRequest {
  entry_id?: string | null;
  kind: EntryKind;
  occurred_at: string;
  currency_code: string;
  amount_minor?: number | null;
  name?: string | null;
  from_entity_id?: string | null;
  from_entity?: string | null;
  to_entity_id?: string | null;
  to_entity?: string | null;
  owner_user_id?: string | null;
  markdown_body?: string | null;
  current_tags: string[];
}

export interface EntryTagSuggestionResponse {
  suggested_tags: string[];
}
