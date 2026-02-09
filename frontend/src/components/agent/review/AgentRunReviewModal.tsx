import { useEffect, useMemo, useRef, useState } from "react";

import type { AgentChangeItem, AgentChangeStatus, AgentRun } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import { Badge } from "../../ui/badge";
import { Button } from "../../ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../../ui/dialog";
import { Textarea } from "../../ui/textarea";
import { buildUnifiedDiffLines, jsonRecordsAreEquivalent } from "./diff";

interface AgentRunReviewModalProps {
  open: boolean;
  run: AgentRun | null;
  onOpenChange: (open: boolean) => void;
  onApproveItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onRejectItem: (payload: { itemId: string }) => Promise<AgentChangeItem>;
  isBusy?: boolean;
}

interface EntryOverrideState {
  parsed: Record<string, unknown> | null;
  parseError: string | null;
  hasChanges: boolean;
}

interface BatchSummary {
  applied: number;
  failed: number;
  failedItemIds: string[];
}

const CHANGE_TYPE_LABEL: Record<AgentChangeItem["change_type"], string> = {
  create_entry: "Entry",
  create_tag: "Tag",
  create_entity: "Entity"
};

const INTERSECTION_THRESHOLDS = [0, 0.2, 0.4, 0.6, 0.8, 1];

