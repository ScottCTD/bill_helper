import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Check, CheckCheck, PanelLeft, PanelLeftClose, type LucideIcon, X } from "lucide-react";

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
import type { AgentChangeItem, AgentChangeStatus, AgentChangeType, AgentRun, Currency, Entity, Tag } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import {
  buildGroupMembershipOverrideState,
  buildGroupMembershipReviewDraft,
  buildGroupOverrideState,
  buildGroupReviewDraft,
  buildEntityOverrideState,
  buildEntityReviewDraft,
  buildEntryOverrideState,
  buildEntryReviewDraftFromPreview,
  buildEntryReviewDraft,
  buildTagOverrideState,
  buildTagReviewDraft,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type GroupMembershipReviewDraft,
  type GroupReviewDraft,
  type ReviewOverrideState,
  type TagReviewDraft,
  uniqueEntityOptionNames
} from "./drafts";
import { buildProposalDiff } from "./diff";
import {
  buildReviewItemSummary,
  buildThreadReviewItems,
  changeTypeLabel,
  isPendingReviewStatus,
  proposalDomain,
  shortId,
  type ThreadReviewItem
} from "./model";

interface AgentThreadReviewModalProps {
  open: boolean;
  runs: AgentRun[];
  onOpenChange: (open: boolean) => void;
  onApproveItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onRejectItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  onReopenItem: (payload: { itemId: string; payloadOverride?: Record<string, unknown> }) => Promise<AgentChangeItem>;
  isBusy?: boolean;
}

interface BatchSummary {
  action: "approve" | "reject";
  succeeded: number;
  failed: number;
  failedItemIds: string[];
}

type TocProposalGroupKey = "entry" | "entity" | "tag" | "group";

interface TocProposalGroup {
  key: TocProposalGroupKey;
  label: string;
  items: ThreadReviewItem[];
}

interface TocStatusIndicator {
  className: string;
  icon: LucideIcon;
  label: string;
}

const KIND_OPTIONS = [
  { value: "EXPENSE", label: "Expense" },
  { value: "INCOME", label: "Income" },
  { value: "TRANSFER", label: "Transfer" }
] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function proposalReferenceId(record: Record<string, unknown>, idKey: string, proposalKey: string): string | null {
  const directId = record[idKey];
  if (typeof directId === "string" && directId.trim()) {
    return directId;
  }
  const proposalId = record[proposalKey];
  if (typeof proposalId === "string" && proposalId.trim()) {
    return proposalId;
  }
  return null;
}

function isUnresolvedDependency(proposal: ThreadReviewItem | null): boolean {
  return proposal != null && proposal.item.status !== "APPLIED";
}

function proposalReferenceLabel(record: Record<string, unknown>, idKey: string, proposalKey: string): string {
  const directId = record[idKey];
  if (typeof directId === "string" && directId.trim()) {
    return directId;
  }
  const proposalId = record[proposalKey];
  if (typeof proposalId === "string" && proposalId.trim()) {
    return `Pending ${shortId(proposalId)}`;
  }
  return "Unresolved";
}

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

function proposalGroupKey(changeType: AgentChangeType): TocProposalGroupKey {
  return proposalDomain(changeType);
}

function groupReviewItems(items: ThreadReviewItem[]): TocProposalGroup[] {
  const grouped: Record<TocProposalGroupKey, ThreadReviewItem[]> = {
    entry: [],
    entity: [],
    tag: [],
    group: []
  };
  for (const reviewItem of items) {
    grouped[proposalGroupKey(reviewItem.item.change_type)].push(reviewItem);
  }
  const groups: TocProposalGroup[] = [
    { key: "entry", label: "Entries", items: grouped.entry },
    { key: "group", label: "Groups", items: grouped.group },
    { key: "entity", label: "Entities", items: grouped.entity },
    { key: "tag", label: "Tags", items: grouped.tag }
  ];
  return groups.filter((group) => group.items.length > 0);
}

