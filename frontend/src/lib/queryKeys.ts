export type EntryListFiltersKey = {
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
};

export const queryKeys = {
  groups: {
    all: ["groups"] as const,
    list: ["groups", "list"] as const,
    detailRoot: ["groups", "detail"] as const,
    detail: (groupId: string) => ["groups", "detail", groupId] as const
  },
  accounts: {
    all: ["accounts"] as const,
    snapshotsRoot: ["snapshots"] as const,
    snapshots: (accountId: string) => ["snapshots", accountId] as const,
    reconciliationRoot: ["reconciliation"] as const,
    reconciliation: (accountId: string) => ["reconciliation", accountId] as const
  },
  entries: {
    all: ["entries"] as const,
    list: (filters: EntryListFiltersKey) => ["entries", "list", filters] as const,
    detailRoot: ["entry"] as const,
    detail: (entryId: string) => ["entry", entryId] as const
  },
  filterGroups: {
    all: ["filter-groups"] as const,
    list: ["filter-groups", "list"] as const
  },
  dashboard: {
    all: ["dashboard"] as const,
    timeline: ["dashboard", "timeline"] as const,
    month: (month: string) => ["dashboard", month] as const
  },
  settings: {
    runtime: ["settings", "runtime"] as const
  },
  properties: {
    entities: ["entities"] as const,
    users: ["users"] as const,
    tags: ["tags"] as const,
    currencies: ["currencies"] as const,
    taxonomies: ["taxonomies"] as const,
    taxonomyTermsRoot: ["taxonomy-terms"] as const,
    taxonomyTerms: (taxonomyKey: string) => ["taxonomy-terms", taxonomyKey] as const
  },
  agent: {
    threads: ["agent", "threads"] as const,
    threadRoot: ["agent", "thread"] as const,
    thread: (threadId: string) => ["agent", "thread", threadId] as const
  }
};
