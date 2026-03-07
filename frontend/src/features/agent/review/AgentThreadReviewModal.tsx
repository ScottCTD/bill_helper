import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { TagMultiSelect } from "../../../components/TagMultiSelect";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../../../components/ui/dialog";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { NativeSelect } from "../../../components/ui/native-select";
import { Textarea } from "../../../components/ui/textarea";
import { listCurrencies, listEntities, listTags, getRuntimeSettings } from "../../../lib/api";
import { queryKeys } from "../../../lib/queryKeys";
import type { AgentChangeItem, AgentChangeStatus, AgentRun, Currency, Entity, Tag } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import {
  buildEntityOverrideState,
  buildEntityReviewDraft,
  buildEntryOverrideState,
  buildEntryReviewDraft,
  buildTagOverrideState,
  buildTagReviewDraft,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type ReviewOverrideState,
  type TagReviewDraft,
  uniqueEntityOptionNames
} from "./drafts";
import { buildProposalDiff } from "./diff";
import { buildReviewItemSummary, buildThreadReviewItems, changeTypeLabel, isPendingReviewStatus, shortId, type ThreadReviewItem } from "./model";

interface AgentThreadReviewModalProps {
  open: boolean;
  runs: AgentRun[];
  onOpenChange: (open: boolean) => void;
  onApproveItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onRejectItem: (payload: { itemId: string }) => Promise<AgentChangeItem>;
  isBusy?: boolean;
}

interface BatchSummary {
  action: "approve" | "reject";
  succeeded: number;
  failed: number;
  failedItemIds: string[];
}

const KIND_OPTIONS = [
  { value: "EXPENSE", label: "Expense" },
  { value: "INCOME", label: "Income" },
  { value: "TRANSFER", label: "Transfer" }
] as const;

function statusBadgeClass(status: AgentChangeStatus): string {
  switch (status) {
    case "PENDING_REVIEW":
      return "agent-review-status-pending";
    case "APPROVED":
      return "agent-review-status-approved";
    case "APPLIED":
      return "agent-review-status-applied";
    case "REJECTED":
      return "agent-review-status-rejected";
    case "APPLY_FAILED":
      return "agent-review-status-failed";
    default:
      return "";
  }
}

function reviewModeClass(changeType: ThreadReviewItem["item"]["change_type"]): string {
  if (changeType.startsWith("create_")) {
    return "is-create";
  }
  if (changeType.startsWith("update_")) {
    return "is-update";
  }
  if (changeType.startsWith("delete_")) {
    return "is-delete";
  }
  return "is-snapshot";
}

function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Review action failed.";
}

function isTextInputTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(target.closest("input, textarea, select, [role='combobox']"));
}

function replaceItem(items: ThreadReviewItem[], updated: AgentChangeItem): ThreadReviewItem[] {
  return items.map((reviewItem) => {
    if (reviewItem.item.id !== updated.id) {
      return reviewItem;
    }
    return {
      ...reviewItem,
      item: updated
    };
  });
}

function findNextPendingItemId(items: ThreadReviewItem[], currentItemId: string | null): string | null {
  const pendingItems = items.filter((reviewItem) => isPendingReviewStatus(reviewItem.item.status));
  if (pendingItems.length === 0) {
    return null;
  }
  if (!currentItemId) {
    return pendingItems[0].item.id;
  }
  const currentIndex = pendingItems.findIndex((reviewItem) => reviewItem.item.id === currentItemId);
  if (currentIndex < 0) {
    return pendingItems[0].item.id;
  }
  return pendingItems[currentIndex + 1]?.item.id ?? pendingItems[currentIndex - 1]?.item.id ?? pendingItems[0].item.id;
}

function findRelativeItemId(items: ThreadReviewItem[], currentItemId: string | null, delta: number): string | null {
  if (items.length === 0) {
    return null;
  }
  if (!currentItemId) {
    return items[0].item.id;
  }
  const currentIndex = items.findIndex((reviewItem) => reviewItem.item.id === currentItemId);
  if (currentIndex < 0) {
    return items[0].item.id;
  }
  const nextIndex = Math.max(0, Math.min(items.length - 1, currentIndex + delta));
  return items[nextIndex]?.item.id ?? null;
}

