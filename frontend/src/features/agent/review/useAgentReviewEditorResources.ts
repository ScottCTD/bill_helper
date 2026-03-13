/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentReviewEditorResources` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/review/useAgentReviewEditorResources.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentReviewEditorResources`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getReconciliation, getRuntimeSettings, listCurrencies, listEntities, listSnapshots, listTags } from "../../../lib/api";
import { queryKeys } from "../../../lib/queryKeys";
import type { Currency, Entity, Snapshot, Tag } from "../../../lib/types";
import { buildSnapshotDeletionImpact, findSnapshotNeighbors } from "../../accounts/helpers";
import type { ThreadReviewItem } from "./model";
import { asRecord } from "./modalHelpers";

export interface SnapshotReviewContext {
  accountId: string | null;
  accountName: string | null;
  currencyCode: string | null;
  previousSnapshot: Snapshot | null;
  nextSnapshot: Snapshot | null;
  impactLines: string[];
  reconciliationSummary: string | null;
  loadError: string | null;
}

export interface ReviewEditorResources {
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  defaultCurrencyCode: string;
  editorLoadError: string | null;
  entityCategoryOptions: string[];
  snapshotReviewContext: SnapshotReviewContext;
  tagTypeOptions: string[];
}

function snapshotAccountId(activeReviewItem: ThreadReviewItem | null): string | null {
  if (!activeReviewItem) {
    return null;
  }
  if (activeReviewItem.item.change_type !== "create_snapshot" && activeReviewItem.item.change_type !== "delete_snapshot") {
    return null;
  }
  const payload = asRecord(activeReviewItem.item.payload_json);
  return typeof payload.account_id === "string" ? payload.account_id : null;
}

function orderedSnapshots(snapshots: Snapshot[]): Snapshot[] {
  return [...snapshots].sort((left, right) => {
    if (left.snapshot_at !== right.snapshot_at) {
      return left.snapshot_at.localeCompare(right.snapshot_at);
    }
    return left.created_at.localeCompare(right.created_at);
  });
}

function findCreateSnapshotNeighbors(snapshots: Snapshot[], snapshotAt: string): { previous: Snapshot | null; next: Snapshot | null } {
  const ordered = orderedSnapshots(snapshots);
  let previous: Snapshot | null = null;
  let next: Snapshot | null = null;
  for (const snapshot of ordered) {
    if (snapshot.snapshot_at < snapshotAt) {
      previous = snapshot;
      continue;
    }
    if (snapshot.snapshot_at > snapshotAt) {
      next = snapshot;
      break;
    }
  }
  return { previous, next };
}

export function useAgentReviewEditorResources(open: boolean, activeReviewItem: ThreadReviewItem | null): ReviewEditorResources {
  const runtimeSettingsQuery = useQuery({
    queryKey: queryKeys.settings.runtime,
    queryFn: getRuntimeSettings,
    enabled: open
  });
  const entitiesQuery = useQuery({
    queryKey: queryKeys.properties.entities,
    queryFn: listEntities,
    enabled: open
  });
  const tagsQuery = useQuery({
    queryKey: queryKeys.properties.tags,
    queryFn: listTags,
    enabled: open
  });
  const currenciesQuery = useQuery({
    queryKey: queryKeys.properties.currencies,
    queryFn: listCurrencies,
    enabled: open
  });

  const activeSnapshotAccountId = snapshotAccountId(activeReviewItem);
  const snapshotListQuery = useQuery({
    queryKey: queryKeys.accounts.snapshots(activeSnapshotAccountId ?? ""),
    queryFn: () => listSnapshots(activeSnapshotAccountId ?? ""),
    enabled: open && Boolean(activeSnapshotAccountId)
  });
  const snapshotReconciliationQuery = useQuery({
    queryKey: queryKeys.accounts.reconciliation(activeSnapshotAccountId ?? ""),
    queryFn: () => getReconciliation(activeSnapshotAccountId ?? ""),
    enabled: open && Boolean(activeSnapshotAccountId)
  });

  return useMemo<ReviewEditorResources>(() => {
    const defaultCurrencyCode = runtimeSettingsQuery.data?.default_currency_code ?? "USD";
    const editorLoadError = [runtimeSettingsQuery, entitiesQuery, tagsQuery, currenciesQuery]
      .map((query) => (query.isError ? (query.error as Error).message : null))
      .find((message): message is string => Boolean(message)) ?? null;
    const tagTypeOptions = Array.from(
      new Set(
        (tagsQuery.data ?? [])
          .map((tag) => tag.type?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));
    const entityCategoryOptions = Array.from(
      new Set(
        (entitiesQuery.data ?? [])
          .map((entity) => entity.category?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));

    const payload = asRecord(activeReviewItem?.item.payload_json);
    const accountName = typeof payload.account_name === "string" ? payload.account_name : null;
    const currencyCode = typeof payload.currency_code === "string" ? payload.currency_code : null;
    const snapshots = snapshotListQuery.data ?? [];
    let previousSnapshot: Snapshot | null = null;
    let nextSnapshot: Snapshot | null = null;
    let impactLines: string[] = [];

    if (activeReviewItem?.item.change_type === "create_snapshot") {
      const snapshotAt = typeof payload.snapshot_at === "string" ? payload.snapshot_at : "";
      const neighbors = findCreateSnapshotNeighbors(snapshots, snapshotAt);
      previousSnapshot = neighbors.previous;
      nextSnapshot = neighbors.next;
    }

    if (activeReviewItem?.item.change_type === "delete_snapshot") {
      const target = asRecord(payload.target);
      const snapshotId = typeof payload.snapshot_id === "string" ? payload.snapshot_id : "";
      const neighbors = findSnapshotNeighbors(snapshots, snapshotId);
      previousSnapshot = neighbors?.previous ?? null;
      nextSnapshot = neighbors?.next ?? null;
      impactLines = snapshotId ? buildSnapshotDeletionImpact(snapshots, snapshotId) : [];
    }

    const reconciliationSummary = snapshotReconciliationQuery.data
      ? (() => {
          const closedIntervals = snapshotReconciliationQuery.data.intervals.filter((interval) => !interval.is_open);
          const openInterval = snapshotReconciliationQuery.data.intervals.find((interval) => interval.is_open) ?? null;
          return `${closedIntervals.length} closed interval(s), ${openInterval ? "open tracked change available" : "no open interval"}`;
        })()
      : null;

    return {
      currencies: currenciesQuery.data ?? [],
      defaultCurrencyCode,
      editorLoadError,
      entities: entitiesQuery.data ?? [],
      entityCategoryOptions,
      snapshotReviewContext: {
        accountId: activeSnapshotAccountId,
        accountName,
        currencyCode,
        previousSnapshot,
        nextSnapshot,
        impactLines,
        reconciliationSummary,
        loadError:
          (snapshotListQuery.isError ? (snapshotListQuery.error as Error).message : null) ??
          (snapshotReconciliationQuery.isError ? (snapshotReconciliationQuery.error as Error).message : null)
      },
      tags: tagsQuery.data ?? [],
      tagTypeOptions
    };
  }, [
    activeReviewItem,
    activeSnapshotAccountId,
    currenciesQuery,
    entitiesQuery,
    runtimeSettingsQuery,
    snapshotListQuery,
    snapshotReconciliationQuery,
    tagsQuery
  ]);
}
