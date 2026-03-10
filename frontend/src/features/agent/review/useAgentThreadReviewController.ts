import { useEffect, useEffectEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getRuntimeSettings, listCurrencies, listEntities, listTags } from "../../../lib/api";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentChangeItem, Currency, Entity, Tag } from "../../../lib/types";
import {
  buildAccountOverrideState,
  buildAccountReviewDraft,
  buildEntityOverrideState,
  buildEntityReviewDraft,
  buildEntryOverrideState,
  buildEntryReviewDraft,
  buildGroupMembershipOverrideState,
  buildGroupMembershipReviewDraft,
  buildGroupOverrideState,
  buildGroupReviewDraft,
  buildTagOverrideState,
  buildTagReviewDraft,
  type AccountReviewDraft,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type GroupMembershipReviewDraft,
  type GroupReviewDraft,
  type ReviewOverrideState,
  type TagReviewDraft
} from "./drafts";
import { buildProposalDiff } from "./diff";
import {
  findNextPendingItemId,
  findRelativeItemId,
  isEditableReviewStatus,
  isTextInputTarget,
  replaceItem,
  resolveErrorMessage
} from "./modalHelpers";
import { type BatchSummary, type AgentThreadReviewModalProps } from "./modalTypes";
import { buildThreadReviewItems, isPendingReviewStatus, shortId, type ThreadReviewItem } from "./model";

interface ReviewEditorResources {
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  defaultCurrencyCode: string;
  editorLoadError: string | null;
  entityCategoryOptions: string[];
  tagTypeOptions: string[];
}

interface ReviewActiveDrafts {
  activeAccountDraft: AccountReviewDraft | null;
  activeEntityDraft: EntityReviewDraft | null;
  activeEntryDraft: EntryReviewDraft | null;
  activeGroupDraft: GroupReviewDraft | null;
  activeGroupMembershipDraft: GroupMembershipReviewDraft | null;
  activeTagDraft: TagReviewDraft | null;
}