function collectCurrencyOptions(currencies: Currency[], draft?: EntryReviewDraft): string[] {
  const codes = new Set(currencies.map((currency) => currency.code));
  if (draft?.currencyCode) {
    codes.add(draft.currencyCode.toUpperCase());
  }
  return Array.from(codes).sort();
}

function ReviewTocSection({
  title,
  items,
  activeItemId,
  onSelect
}: {
  title: string;
  items: ThreadReviewItem[];
  activeItemId: string | null;
  onSelect: (itemId: string) => void;
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="agent-review-toc-section" aria-label={title}>
      <div className="agent-review-toc-section-header">
        <h3>{title}</h3>
        <span>{items.length}</span>
      </div>
      <div className="agent-review-toc-list">
        {items.map((reviewItem) => {
          const isActive = reviewItem.item.id === activeItemId;
          return (
            <button
              key={reviewItem.item.id}
              type="button"
              className={cn(
                "agent-review-toc-item",
                reviewModeClass(reviewItem.item.change_type),
                isActive && "is-active",
                !isPendingReviewStatus(reviewItem.item.status) && "is-resolved"
              )}
              onClick={() => onSelect(reviewItem.item.id)}
            >
              <div className="agent-review-toc-item-copy">
                <span className="agent-review-toc-item-title">{buildReviewItemSummary(reviewItem.item)}</span>
                <span className="agent-review-toc-item-meta">
                  Run {reviewItem.runIndex} · {shortId(reviewItem.item.id)}
                </span>
              </div>
              <Badge variant="outline" className={cn("agent-review-status-badge", statusBadgeClass(reviewItem.item.status))}>
                {reviewItem.item.status}
              </Badge>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function ReviewEntryEditor({
  draft,
  currencies,
  entities,
  tags,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: EntryReviewDraft;
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: EntryReviewDraft) => void;
}) {
  const currencyOptions = useMemo(() => collectCurrencyOptions(currencies, draft), [currencies, draft]);
  const entityOptions = useMemo(
    () => uniqueEntityOptionNames(entities, [draft.fromEntity, draft.toEntity]),
    [draft.fromEntity, draft.toEntity, entities]
  );

  return (
    <div className="agent-review-editor-grid">
      <div className="agent-review-editor-row">
        <FormField label="Date">
          <Input
            type="date"
            value={draft.date}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, date: event.target.value })}
          />
        </FormField>
        <FormField label="Kind">
          <NativeSelect
            value={draft.kind}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, kind: event.target.value as EntryReviewDraft["kind"] })}
          >
            {KIND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </div>

      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>

      <div className="agent-review-editor-row">
        <FormField label="Amount">
          <Input
            type="number"
            min="0"
            step="0.01"
            value={draft.amountMajor}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, amountMajor: event.target.value })}
          />
        </FormField>
        <FormField label="Currency">
          <NativeSelect
            value={draft.currencyCode}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, currencyCode: event.target.value })}
          >
            {currencyOptions.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </div>

      <div className="agent-review-editor-row">
        <FormField label="From entity">
          <CreatableSingleSelect
            value={draft.fromEntity}
            options={entityOptions}
            disabled={isDisabled}
            ariaLabel="From entity"
            placeholder="Select or create entity..."
            onChange={(nextValue) => onDraftChange({ ...draft, fromEntity: nextValue })}
          />
        </FormField>
        <FormField label="To entity">
          <CreatableSingleSelect
            value={draft.toEntity}
            options={entityOptions}
            disabled={isDisabled}
            ariaLabel="To entity"
            placeholder="Select or create entity..."
            onChange={(nextValue) => onDraftChange({ ...draft, toEntity: nextValue })}
          />
        </FormField>
      </div>

      <FormField label="Tags">
        <TagMultiSelect
          value={draft.tags}
          options={tags}
          disabled={isDisabled}
          ariaLabel="Tags"
          onChange={(nextTags) => onDraftChange({ ...draft, tags: nextTags })}
        />
      </FormField>

      <FormField label="Notes" error={validationError}>
        <Textarea
          rows={5}
          value={draft.markdownNotes}
          disabled={isDisabled}
          onChange={(event) => onDraftChange({ ...draft, markdownNotes: event.target.value })}
        />
      </FormField>
    </div>
  );
}

