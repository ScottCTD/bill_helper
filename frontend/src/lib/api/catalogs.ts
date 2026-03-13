/**
 * CALLING SPEC:
 * - Purpose: expose catalog, entity, tag, user, currency, and taxonomy API calls for the frontend.
 * - Inputs: catalog resource ids and mutation payloads.
 * - Outputs: typed catalog resources or empty success responses.
 * - Side effects: HTTP requests only.
 */

import type { Currency, Entity, Tag, Taxonomy, TaxonomyTerm, User } from "../types";
import { request } from "./core";

export function listEntities(): Promise<Entity[]> {
  return request<Entity[]>("/api/v1/entities");
}

export function createEntity(payload: { name: string; category?: string | null }): Promise<Entity> {
  return request<Entity>("/api/v1/entities", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateEntity(entityId: string, payload: { name?: string; category?: string | null }): Promise<Entity> {
  return request<Entity>(`/api/v1/entities/${entityId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteEntity(entityId: string): Promise<void> {
  return request<void>(`/api/v1/entities/${entityId}`, {
    method: "DELETE"
  });
}

export function listTags(): Promise<Tag[]> {
  return request<Tag[]>("/api/v1/tags");
}

export function createTag(payload: {
  name: string;
  color?: string | null;
  description?: string | null;
  type?: string | null;
}): Promise<Tag> {
  return request<Tag>("/api/v1/tags", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTag(
  tagId: number,
  payload: { name?: string; color?: string | null; description?: string | null; type?: string | null }
): Promise<Tag> {
  return request<Tag>(`/api/v1/tags/${tagId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteTag(tagId: number): Promise<void> {
  return request<void>(`/api/v1/tags/${tagId}`, {
    method: "DELETE"
  });
}

export function listUsers(): Promise<User[]> {
  return request<User[]>("/api/v1/users");
}

export function listCurrencies(): Promise<Currency[]> {
  return request<Currency[]>("/api/v1/currencies");
}

export function listTaxonomies(): Promise<Taxonomy[]> {
  return request<Taxonomy[]>("/api/v1/taxonomies");
}

export function listTaxonomyTerms(taxonomyKey: string): Promise<TaxonomyTerm[]> {
  return request<TaxonomyTerm[]>(`/api/v1/taxonomies/${taxonomyKey}/terms`);
}

export function createTaxonomyTerm(
  taxonomyKey: string,
  payload: { name: string; parent_term_id?: string | null; description?: string | null }
): Promise<TaxonomyTerm> {
  return request<TaxonomyTerm>(`/api/v1/taxonomies/${taxonomyKey}/terms`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTaxonomyTerm(
  taxonomyKey: string,
  termId: string,
  payload: { name?: string; description?: string | null }
): Promise<TaxonomyTerm> {
  return request<TaxonomyTerm>(`/api/v1/taxonomies/${taxonomyKey}/terms/${termId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}
