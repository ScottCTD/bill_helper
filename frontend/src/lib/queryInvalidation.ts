import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "./queryKeys";

const ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category";
const TAG_TYPE_TAXONOMY_KEY = "tag_type";

export function invalidateEntryReadModels(queryClient: QueryClient, entryId?: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.groups.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.tags });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.entities });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.users });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.currencies });
  if (entryId) {
    queryClient.invalidateQueries({ queryKey: queryKeys.entries.detail(entryId) });
    return;
  }
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.detailRoot });
}

export function invalidateGroupReadModels(queryClient: QueryClient, entryId?: string, groupId?: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.groups.all });
  if (groupId) {
    queryClient.invalidateQueries({ queryKey: queryKeys.groups.detail(groupId) });
  }
  if (entryId) {
    queryClient.invalidateQueries({ queryKey: queryKeys.entries.detail(entryId) });
    return;
  }
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.detailRoot });
}

export const invalidateEntryLinkReadModels = invalidateGroupReadModels;

export function invalidateAgentThreadData(queryClient: QueryClient, threadId?: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.agent.threads });
  if (threadId) {
    queryClient.invalidateQueries({ queryKey: queryKeys.agent.thread(threadId) });
    return;
  }
  queryClient.invalidateQueries({ queryKey: queryKeys.agent.threadRoot });
}

export function invalidateRuntimeSettingsReadModels(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.settings.runtime });
  queryClient.invalidateQueries({ queryKey: queryKeys.agent.threads });
  queryClient.invalidateQueries({ queryKey: queryKeys.agent.threadRoot });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.users });
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
}

export function invalidateAccountReadModels(queryClient: QueryClient, accountId?: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.reconciliationRoot });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.snapshotsRoot });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.users });
  if (accountId) {
    queryClient.invalidateQueries({ queryKey: queryKeys.accounts.reconciliation(accountId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.accounts.snapshots(accountId) });
  }
}

export function invalidateEntityReadModels(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.entities });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.taxonomyTerms(ENTITY_CATEGORY_TAXONOMY_KEY) });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
}

export function invalidateTagReadModels(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.tags });
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.taxonomyTerms(TAG_TYPE_TAXONOMY_KEY) });
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
}

export function invalidateUserReadModels(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.users });
  queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
}

export function invalidateTaxonomyReadModels(queryClient: QueryClient, taxonomyKey?: string): void {
  queryClient.invalidateQueries({ queryKey: queryKeys.properties.taxonomies });
  if (taxonomyKey) {
    queryClient.invalidateQueries({ queryKey: queryKeys.properties.taxonomyTerms(taxonomyKey) });
  } else {
    queryClient.invalidateQueries({ queryKey: queryKeys.properties.taxonomyTermsRoot });
  }

  if (taxonomyKey === ENTITY_CATEGORY_TAXONOMY_KEY) {
    queryClient.invalidateQueries({ queryKey: queryKeys.properties.entities });
    queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
    return;
  }

  if (taxonomyKey === TAG_TYPE_TAXONOMY_KEY) {
    queryClient.invalidateQueries({ queryKey: queryKeys.properties.tags });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    queryClient.invalidateQueries({ queryKey: queryKeys.entries.all });
  }
}