export function useAgentThreadReviewController({
  open,
  runs,
  onApproveItem,
  onRejectItem,
  onReopenItem,
  isBusy = false
}: AgentThreadReviewModalProps) {
  const [items, setItems] = useState<ThreadReviewItem[]>([]);
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [entryDrafts, setEntryDrafts] = useState<Record<string, EntryReviewDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<string, TagReviewDraft>>({});
  const [accountDrafts, setAccountDrafts] = useState<Record<string, AccountReviewDraft>>({});
  const [entityDrafts, setEntityDrafts] = useState<Record<string, EntityReviewDraft>>({});
  const [groupDrafts, setGroupDrafts] = useState<Record<string, GroupReviewDraft>>({});
  const [groupMembershipDrafts, setGroupMembershipDrafts] = useState<Record<string, GroupMembershipReviewDraft>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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

  const flattenedItems = useMemo(() => buildThreadReviewItems(runs), [runs]);

  useEffect(() => {
    if (!open) {
      setItems([]);
      setActiveItemId(null);
      setEntryDrafts({});
      setTagDrafts({});
      setAccountDrafts({});
      setEntityDrafts({});
      setGroupDrafts({});
      setGroupMembershipDrafts({});
      setActionError(null);
      setActionNotice(null);
      setBatchSummary(null);
      setIsBatchRunning(false);
      setIsSidebarCollapsed(false);
      return;
    }

    setItems(flattenedItems);
  }, [flattenedItems, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    if (items.length === 0) {
      setActiveItemId(null);
      return;
    }
    if (activeItemId && items.some((item) => item.item.id === activeItemId)) {
      return;
    }
    const nextItemId = items.find((item) => isPendingReviewStatus(item.item.status))?.item.id ?? items[0].item.id;
    setActiveItemId(nextItemId);
  }, [activeItemId, items, open]);

  const pendingItems = useMemo(() => items.filter((item) => isPendingReviewStatus(item.item.status)), [items]);
  const resolvedItems = useMemo(() => items.filter((item) => !isPendingReviewStatus(item.item.status)), [items]);
  const activeReviewItem = useMemo(() => items.find((item) => item.item.id === activeItemId) ?? null, [activeItemId, items]);
  const pendingCount = pendingItems.length;

  const editorResources = useMemo<ReviewEditorResources>(() => {
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
    return {
      currencies: currenciesQuery.data ?? [],
      defaultCurrencyCode,
      editorLoadError,
      entities: entitiesQuery.data ?? [],
      entityCategoryOptions,
      tags: tagsQuery.data ?? [],
      tagTypeOptions
    };
  }, [currenciesQuery, entitiesQuery, runtimeSettingsQuery, tagsQuery]);

  function resolveOverrideState(reviewItem: ThreadReviewItem): ReviewOverrideState {
    if (reviewItem.item.change_type === "create_entry" || reviewItem.item.change_type === "update_entry") {
      return buildEntryOverrideState(
        reviewItem.item,
        entryDrafts[reviewItem.item.id] ?? buildEntryReviewDraft(reviewItem.item, editorResources.defaultCurrencyCode),
        editorResources.defaultCurrencyCode
      );
    }
    if (reviewItem.item.change_type === "create_tag" || reviewItem.item.change_type === "update_tag") {
      return buildTagOverrideState(reviewItem.item, tagDrafts[reviewItem.item.id] ?? buildTagReviewDraft(reviewItem.item));
    }
    if (reviewItem.item.change_type === "create_account" || reviewItem.item.change_type === "update_account") {
      return buildAccountOverrideState(
        reviewItem.item,
        accountDrafts[reviewItem.item.id] ?? buildAccountReviewDraft(reviewItem.item)
      );
    }
    if (reviewItem.item.change_type === "create_entity" || reviewItem.item.change_type === "update_entity") {
      return buildEntityOverrideState(
        reviewItem.item,
        entityDrafts[reviewItem.item.id] ?? buildEntityReviewDraft(reviewItem.item)
      );
    }
    if (reviewItem.item.change_type === "create_group" || reviewItem.item.change_type === "update_group") {
      return buildGroupOverrideState(reviewItem.item, groupDrafts[reviewItem.item.id] ?? buildGroupReviewDraft(reviewItem.item));
    }
    if (reviewItem.item.change_type === "create_group_member") {
      return buildGroupMembershipOverrideState(
        reviewItem.item,
        groupMembershipDrafts[reviewItem.item.id] ?? buildGroupMembershipReviewDraft(reviewItem.item)
      );
    }
    return { hasChanges: false, validationError: null };
  }

  function mergeUpdatedItem(updated: AgentChangeItem) {
    setItems((current) => replaceItem(current, updated));
  }

  function focusNextPending(currentItemId: string) {
    const nextItemId = findNextPendingItemId(items, currentItemId);
    setActiveItemId(nextItemId ?? currentItemId);
  }

  async function approveReviewItem(reviewItem: ThreadReviewItem): Promise<boolean> {
    const overrideState = resolveOverrideState(reviewItem);
    if (overrideState.validationError) {
      setActionError(overrideState.validationError);
      setActiveItemId(reviewItem.item.id);
      return false;
    }

    try {
      const updated = await onApproveItem({
        itemId: reviewItem.item.id,
        payloadOverride: overrideState.hasChanges ? overrideState.payloadOverride : undefined
      });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      setActionError(resolveErrorMessage(error));
      return false;
    }
  }

  async function rejectReviewItem(reviewItem: ThreadReviewItem): Promise<boolean> {
    const overrideState = resolveOverrideState(reviewItem);
    if (overrideState.validationError) {
      setActionError(overrideState.validationError);
      setActiveItemId(reviewItem.item.id);
      return false;
    }
    try {
      const updated = await onRejectItem({
        itemId: reviewItem.item.id,
        payloadOverride: overrideState.hasChanges ? overrideState.payloadOverride : undefined
      });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      setActionError(resolveErrorMessage(error));
      return false;
    }
  }

  async function reopenReviewItem(reviewItem: ThreadReviewItem): Promise<boolean> {
    const overrideState = resolveOverrideState(reviewItem);
    if (overrideState.validationError) {
      setActionError(overrideState.validationError);
      setActiveItemId(reviewItem.item.id);
      return false;
    }
    try {
      const updated = await onReopenItem({
        itemId: reviewItem.item.id,
        payloadOverride: overrideState.hasChanges ? overrideState.payloadOverride : undefined
      });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      setActionError(resolveErrorMessage(error));
      return false;
    }
  }

  async function handleApproveActive() {
    if (!activeReviewItem || !isActiveEditable || isBusy || isBatchRunning) {
      return;
    }
    setActionNotice(null);
    setBatchSummary(null);
    const wasPending = isPendingReviewStatus(activeReviewItem.item.status);
    const succeeded = await approveReviewItem(activeReviewItem);
    if (succeeded) {
      setActionNotice(`Approved ${shortId(activeReviewItem.item.id)}.`);
      if (wasPending) {
        focusNextPending(activeReviewItem.item.id);
      } else {
        setActiveItemId(activeReviewItem.item.id);
      }
    }
  }

  async function handleRejectActive() {
    if (!activeReviewItem || !isActiveEditable || isBusy || isBatchRunning) {
      return;
    }
    setActionNotice(null);
    setBatchSummary(null);
    const wasPending = isPendingReviewStatus(activeReviewItem.item.status);
    const succeeded = await rejectReviewItem(activeReviewItem);
    if (succeeded) {
      setActionNotice(`Rejected ${shortId(activeReviewItem.item.id)}.`);
      if (wasPending) {
        focusNextPending(activeReviewItem.item.id);
      } else {
        setActiveItemId(activeReviewItem.item.id);
      }
    }
  }

  async function handleReopenActive() {
    if (!activeReviewItem || !isActiveEditable || isBusy || isBatchRunning) {
      return;
    }
    setActionNotice(null);
    setBatchSummary(null);
    const succeeded = await reopenReviewItem(activeReviewItem);
    if (succeeded) {
      setActionNotice(`Moved ${shortId(activeReviewItem.item.id)} to pending review.`);
      setActiveItemId(activeReviewItem.item.id);
    }
  }

  async function handleBatchAction(action: "approve" | "reject") {
    if (isBusy || isBatchRunning || pendingItems.length === 0) {
      return;
    }

    setActionError(null);
    setActionNotice(null);
    setBatchSummary(null);
    setIsBatchRunning(true);

    let succeeded = 0;
    let failed = 0;
    const failedItemIds: string[] = [];

    for (const reviewItem of pendingItems) {
      const currentReviewItem = items.find((item) => item.item.id === reviewItem.item.id) ?? reviewItem;
      const result = action === "approve" ? await approveReviewItem(currentReviewItem) : await rejectReviewItem(currentReviewItem);
      if (result) {
        succeeded += 1;
        continue;
      }
      failed += 1;
      failedItemIds.push(currentReviewItem.item.id);
    }

    setIsBatchRunning(false);
    setBatchSummary({
      action,
      succeeded,
      failed,
      failedItemIds
    });

    if (failedItemIds.length > 0) {
      setActiveItemId(failedItemIds[0]);
      setActionError(`${failed} proposal${failed === 1 ? "" : "s"} failed during ${action === "approve" ? "approval" : "rejection"}.`);
      return;
    }

    setActionNotice(`${action === "approve" ? "Approved" : "Rejected"} ${succeeded} proposal${succeeded === 1 ? "" : "s"}.`);
  }

  const handleKeyboardShortcut = useEffectEvent((event: KeyboardEvent) => {
    if (isTextInputTarget(event.target)) {
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setActiveItemId((current) => findRelativeItemId(items, current, -1));
      return;
    }
    if (event.key === "ArrowRight" || event.key === " ") {
      event.preventDefault();
      setActiveItemId((current) => findRelativeItemId(items, current, 1));
      return;
    }
    if ((event.key === "a" || event.key === "A") && activeReviewItem && isEditableReviewStatus(activeReviewItem.item.status)) {
      event.preventDefault();
      void handleApproveActive();
      return;
    }
    if ((event.key === "r" || event.key === "R") && activeReviewItem && isEditableReviewStatus(activeReviewItem.item.status)) {
      event.preventDefault();
      void handleRejectActive();
    }
  });

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      handleKeyboardShortcut(event);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyboardShortcut, open]);

  const activeOverrideState = activeReviewItem ? resolveOverrideState(activeReviewItem) : { hasChanges: false, validationError: null };
  const reviewerOverride =
    activeReviewItem && activeOverrideState.hasChanges && activeOverrideState.payloadOverride
      ? activeOverrideState.payloadOverride
      : undefined;
  const diffPreview =
    activeReviewItem != null ? buildProposalDiff(activeReviewItem.item.change_type, activeReviewItem.item.payload_json, reviewerOverride) : null;
  const nextPendingItemId = findNextPendingItemId(items, activeItemId);
  const isActivePending = activeReviewItem ? isPendingReviewStatus(activeReviewItem.item.status) : false;
  const isActiveEditable = activeReviewItem ? isEditableReviewStatus(activeReviewItem.item.status) : false;

  const activeDrafts = useMemo<ReviewActiveDrafts>(
    () => ({
      activeAccountDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_account" || activeReviewItem.item.change_type === "update_account")
          ? accountDrafts[activeReviewItem.item.id] ?? buildAccountReviewDraft(activeReviewItem.item)
          : null,
      activeEntityDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_entity" || activeReviewItem.item.change_type === "update_entity")
          ? entityDrafts[activeReviewItem.item.id] ?? buildEntityReviewDraft(activeReviewItem.item)
          : null,
      activeEntryDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_entry" || activeReviewItem.item.change_type === "update_entry")
          ? entryDrafts[activeReviewItem.item.id] ?? buildEntryReviewDraft(activeReviewItem.item, editorResources.defaultCurrencyCode)
          : null,
      activeGroupDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_group" || activeReviewItem.item.change_type === "update_group")
          ? groupDrafts[activeReviewItem.item.id] ?? buildGroupReviewDraft(activeReviewItem.item)
          : null,
      activeGroupMembershipDraft:
        activeReviewItem && activeReviewItem.item.change_type === "create_group_member"
          ? groupMembershipDrafts[activeReviewItem.item.id] ?? buildGroupMembershipReviewDraft(activeReviewItem.item)
          : null,
      activeTagDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_tag" || activeReviewItem.item.change_type === "update_tag")
          ? tagDrafts[activeReviewItem.item.id] ?? buildTagReviewDraft(activeReviewItem.item)
          : null
    }),
    [
      accountDrafts,
      activeReviewItem,
      editorResources.defaultCurrencyCode,
      entityDrafts,
      entryDrafts,
      groupDrafts,
      groupMembershipDrafts,
      tagDrafts
    ]
  );

  return {
    actionError,
    actionNotice,
    activeDrafts,
    activeItemId,
    activeOverrideState,
    activeReviewItem,
    batchSummary,
    diffPreview,
    editorResources,
    isActiveEditable,
    isActivePending,
    isBatchRunning,
    isSidebarCollapsed,
    items,
    nextPendingItemId,
    pendingCount,
    pendingItems,
    resolvedItems,
    selectRelativeItem(delta: number) {
      setActiveItemId((current) => findRelativeItemId(items, current, delta));
    },
    setActiveItemId,
    setActiveAccountDraft(nextDraft: AccountReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setAccountDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    setActiveEntityDraft(nextDraft: EntityReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setEntityDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    setActiveEntryDraft(nextDraft: EntryReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setEntryDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    setActiveGroupDraft(nextDraft: GroupReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setGroupDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    setActiveGroupMembershipDraft(nextDraft: GroupMembershipReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setGroupMembershipDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    setActiveTagDraft(nextDraft: TagReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setTagDrafts((current) => ({
        ...current,
        [activeReviewItem.item.id]: nextDraft
      }));
    },
    toggleSidebar() {
      setIsSidebarCollapsed((current) => !current);
    },
    handleApproveActive,
    handleBatchAction,
    handleRejectActive,
    handleReopenActive
  };
}
