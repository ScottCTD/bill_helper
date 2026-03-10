import { useEffect, useEffectEvent, useMemo, useState } from "react";

import type { AgentChangeItem } from "../../../lib/types";
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
import { useAgentReviewDraftState } from "./useAgentReviewDraftState";
import { useAgentReviewEditorResources } from "./useAgentReviewEditorResources";

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
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const flattenedItems = useMemo(() => buildThreadReviewItems(runs), [runs]);
  const editorResources = useAgentReviewEditorResources(open);
  const activeReviewItem = useMemo(() => items.find((item) => item.item.id === activeItemId) ?? null, [activeItemId, items]);
  const draftState = useAgentReviewDraftState({
    activeReviewItem,
    defaultCurrencyCode: editorResources.defaultCurrencyCode
  });
  const {
    activeDrafts,
    clearReviewDrafts,
    resolveOverrideState,
    setActiveAccountDraft,
    setActiveEntityDraft,
    setActiveEntryDraft,
    setActiveGroupDraft,
    setActiveGroupMembershipDraft,
    setActiveTagDraft
  } = draftState;

  useEffect(() => {
    if (!open) {
      setItems([]);
      setActiveItemId(null);
      setActionError(null);
      setActionNotice(null);
      setBatchSummary(null);
      setIsBatchRunning(false);
      setIsSidebarCollapsed(false);
      clearReviewDrafts();
      return;
    }

    setItems(flattenedItems);
  }, [clearReviewDrafts, flattenedItems, open]);

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
  const pendingCount = pendingItems.length;

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
    setActiveAccountDraft,
    setActiveEntityDraft,
    setActiveEntryDraft,
    setActiveGroupDraft,
    setActiveGroupMembershipDraft,
    setActiveTagDraft,
    toggleSidebar() {
      setIsSidebarCollapsed((current) => !current);
    },
    handleApproveActive,
    handleBatchAction,
    handleRejectActive,
    handleReopenActive
  };
}