function ReviewTagEditor({
  draft,
  typeOptions,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: TagReviewDraft;
  typeOptions: string[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: TagReviewDraft) => void;
}) {
  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>
      <FormField label="Type" error={validationError}>
        <CreatableSingleSelect
          value={draft.type}
          options={typeOptions}
          disabled={isDisabled}
          ariaLabel="Tag type"
          placeholder="Select or create type..."
          onChange={(nextValue) => onDraftChange({ ...draft, type: nextValue })}
        />
      </FormField>
    </div>
  );
}

function ReviewEntityEditor({
  draft,
  categoryOptions,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: EntityReviewDraft;
  categoryOptions: string[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: EntityReviewDraft) => void;
}) {
  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name">
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>
      <FormField label="Category" error={validationError}>
        <CreatableSingleSelect
          value={draft.category}
          options={categoryOptions}
          disabled={isDisabled}
          ariaLabel="Entity category"
          placeholder="Select or create category..."
          onChange={(nextValue) => onDraftChange({ ...draft, category: nextValue })}
        />
      </FormField>
    </div>
  );
}

export function AgentThreadReviewModal({
  open,
  runs,
  onOpenChange,
  onApproveItem,
  onRejectItem,
  isBusy = false
}: AgentThreadReviewModalProps) {
  const [items, setItems] = useState<ThreadReviewItem[]>([]);
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [entryDrafts, setEntryDrafts] = useState<Record<string, EntryReviewDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<string, TagReviewDraft>>({});
  const [entityDrafts, setEntityDrafts] = useState<Record<string, EntityReviewDraft>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<BatchSummary | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);

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
      setEntityDrafts({});
      setActionError(null);
      setActionNotice(null);
      setBatchSummary(null);
      setIsBatchRunning(false);
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

  const defaultCurrencyCode = runtimeSettingsQuery.data?.default_currency_code ?? "USD";
  const editorLoadError = [runtimeSettingsQuery, entitiesQuery, tagsQuery, currenciesQuery]
    .map((query) => (query.isError ? (query.error as Error).message : null))
    .find((message): message is string => Boolean(message));

  const tagTypeOptions = useMemo(
    () =>
      Array.from(
        new Set(
          (tagsQuery.data ?? [])
            .map((tag) => tag.type?.trim())
            .filter((value): value is string => Boolean(value))
        )
      ).sort((left, right) => left.localeCompare(right)),
    [tagsQuery.data]
  );
  const entityCategoryOptions = useMemo(
    () =>
      Array.from(
        new Set(
          (entitiesQuery.data ?? [])
            .map((entity) => entity.category?.trim())
            .filter((value): value is string => Boolean(value))
        )
      ).sort((left, right) => left.localeCompare(right)),
    [entitiesQuery.data]
  );

  function resolveOverrideState(reviewItem: ThreadReviewItem): ReviewOverrideState {
    if (reviewItem.item.change_type === "create_entry" || reviewItem.item.change_type === "update_entry") {
      return buildEntryOverrideState(
        reviewItem.item,
        entryDrafts[reviewItem.item.id] ?? buildEntryReviewDraft(reviewItem.item, defaultCurrencyCode),
        defaultCurrencyCode
      );
    }
    if (reviewItem.item.change_type === "create_tag" || reviewItem.item.change_type === "update_tag") {
      return buildTagOverrideState(reviewItem.item, tagDrafts[reviewItem.item.id] ?? buildTagReviewDraft(reviewItem.item));
    }
    if (reviewItem.item.change_type === "create_entity" || reviewItem.item.change_type === "update_entity") {
      return buildEntityOverrideState(
        reviewItem.item,
        entityDrafts[reviewItem.item.id] ?? buildEntityReviewDraft(reviewItem.item)
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
    try {
      const updated = await onRejectItem({ itemId: reviewItem.item.id });
      mergeUpdatedItem(updated);
      setActionError(null);
      return true;
    } catch (error) {
      setActionError(resolveErrorMessage(error));
      return false;
    }
  }

  async function handleApproveActive() {
    if (!activeReviewItem || !isPendingReviewStatus(activeReviewItem.item.status) || isBusy || isBatchRunning) {
      return;
    }
    setActionNotice(null);
    setBatchSummary(null);
    const succeeded = await approveReviewItem(activeReviewItem);
    if (succeeded) {
      setActionNotice(`Approved ${shortId(activeReviewItem.item.id)}.`);
      focusNextPending(activeReviewItem.item.id);
    }
  }

  async function handleRejectActive() {
    if (!activeReviewItem || !isPendingReviewStatus(activeReviewItem.item.status) || isBusy || isBatchRunning) {
      return;
    }
    setActionNotice(null);
    setBatchSummary(null);
    const succeeded = await rejectReviewItem(activeReviewItem);
    if (succeeded) {
      setActionNotice(`Rejected ${shortId(activeReviewItem.item.id)}.`);
      focusNextPending(activeReviewItem.item.id);
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

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
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
      if ((event.key === "a" || event.key === "A") && activeReviewItem && isPendingReviewStatus(activeReviewItem.item.status)) {
        event.preventDefault();
        void handleApproveActive();
        return;
      }
      if ((event.key === "r" || event.key === "R") && activeReviewItem && isPendingReviewStatus(activeReviewItem.item.status)) {
        event.preventDefault();
        void handleRejectActive();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeReviewItem, items, open]);

  if (!open) {
    return null;
  }

  const activeOverrideState = activeReviewItem ? resolveOverrideState(activeReviewItem) : { hasChanges: false, validationError: null };
  const reviewerOverride =
    activeReviewItem && activeOverrideState.hasChanges && activeOverrideState.payloadOverride
      ? activeOverrideState.payloadOverride
      : undefined;
  const diffPreview =
    activeReviewItem != null ? buildProposalDiff(activeReviewItem.item.change_type, activeReviewItem.item.payload_json, reviewerOverride) : null;
  const nextPendingItemId = findNextPendingItemId(items, activeItemId);
  const isActivePending = activeReviewItem ? isPendingReviewStatus(activeReviewItem.item.status) : false;
  const activeEntryDraft =
    activeReviewItem && (activeReviewItem.item.change_type === "create_entry" || activeReviewItem.item.change_type === "update_entry")
      ? entryDrafts[activeReviewItem.item.id] ?? buildEntryReviewDraft(activeReviewItem.item, defaultCurrencyCode)
      : null;
  const activeTagDraft =
    activeReviewItem && (activeReviewItem.item.change_type === "create_tag" || activeReviewItem.item.change_type === "update_tag")
      ? tagDrafts[activeReviewItem.item.id] ?? buildTagReviewDraft(activeReviewItem.item)
      : null;
  const activeEntityDraft =
    activeReviewItem && (activeReviewItem.item.change_type === "create_entity" || activeReviewItem.item.change_type === "update_entity")
      ? entityDrafts[activeReviewItem.item.id] ?? buildEntityReviewDraft(activeReviewItem.item)
      : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="agent-review-modal-content">
        <div className="agent-review-modal-layout">
          <DialogHeader className="agent-review-modal-header">
            <div className="agent-review-header-copy">
              <DialogTitle>Thread review</DialogTitle>
              <DialogDescription>
                {pendingCount} pending of {items.length} proposal{items.length === 1 ? "" : "s"}
              </DialogDescription>
            </div>
            <div className="agent-review-header-stats">
              <Badge variant="outline" className="agent-review-header-pill">
                Pending {pendingCount}
              </Badge>
              <Badge variant="outline" className="agent-review-header-pill">
                Reviewed {resolvedItems.length}
              </Badge>
            </div>
          </DialogHeader>

          <div className="agent-review-shell">
            <aside className="agent-review-sidebar">
              <div className="agent-review-sidebar-top">
                <div className="agent-review-sidebar-summary">
                  <p>Review proposals across the whole thread. Pending items stay first; resolved items remain available for audit.</p>
                </div>
                <div className="agent-review-sidebar-actions">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      void handleBatchAction("approve");
                    }}
                    disabled={pendingCount === 0 || isBatchRunning || isBusy}
                  >
                    {isBatchRunning ? "Working..." : "Approve All"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      void handleBatchAction("reject");
                    }}
                    disabled={pendingCount === 0 || isBatchRunning || isBusy}
                  >
                    {isBatchRunning ? "Working..." : "Reject All"}
                  </Button>
                </div>
              </div>

              <div className="agent-review-sidebar-scroll">
                <ReviewTocSection title="Pending" items={pendingItems} activeItemId={activeItemId} onSelect={setActiveItemId} />
                <ReviewTocSection title="Reviewed / Failed" items={resolvedItems} activeItemId={activeItemId} onSelect={setActiveItemId} />
              </div>
            </aside>

            <section className="agent-review-card-column">
              {!activeReviewItem || !diffPreview ? (
                <div className="agent-review-empty-card">
                  <p className="muted">{items.length === 0 ? "No proposals in this thread." : "Select a proposal to review."}</p>
                </div>
              ) : (
                <article
                  key={activeReviewItem.item.id}
                  className={cn("agent-review-card", reviewModeClass(activeReviewItem.item.change_type), "agent-review-card-animated")}
                >
                  <header className="agent-review-card-header">
                    <div className="agent-review-card-header-main">
                      <div className="agent-review-card-kicker">
                        <span>{changeTypeLabel(activeReviewItem.item.change_type)}</span>
                        <Badge variant="outline" className={cn("agent-review-status-badge", statusBadgeClass(activeReviewItem.item.status))}>
                          {activeReviewItem.item.status}
                        </Badge>
                      </div>
                      <h3>{buildReviewItemSummary(activeReviewItem.item)}</h3>
                      <p className="agent-review-card-run-meta">
                        Run {activeReviewItem.runIndex} · {prettyDateTime(activeReviewItem.runCreatedAt)} · Proposal {shortId(activeReviewItem.item.id)}
                      </p>
                    </div>
                  </header>

                  <div className="agent-review-card-body">
                    <section className="agent-review-panel-section">
                      <h4>Rationale</h4>
                      <p className="agent-review-rationale">{activeReviewItem.item.rationale_text || "No rationale provided."}</p>
                    </section>

                    <section className="agent-review-panel-section">
                      <div className="agent-review-section-heading">
                        <h4>{diffPreview.title}</h4>
                        <div className="agent-review-item-stats">
                          {diffPreview.stats.changed > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-changed">
                              Changed {diffPreview.stats.changed}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.added > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-added">
                              Added {diffPreview.stats.added}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.removed > 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat is-removed">
                              Removed {diffPreview.stats.removed}
                            </Badge>
                          ) : null}
                          {diffPreview.stats.changed === 0 && diffPreview.stats.added === 0 && diffPreview.stats.removed === 0 ? (
                            <Badge variant="outline" className="agent-review-diff-stat">
                              No deltas
                            </Badge>
                          ) : null}
                        </div>
                      </div>
                      {diffPreview.metadata.length > 0 ? (
                        <div className="agent-review-metadata" role="list" aria-label={`Metadata for proposal ${shortId(activeReviewItem.item.id)}`}>
                          {diffPreview.metadata.map((meta) => (
                            <div
                              key={`${activeReviewItem.item.id}:${meta.label}:${meta.value}`}
                              className={cn(
                                "agent-review-metadata-pill",
                                meta.tone === "warning" && "is-warning",
                                meta.tone === "danger" && "is-danger"
                              )}
                              role="listitem"
                            >
                              <span className="agent-review-metadata-label">{meta.label}</span>
                              <span className="agent-review-metadata-value">{meta.value}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div className="agent-review-diff" role="list" aria-label={`Diff for proposal ${shortId(activeReviewItem.item.id)}`}>
                        {diffPreview.lines.length === 0 ? <p className="muted">No changed fields.</p> : null}
                        {diffPreview.lines.map((line) => (
                          <div
                            key={`${activeReviewItem.item.id}:${line.sign}:${line.path}:${line.value}`}
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
                      {diffPreview.note ? <p className="agent-review-item-note muted">{diffPreview.note}</p> : null}
                    </section>

                    {editorLoadError ? (
                      <p className="error agent-review-editor-error">
                        Review editor options failed to load: {editorLoadError}
                      </p>
                    ) : null}

                    {isActivePending && activeEntryDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>Adjust the proposed entry before approval.</p>
                        </div>
                        <ReviewEntryEditor
                          draft={activeEntryDraft}
                          currencies={currenciesQuery.data ?? []}
                          entities={entitiesQuery.data ?? []}
                          tags={tagsQuery.data ?? []}
                          validationError={activeOverrideState.validationError}
                          isDisabled={isBusy || isBatchRunning}
                          onDraftChange={(nextDraft) =>
                            setEntryDrafts((current) => ({
                              ...current,
                              [activeReviewItem.item.id]: nextDraft
                            }))
                          }
                        />
                      </section>
                    ) : null}

                    {isActivePending && activeTagDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>Adjust the proposed tag before approval.</p>
                        </div>
                        <ReviewTagEditor
                          draft={activeTagDraft}
                          typeOptions={tagTypeOptions}
                          validationError={activeOverrideState.validationError}
                          isDisabled={isBusy || isBatchRunning}
                          onDraftChange={(nextDraft) =>
                            setTagDrafts((current) => ({
                              ...current,
                              [activeReviewItem.item.id]: nextDraft
                            }))
                          }
                        />
                      </section>
                    ) : null}

                    {isActivePending && activeEntityDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>Adjust the proposed entity before approval.</p>
                        </div>
                        <ReviewEntityEditor
                          draft={activeEntityDraft}
                          categoryOptions={entityCategoryOptions}
                          validationError={activeOverrideState.validationError}
                          isDisabled={isBusy || isBatchRunning}
                          onDraftChange={(nextDraft) =>
                            setEntityDrafts((current) => ({
                              ...current,
                              [activeReviewItem.item.id]: nextDraft
                            }))
                          }
                        />
                      </section>
                    ) : null}

                    {!isActivePending ? (
                      <section className="agent-review-panel-section">
                        <h4>Review outcome</h4>
                        {activeReviewItem.item.review_note ? <p className="agent-review-outcome-note">{activeReviewItem.item.review_note}</p> : null}
                        {activeReviewItem.item.applied_resource_type && activeReviewItem.item.applied_resource_id ? (
                          <p className="muted">
                            Applied resource: {activeReviewItem.item.applied_resource_type} #{activeReviewItem.item.applied_resource_id}
                          </p>
                        ) : null}
                        {!activeReviewItem.item.review_note &&
                        !activeReviewItem.item.applied_resource_type &&
                        activeReviewItem.item.status !== "PENDING_REVIEW" ? (
                          <p className="muted">No additional review note recorded.</p>
                        ) : null}
                      </section>
                    ) : null}
                  </div>

                  <footer className="agent-review-card-footer">
                    <div className="agent-review-card-nav">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveItemId(findRelativeItemId(items, activeItemId, -1))}
                        disabled={items.length <= 1}
                      >
                        Previous
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveItemId(findRelativeItemId(items, activeItemId, 1))}
                        disabled={items.length <= 1}
                      >
                        Next
                      </Button>
                      {isActivePending ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setActiveItemId(nextPendingItemId)}
                          disabled={!nextPendingItemId || nextPendingItemId === activeItemId}
                        >
                          Skip
                        </Button>
                      ) : null}
                    </div>

                    {isActivePending ? (
                      <div className="agent-review-card-actions">
                        <Button type="button" variant="outline" onClick={handleRejectActive} disabled={isBusy || isBatchRunning}>
                          Reject
                        </Button>
                        <Button type="button" onClick={handleApproveActive} disabled={isBusy || isBatchRunning}>
                          Approve
                        </Button>
                      </div>
                    ) : null}
                  </footer>
                </article>
              )}
            </section>
          </div>

          <footer className="agent-review-modal-footer">
            <p className="agent-review-footer-pending">
              Pending {pendingCount} of {items.length}
              {activeReviewItem ? ` · Run ${activeReviewItem.runIndex}` : ""}
            </p>
            {actionError ? <p className="error agent-review-footer-message">{actionError}</p> : null}
            {actionNotice ? <p className="muted agent-review-footer-message">{actionNotice}</p> : null}
            {batchSummary ? (
              <div className="agent-review-batch-summary">
                <p>
                  {batchSummary.action === "approve" ? "Approved" : "Rejected"} {batchSummary.succeeded} · Failed {batchSummary.failed}
                </p>
                {batchSummary.failedItemIds.length > 0 ? (
                  <div className="agent-review-failed-links">
                    {batchSummary.failedItemIds.map((itemId) => (
                      <Button key={itemId} type="button" variant="link" size="sm" onClick={() => setActiveItemId(itemId)}>
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
