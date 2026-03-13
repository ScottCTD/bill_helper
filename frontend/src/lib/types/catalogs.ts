/**
 * CALLING SPEC:
 * - Purpose: define catalog and reference-data types shared across the frontend.
 * - Inputs: frontend modules that render or mutate tags, entities, users, currencies, and taxonomies.
 * - Outputs: catalog entity interfaces.
 * - Side effects: type declarations only.
 */

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  description?: string | null;
  type?: string | null;
  entry_count?: number | null;
}

export interface EntryTag {
  id: number;
  name: string;
  color: string | null;
  description?: string | null;
  type?: string | null;
}

export interface Entity {
  id: string;
  name: string;
  category: string | null;
  is_account: boolean;
  from_count?: number | null;
  to_count?: number | null;
  account_count?: number | null;
  entry_count?: number | null;
  net_amount_minor?: number | null;
  net_amount_currency_code?: string | null;
  net_amount_mixed_currencies?: boolean;
}

export interface User {
  id: string;
  name: string;
  is_admin: boolean;
  is_current_user: boolean;
  account_count?: number | null;
  entry_count?: number | null;
}

export interface Currency {
  code: string;
  name: string;
  entry_count: number;
  is_placeholder: boolean;
}

export interface Taxonomy {
  id: string;
  key: string;
  applies_to: string;
  cardinality: string;
  display_name: string;
}

export interface TaxonomyTerm {
  id: string;
  taxonomy_id: string;
  name: string;
  normalized_name: string;
  parent_term_id: string | null;
  description?: string | null;
  usage_count: number;
}