function tocStatusIndicator(status: AgentChangeStatus): TocStatusIndicator | null {
  switch (status) {
    case "APPROVED":
      return { className: "is-approved", icon: Check, label: "Approved" };
    case "APPLIED":
      return { className: "is-applied", icon: CheckCheck, label: "Applied" };
    case "REJECTED":
      return { className: "is-rejected", icon: X, label: "Rejected" };
    case "APPLY_FAILED":
      return { className: "is-failed", icon: AlertTriangle, label: "Apply failed" };
    default:
      return null;
  }
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

  const groups = groupReviewItems(items);

  return (
    <section className="agent-review-toc-section" aria-label={title}>
      <div className="agent-review-toc-section-header">
        <h3>{title}</h3>
        <span>{items.length}</span>
      </div>
      {groups.map((group) => (
        <div key={group.key} className="agent-review-toc-group">
          <div className="agent-review-toc-group-header">
            <h4>{group.label}</h4>
            <span>{group.items.length}</span>
          </div>
          <div className="agent-review-toc-list">
            {group.items.map((reviewItem) => {
              const isActive = reviewItem.item.id === activeItemId;
              const statusIndicator = tocStatusIndicator(reviewItem.item.status);
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
                  {statusIndicator ? (
                    <span
                      className={cn("agent-review-toc-status-indicator", statusIndicator.className)}
                      aria-label={statusIndicator.label}
                      title={statusIndicator.label}
                    >
                      <statusIndicator.icon className="h-3.5 w-3.5" aria-hidden />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ))}
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

function resolveProposalItemByReference(items: ThreadReviewItem[], referenceId: string | null): ThreadReviewItem | null {
  if (!referenceId) {
    return null;
  }
  const normalizedReference = referenceId.toLowerCase();
  const exactMatch = items.find((item) => item.item.id.toLowerCase() === normalizedReference);
  if (exactMatch) {
    return exactMatch;
  }
  return items.find((item) => item.item.id.toLowerCase().startsWith(normalizedReference)) ?? null;
}

function isEditableReviewStatus(status: AgentChangeStatus): boolean {
  return status !== "APPLIED";
}

function PendingDependencyChip({
  label,
  proposal
}: {
  label: string;
  proposal: ThreadReviewItem;
}) {
  return (
    <div className="agent-review-dependency-chip">
      <div className="agent-review-dependency-chip-copy">
        <span className="agent-review-dependency-chip-label">{label}</span>
        <span className="agent-review-dependency-chip-title">{buildReviewItemSummary(proposal.item)}</span>
      </div>
      <Badge variant="outline" className={cn("agent-review-status-badge", statusBadgeClass(proposal.item.status))}>
        {proposal.item.status}
      </Badge>
    </div>
  );
}

function ReviewGroupEditor({
  draft,
  isUpdate,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: GroupReviewDraft;
  isUpdate: boolean;
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: GroupReviewDraft) => void;
}) {
  return (
    <div className="agent-review-editor-grid">
      <FormField label="Group name" error={validationError}>
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>
      <FormField label="Group type">
        <NativeSelect
          value={draft.groupType}
          disabled={isDisabled || isUpdate}
          onChange={(event) => onDraftChange({ ...draft, groupType: event.target.value as GroupReviewDraft["groupType"] })}
        >
          <option value="BUNDLE">Bundle</option>
          <option value="SPLIT">Split</option>
          <option value="RECURRING">Recurring</option>
        </NativeSelect>
      </FormField>
    </div>
  );
}

function ReviewGroupMembershipEditor({
  item,
  draft,
  validationError,
  isDisabled,
  items,
  currencies,
  entities,
  tags,
  defaultCurrencyCode,
  onDraftChange
}: {
  item: AgentChangeItem;
  draft: GroupMembershipReviewDraft;
  validationError: string | null;
  isDisabled: boolean;
  items: ThreadReviewItem[];
  currencies: Currency[];
  entities: Entity[];
  tags: Tag[];
  defaultCurrencyCode: string;
  onDraftChange: (nextDraft: GroupMembershipReviewDraft) => void;
}) {
  const payload = item.payload_json;
  const groupRef = asRecord(payload.group_ref);
  const entryRef = asRecord(payload.entry_ref);
  const childGroupRef = asRecord(payload.child_group_ref);
  const groupPreview = asRecord(payload.group_preview);
  const memberPreview = asRecord(payload.member_preview);
  const isEntryTarget = Object.keys(entryRef).length > 0;
  const groupDependency = resolveProposalItemByReference(items, proposalReferenceId(groupRef, "group_id", "create_group_proposal_id"));
  const memberDependency = isEntryTarget
    ? resolveProposalItemByReference(items, proposalReferenceId(entryRef, "entry_id", "create_entry_proposal_id"))
    : resolveProposalItemByReference(items, proposalReferenceId(childGroupRef, "group_id", "create_group_proposal_id"));
  const groupType = typeof groupPreview.group_type === "string" ? groupPreview.group_type : "BUNDLE";
  const parentGroupName =
    typeof groupPreview.name === "string" && groupPreview.name.trim()
      ? groupPreview.name
      : proposalReferenceLabel(groupRef, "group_id", "create_group_proposal_id");
  const memberEntryDraft = isEntryTarget ? buildEntryReviewDraftFromPreview(memberPreview, defaultCurrencyCode) : null;
  const childGroupName =
    typeof memberPreview.name === "string" && memberPreview.name.trim()
      ? memberPreview.name
      : proposalReferenceLabel(childGroupRef, "group_id", "create_group_proposal_id");
  const childGroupType = typeof memberPreview.group_type === "string" ? memberPreview.group_type : "Unknown";
  const unresolvedGroupDependency = isUnresolvedDependency(groupDependency) ? groupDependency : null;
  const unresolvedMemberDependency = isUnresolvedDependency(memberDependency) ? memberDependency : null;

  return (
    <div className="agent-review-editor-grid">
      {(unresolvedGroupDependency || unresolvedMemberDependency) ? (
        <div className="agent-review-dependency-list">
          {unresolvedGroupDependency ? <PendingDependencyChip label="Parent group dependency" proposal={unresolvedGroupDependency} /> : null}
          {unresolvedMemberDependency ? (
            <PendingDependencyChip
              label={isEntryTarget ? "Entry dependency" : "Child group dependency"}
              proposal={unresolvedMemberDependency}
            />
          ) : null}
        </div>
      ) : null}

      <div className="agent-review-editor-row">
        <FormField label="Parent group">
          <Input value={parentGroupName} disabled />
        </FormField>
        <FormField label="Parent group type">
          <Input value={groupType} disabled />
        </FormField>
      </div>

      {isEntryTarget && memberEntryDraft ? (
        <div className="agent-review-member-preview">
          <div className="agent-review-section-heading">
            <h4>Member entry</h4>
            <p>Read-only snapshot of the entry being added to this group.</p>
          </div>
          <ReviewEntryEditor
            draft={memberEntryDraft}
            currencies={currencies}
            entities={entities}
            tags={tags}
            validationError={null}
            isDisabled
            onDraftChange={() => undefined}
          />
        </div>
      ) : null}

      {!isEntryTarget ? (
        <div className="agent-review-editor-row">
          <FormField label="Child group">
            <Input value={childGroupName} disabled />
          </FormField>
          <FormField label="Child group type">
            <Input value={childGroupType} disabled />
          </FormField>
        </div>
      ) : null}

      <div className="agent-review-editor-row">
        <FormField label="Member type">
          <Input value={isEntryTarget ? "Entry" : "Child group"} disabled />
        </FormField>
        <FormField
          label="Split role"
          error={validationError && groupType === "SPLIT" ? validationError : undefined}
          hint={groupType === "SPLIT" ? "Required for split-group adds." : `Parent group type: ${groupType}`}
        >
          <NativeSelect
            value={draft.memberRole}
            disabled={isDisabled || groupType !== "SPLIT"}
            onChange={(event) => onDraftChange({ ...draft, memberRole: event.target.value as GroupMembershipReviewDraft["memberRole"] })}
          >
            {groupType === "SPLIT" ? (
              <>
                <option value="">Select role</option>
                <option value="PARENT">Parent</option>
                <option value="CHILD">Child</option>
              </>
            ) : (
              <option value="">Not used</option>
            )}
          </NativeSelect>
        </FormField>
      </div>
    </div>
  );
}

export function AgentThreadReviewModal({
  open,
  runs,
  onOpenChange,
  onApproveItem,
  onRejectItem,
  onReopenItem,
  isBusy = false
}: AgentThreadReviewModalProps) {
  const [items, setItems] = useState<ThreadReviewItem[]>([]);
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [entryDrafts, setEntryDrafts] = useState<Record<string, EntryReviewDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<string, TagReviewDraft>>({});
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
    if (!activeReviewItem || !isEditableReviewStatus(activeReviewItem.item.status) || isBusy || isBatchRunning) {
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
    if (!activeReviewItem || !isEditableReviewStatus(activeReviewItem.item.status) || isBusy || isBatchRunning) {
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
      if ((event.key === "a" || event.key === "A") && activeReviewItem && isEditableReviewStatus(activeReviewItem.item.status)) {
        event.preventDefault();
        void handleApproveActive();
        return;
      }
      if ((event.key === "r" || event.key === "R") && activeReviewItem && isEditableReviewStatus(activeReviewItem.item.status)) {
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
  const isActiveEditable = activeReviewItem ? isEditableReviewStatus(activeReviewItem.item.status) : false;
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
  const activeGroupDraft =
    activeReviewItem && (activeReviewItem.item.change_type === "create_group" || activeReviewItem.item.change_type === "update_group")
      ? groupDrafts[activeReviewItem.item.id] ?? buildGroupReviewDraft(activeReviewItem.item)
      : null;
  const activeGroupMembershipDraft =
    activeReviewItem && activeReviewItem.item.change_type === "create_group_member"
      ? groupMembershipDrafts[activeReviewItem.item.id] ?? buildGroupMembershipReviewDraft(activeReviewItem.item)
      : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="agent-review-modal-content h-[96vh] w-[96vw] max-w-none overflow-hidden bg-card p-0 sm:w-[94vw] md:w-[92vw] lg:h-[94vh] lg:w-[88vw] xl:w-[78rem]">
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

          <div className={cn("agent-review-shell", isSidebarCollapsed && "is-sidebar-collapsed")}>
            <div className="agent-review-controls-bar">
              <div className="agent-review-controls-group">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="agent-review-sidebar-toggle"
                  onClick={() => setIsSidebarCollapsed((current) => !current)}
                  aria-controls="agent-review-sidebar"
                  aria-expanded={!isSidebarCollapsed}
                >
                  {isSidebarCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                  {isSidebarCollapsed ? "Show list" : "Hide list"}
                </Button>
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

              <div className="agent-review-controls-group agent-review-controls-nav">
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
                <div className="agent-review-controls-group agent-review-controls-actions">
                  <Button type="button" variant="outline" onClick={handleRejectActive} disabled={isBusy || isBatchRunning}>
                    Reject
                  </Button>
                  <Button type="button" onClick={handleApproveActive} disabled={isBusy || isBatchRunning}>
                    Approve
                  </Button>
                </div>
              ) : isActiveEditable ? (
                <div className="agent-review-controls-group agent-review-controls-actions">
                  {activeReviewItem?.item.status !== "PENDING_REVIEW" ? (
                    <Button type="button" variant="ghost" onClick={handleReopenActive} disabled={isBusy || isBatchRunning}>
                      Move to Pending
                    </Button>
                  ) : null}
                  <Button type="button" variant="outline" onClick={handleRejectActive} disabled={isBusy || isBatchRunning}>
                    {activeReviewItem?.item.status === "REJECTED" ? "Save Rejected" : "Reject"}
                  </Button>
                  <Button type="button" onClick={handleApproveActive} disabled={isBusy || isBatchRunning}>
                    {activeReviewItem?.item.status === "APPLY_FAILED" ? "Approve Again" : "Approve"}
                  </Button>
                </div>
              ) : null}
            </div>

            {!isSidebarCollapsed ? (
              <aside id="agent-review-sidebar" className="agent-review-sidebar">
                <div className="agent-review-sidebar-scroll">
                  <ReviewTocSection title="Pending" items={pendingItems} activeItemId={activeItemId} onSelect={setActiveItemId} />
                  <ReviewTocSection title="Reviewed / Failed" items={resolvedItems} activeItemId={activeItemId} onSelect={setActiveItemId} />
                </div>
              </aside>
            ) : null}

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

                    {isActiveEditable && activeEntryDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{isActivePending ? "Adjust the proposed entry before approval." : "Adjust the proposal payload before changing review status."}</p>
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

                    {isActiveEditable && activeTagDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{isActivePending ? "Adjust the proposed tag before approval." : "Adjust the proposal payload before changing review status."}</p>
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

                    {isActiveEditable && activeEntityDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>{isActivePending ? "Adjust the proposed entity before approval." : "Adjust the proposal payload before changing review status."}</p>
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

                    {isActiveEditable && activeGroupDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>
                            {isActivePending
                              ? activeReviewItem.item.change_type === "create_group"
                                ? "Adjust the proposed group before approval."
                                : "Rename the proposed group before approval."
                              : "Adjust the proposal payload before changing review status."}
                          </p>
                        </div>
                        <ReviewGroupEditor
                          draft={activeGroupDraft}
                          isUpdate={activeReviewItem.item.change_type === "update_group"}
                          validationError={activeOverrideState.validationError}
                          isDisabled={isBusy || isBatchRunning}
                          onDraftChange={(nextDraft) =>
                            setGroupDrafts((current) => ({
                              ...current,
                              [activeReviewItem.item.id]: nextDraft
                            }))
                          }
                        />
                      </section>
                    ) : null}

                    {isActiveEditable && activeGroupMembershipDraft ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Review edits</h4>
                          <p>
                            {isActivePending
                              ? "Review the group and member details before approval. Only split role is editable; unresolved proposal dependencies stay locked."
                              : "Review the group and member details before changing review status. Only split role is editable; unresolved proposal dependencies stay locked."}
                          </p>
                        </div>
                        <ReviewGroupMembershipEditor
                          item={activeReviewItem.item}
                          draft={activeGroupMembershipDraft}
                          validationError={activeOverrideState.validationError}
                          isDisabled={isBusy || isBatchRunning}
                          items={items}
                          currencies={currenciesQuery.data ?? []}
                          entities={entitiesQuery.data ?? []}
                          tags={tagsQuery.data ?? []}
                          defaultCurrencyCode={defaultCurrencyCode}
                          onDraftChange={(nextDraft) =>
                            setGroupMembershipDrafts((current) => ({
                              ...current,
                              [activeReviewItem.item.id]: nextDraft
                            }))
                          }
                        />
                      </section>
                    ) : null}

                    {isActiveEditable &&
                    (activeReviewItem.item.change_type === "delete_group" || activeReviewItem.item.change_type === "delete_group_member") ? (
                      <section className="agent-review-panel-section">
                        <div className="agent-review-section-heading">
                          <h4>Confirmation</h4>
                          <p>This proposal is confirmation-only. Approve to apply exactly what is shown above.</p>
                        </div>
                        <p className="agent-review-rationale">
                          {activeReviewItem.item.change_type === "delete_group"
                            ? "Delete-group proposals are not reviewer-editable in v1."
                            : "Remove-member proposals are not reviewer-editable in v1."}
                        </p>
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