function asJsonText(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function statusBadgeClass(status: AgentChangeStatus): string {
  switch (status) {
    case "PENDING_REVIEW":
      return "agent-review-status-pending";
    case "APPLIED":
      return "agent-review-status-applied";
    case "REJECTED":
      return "agent-review-status-rejected";
    case "APPLY_FAILED":
      return "agent-review-status-failed";
    case "APPROVED":
      return "agent-review-status-approved";
    default:
      return "";
  }
}

function isPending(item: AgentChangeItem): boolean {
  return item.status === "PENDING_REVIEW";
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Review action failed.";
}

function buildInitialEntryDrafts(items: AgentChangeItem[], previous: Record<string, string>): Record<string, string> {
  const next: Record<string, string> = {};

  items.forEach((item) => {
    if (item.change_type !== "create_entry") {
      return;
    }
    next[item.id] = previous[item.id] ?? asJsonText(item.payload_json);
  });

  return next;
}

function replaceItemById(items: AgentChangeItem[], updated: AgentChangeItem): AgentChangeItem[] {
  return items.map((item) => {
    if (item.id === updated.id) {
      return updated;
    }
    return item;
  });
}

function findNextPendingAfter(items: AgentChangeItem[], itemId: string): AgentChangeItem | null {
  const startIndex = items.findIndex((item) => item.id === itemId);
  if (startIndex < 0) {
    return null;
  }

  for (let index = startIndex + 1; index < items.length; index += 1) {
    if (isPending(items[index])) {
      return items[index];
    }
  }

  return null;
}

export function AgentRunReviewModal({
  open,
  run,
  onOpenChange,
  onApproveItem,
  onRejectItem,
  isBusy = false
}: AgentRunReviewModalProps) {
  const [items, setItems] = useState<AgentChangeItem[]>([]);
  const [entryOverrideByItem, setEntryOverrideByItem] = useState<Record<string, string>>({});
  const [focusedItemId, setFocusedItemId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const blockRefs = useRef<Map<string, HTMLElement>>(new Map());

  useEffect(() => {
    if (!open || !run) {
      setItems([]);
      setEntryOverrideByItem({});
      setFocusedItemId(null);
      setActionError(null);
      setActionNotice(null);
      setBatchSummary(null);
      setIsBatchRunning(false);
      return;
    }

    setActionError(null);
    setActionNotice(null);
    setBatchSummary(null);
    setIsBatchRunning(false);
  }, [open, run?.id]);

  useEffect(() => {
    if (!open || !run) {
      return;
    }

    setItems(run.change_items);
    setEntryOverrideByItem((previous) => buildInitialEntryDrafts(run.change_items, previous));
  }, [open, run]);

  const entryOverrideStateByItem = useMemo(() => {
    const map = new Map<string, EntryOverrideState>();

    items.forEach((item) => {
      if (item.change_type !== "create_entry") {
        return;
      }
      const draft = entryOverrideByItem[item.id] ?? asJsonText(item.payload_json);
      try {
        const parsed = JSON.parse(draft) as Record<string, unknown>;
        map.set(item.id, {
          parsed,
          parseError: null,
          hasChanges: !jsonRecordsAreEquivalent(item.payload_json, parsed)
        });
      } catch (error) {
        map.set(item.id, {
          parsed: null,
          parseError: (error as Error).message,
          hasChanges: false
        });
      }
    });

    return map;
  }, [entryOverrideByItem, items]);

  const pendingItems = useMemo(() => items.filter(isPending), [items]);

  const focusedPendingItem = useMemo(() => {
    if (pendingItems.length === 0) {
      return null;
    }
    return pendingItems.find((item) => item.id === focusedItemId) ?? pendingItems[0];
  }, [focusedItemId, pendingItems]);

  useEffect(() => {
    if (pendingItems.length === 0) {
      setFocusedItemId(null);
      return;
    }
    if (!focusedItemId || !pendingItems.some((item) => item.id === focusedItemId)) {
      setFocusedItemId(pendingItems[0].id);
    }
  }, [focusedItemId, pendingItems]);

  useEffect(() => {
    if (!open || pendingItems.length === 0 || !scrollContainerRef.current) {
      return;
    }

    const root = scrollContainerRef.current;
    const ratiosById = new Map<string, number>();
    const pendingIds = new Set(pendingItems.map((item) => item.id));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const itemId = (entry.target as HTMLElement).dataset.itemId;
          if (!itemId) {
            return;
          }
          ratiosById.set(itemId, entry.intersectionRatio);
        });

        let bestItemId: string | null = null;
        let bestRatio = -1;

        pendingIds.forEach((itemId) => {
          const ratio = ratiosById.get(itemId) ?? 0;
          if (ratio > bestRatio) {
            bestRatio = ratio;
            bestItemId = itemId;
          }
        });

        if (bestItemId) {
          setFocusedItemId(bestItemId);
        }
      },
      {
        root,
        threshold: INTERSECTION_THRESHOLDS
      }
    );

    items.forEach((item) => {
      const block = blockRefs.current.get(item.id);
      if (block) {
        observer.observe(block);
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [items, open, pendingItems]);

  function setItemBlockRef(itemId: string, node: HTMLElement | null) {
    if (node) {
      blockRefs.current.set(itemId, node);
      return;
    }
    blockRefs.current.delete(itemId);
  }

  function scrollToItem(itemId: string, smooth = true) {
    const target = blockRefs.current.get(itemId);
    if (!target) {
      return;
    }
    target.scrollIntoView({
      behavior: smooth ? "smooth" : "auto",
      block: "start"
    });
  }

  function mergeUpdatedItem(updated: AgentChangeItem) {
    setItems((current) => replaceItemById(current, updated));
  }

  function markItemFailed(itemId: string, reason: string) {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId || item.status !== "PENDING_REVIEW") {
          return item;
        }
        return {
          ...item,
          status: "APPLY_FAILED",
          review_note: reason
        };
      })
    );
  }

  async function approveItem(item: AgentChangeItem): Promise<boolean> {
    const overrideState = entryOverrideStateByItem.get(item.id);

    let payloadOverride: Record<string, unknown> | undefined;
    if (item.change_type === "create_entry") {
      if (overrideState?.parseError) {
        setActionError(`Invalid JSON for ${shortId(item.id)}: ${overrideState.parseError}`);
        return false;
      }
      if (overrideState?.hasChanges && overrideState.parsed) {
        payloadOverride = overrideState.parsed;
      }
    }

    try {
      const updated = await onApproveItem({
        itemId: item.id,
        payloadOverride
      });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      const message = resolveErrorMessage(error);
      setActionError(message);
      markItemFailed(item.id, message);
      return false;
    }
  }

  async function rejectItem(item: AgentChangeItem): Promise<boolean> {
    try {
      const updated = await onRejectItem({ itemId: item.id });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      setActionError(resolveErrorMessage(error));
      return false;
    }
  }

  async function handleApproveFocused() {
    if (!focusedPendingItem || isBatchRunning || isBusy) {
      return;
    }

    setBatchSummary(null);
    setActionNotice(null);

    const approved = await approveItem(focusedPendingItem);
    if (approved) {
      setActionNotice(`Approved ${shortId(focusedPendingItem.id)}.`);
    }
  }

  async function handleRejectFocused() {
    if (!focusedPendingItem || isBatchRunning || isBusy) {
      return;
    }

    setBatchSummary(null);
    setActionNotice(null);

    const rejected = await rejectItem(focusedPendingItem);
    if (rejected) {
      setActionNotice(`Rejected ${shortId(focusedPendingItem.id)}.`);
    }
  }

  async function handleApproveAndNext() {
    if (!focusedPendingItem || isBatchRunning || isBusy) {
      return;
    }

    setBatchSummary(null);
    setActionNotice(null);

    const nextPendingItem = findNextPendingAfter(items, focusedPendingItem.id);
    const approved = await approveItem(focusedPendingItem);
    if (!approved) {
      return;
    }

    if (nextPendingItem) {
      setFocusedItemId(nextPendingItem.id);
      scrollToItem(nextPendingItem.id);
      setActionNotice(`Approved ${shortId(focusedPendingItem.id)}. Focus moved to ${shortId(nextPendingItem.id)}.`);
      return;
    }

    const remainingPending = items.filter((item) => isPending(item) && item.id !== focusedPendingItem.id).length;
    if (remainingPending === 0) {
      setActionNotice("All pending proposals are reviewed.");
      return;
    }

    setActionNotice("Reached end of this run. Remaining pending items are above.");
  }

  async function handleApproveAll() {
    if (isBatchRunning || isBusy) {
      return;
    }

    const queue = items.filter(isPending);
    if (queue.length === 0) {
      return;
    }

    const confirmText = `Approve all ${queue.length} pending proposal${queue.length === 1 ? "" : "s"} in this run?`;
    if (!window.confirm(confirmText)) {
      return;
    }

    setActionError(null);
    setActionNotice(null);
    setBatchSummary(null);
    setIsBatchRunning(true);

    let applied = 0;
    let failed = 0;
    const failedItemIds: string[] = [];

    for (const item of queue) {
      const overrideState = entryOverrideStateByItem.get(item.id);

      let payloadOverride: Record<string, unknown> | undefined;
      if (item.change_type === "create_entry") {
        if (overrideState?.parseError) {
          failed += 1;
          failedItemIds.push(item.id);
          markItemFailed(item.id, `Invalid JSON: ${overrideState.parseError}`);
          continue;
        }
        if (overrideState?.hasChanges && overrideState.parsed) {
          payloadOverride = overrideState.parsed;
        }
      }

      try {
        const updated = await onApproveItem({
          itemId: item.id,
          payloadOverride
        });
        mergeUpdatedItem(updated);
        applied += 1;
      } catch (error) {
        const message = resolveErrorMessage(error);
        failed += 1;
        failedItemIds.push(item.id);
        markItemFailed(item.id, message);
      }
    }

    setIsBatchRunning(false);
    setBatchSummary({
      applied,
      failed,
      failedItemIds
    });

    if (failedItemIds.length > 0) {
      setFocusedItemId(failedItemIds[0]);
      scrollToItem(failedItemIds[0]);
    }

    if (failed === 0) {
      setActionNotice(`Applied ${applied} proposal${applied === 1 ? "" : "s"}.`);
      return;
    }

    setActionError(`${failed} proposal${failed === 1 ? "" : "s"} failed while approving all.`);
  }

  if (!run) {
    return null;
  }

  const pendingCount = pendingItems.length;
  const totalCount = items.length;
  const focusedPendingOrdinal = focusedPendingItem
    ? pendingItems.findIndex((item) => item.id === focusedPendingItem.id) + 1
    : 0;
  const isActionDisabled = !focusedPendingItem || isBatchRunning || isBusy;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="agent-review-modal-content">
        <div className="agent-review-modal-layout">
          <DialogHeader className="agent-review-modal-header">
            <DialogTitle>Review proposed changes</DialogTitle>
            <DialogDescription>
              Run {shortId(run.id)} · {pendingCount} pending of {totalCount}
            </DialogDescription>
          </DialogHeader>

          <div className="agent-review-modal-scroll scroll-surface" ref={scrollContainerRef}>
            {items.length === 0 ? <p className="muted">No proposals in this run.</p> : null}

            {items.map((item, index) => {
              const overrideState = entryOverrideStateByItem.get(item.id);
              const reviewerOverride =
                item.change_type === "create_entry" && overrideState?.hasChanges && overrideState.parsed
                  ? overrideState.parsed
                  : undefined;
              const diffLines = buildUnifiedDiffLines(item.payload_json, reviewerOverride);
              const isFocused = item.status === "PENDING_REVIEW" && item.id === focusedPendingItem?.id;

              return (
                <article
                  key={item.id}
                  className={cn("agent-review-item", isFocused && "is-focused")}
                  data-item-id={item.id}
                  ref={(node) => setItemBlockRef(item.id, node)}
                  tabIndex={-1}
                >
                  <header className="agent-review-item-header">
                    <div className="agent-review-item-heading">
                      <h4>
                        {index + 1}. {CHANGE_TYPE_LABEL[item.change_type]} proposal
                      </h4>
                      <Badge variant="outline" className={cn("agent-review-status-badge", statusBadgeClass(item.status))}>
                        {item.status}
                      </Badge>
                    </div>
                    <p className="agent-review-item-id">#{shortId(item.id)}</p>
                  </header>

                  <p className="agent-review-item-rationale">{item.rationale_text || "No rationale provided."}</p>

                  <div className="agent-review-diff" role="list" aria-label={`Diff for proposal ${shortId(item.id)}`}>
                    {diffLines.length === 0 ? <p className="muted">No payload differences.</p> : null}
                    {diffLines.map((line) => (
                      <div
                        key={`${item.id}:${line.sign}:${line.path}:${line.value}`}
                        className={cn("agent-review-diff-line", line.sign === "+" ? "is-added" : "is-removed")}
                        role="listitem"
                      >
                        <span className="agent-review-diff-sign" aria-hidden>
                          {line.sign}
                        </span>
                        <span className="agent-review-diff-path">{line.path}</span>
                        <code className="agent-review-diff-value">{line.value}</code>
                      </div>
                    ))}
                  </div>

                  {item.change_type === "create_entry" && item.status === "PENDING_REVIEW" ? (
                    <label className="agent-entry-override">
                      Edit payload before approve (JSON)
                      <Textarea
                        value={entryOverrideByItem[item.id] ?? asJsonText(item.payload_json)}
                        onChange={(event) =>
                          setEntryOverrideByItem((state) => ({
                            ...state,
                            [item.id]: event.target.value
                          }))
                        }
                        rows={7}
                      />
                      {overrideState?.parseError ? <p className="error">Invalid JSON: {overrideState.parseError}</p> : null}
                    </label>
                  ) : null}

                  {item.status === "APPLY_FAILED" ? (
                    <p className="error">{item.review_note || "Apply failed. Check payload and retry."}</p>
                  ) : null}

                  {item.status !== "APPLY_FAILED" && item.review_note ? (
                    <p className="muted">Review note: {item.review_note}</p>
                  ) : null}

                  {item.applied_resource_type && item.applied_resource_id ? (
                    <p className="muted">
                      Applied resource: {item.applied_resource_type} #{item.applied_resource_id}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>

          <footer className="agent-review-modal-footer">
            <div className="agent-review-footer-actions">
              <Button type="button" variant="destructive" onClick={handleRejectFocused} disabled={isActionDisabled}>
                Reject
              </Button>
              <Button type="button" onClick={handleApproveFocused} disabled={isActionDisabled}>
                Approve
              </Button>
              <Button type="button" variant="secondary" onClick={handleApproveAndNext} disabled={isActionDisabled}>
                Approve &amp; Next
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleApproveAll}
                disabled={pendingCount === 0 || isBatchRunning || isBusy}
              >
                {isBatchRunning ? "Approving..." : "Approve All"}
              </Button>
            </div>

            <p className="agent-review-footer-pending">
              Pending {pendingCount} of {totalCount}
              {focusedPendingItem ? ` · Focus ${focusedPendingOrdinal}` : ""}
            </p>

            {actionError ? <p className="error agent-review-footer-message">{actionError}</p> : null}
            {actionNotice ? <p className="muted agent-review-footer-message">{actionNotice}</p> : null}

            {batchSummary ? (
              <div className="agent-review-batch-summary">
                <p>
                  Applied {batchSummary.applied} · Failed {batchSummary.failed}
                </p>
                {batchSummary.failedItemIds.length > 0 ? (
                  <div className="agent-review-failed-links">
                    {batchSummary.failedItemIds.map((itemId) => (
                      <Button
                        key={itemId}
                        type="button"
                        variant="link"
                        size="sm"
                        onClick={() => {
                          setFocusedItemId(itemId);
                          scrollToItem(itemId);
                        }}
                      >
                        Jump to {shortId(itemId)}
                      </Button>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </footer>
        </div>
      </DialogContent>
    </Dialog>
  );
}
