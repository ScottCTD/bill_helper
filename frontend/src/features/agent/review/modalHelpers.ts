/**
 * CALLING SPEC:
 * - Purpose: provide the `modalHelpers` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/modalHelpers.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `modalHelpers`.
 * - Side effects: module-local frontend behavior only.
 */
import { AlertTriangle, Check, CheckCheck, type LucideIcon, X } from "lucide-react";

import type { AgentChangeItem, AgentChangeStatus, Currency } from "../../../lib/types";
import { isPendingReviewStatus, proposalTocGroupKey, shortId, type ProposalTocGroupKey, type ThreadReviewItem } from "./model";

export interface TocStatusIndicator {
  className: string;
  icon: LucideIcon;
  label: string;
}

interface TocProposalGroup {
  key: ProposalTocGroupKey;
  label: string;
  items: ThreadReviewItem[];
}

export const KIND_OPTIONS = [
  { value: "EXPENSE", label: "Expense" },
  { value: "INCOME", label: "Income" },
  { value: "TRANSFER", label: "Transfer" }
] as const;

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export function proposalReferenceId(record: Record<string, unknown>, idKey: string, proposalKey: string): string | null {
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

export function isUnresolvedDependency(proposal: ThreadReviewItem | null): boolean {
  return proposal != null && proposal.item.status !== "APPLIED";
}

export function proposalReferenceLabel(record: Record<string, unknown>, idKey: string, proposalKey: string): string {
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

export function statusBadgeClass(status: AgentChangeStatus): string {
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

export function reviewModeClass(changeType: ThreadReviewItem["item"]["change_type"]): string {
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

export function groupReviewItems(items: ThreadReviewItem[]): TocProposalGroup[] {
  const grouped: Record<ProposalTocGroupKey, ThreadReviewItem[]> = {
    entry: [],
    account: [],
    snapshot: [],
    entity: [],
    tag: [],
    group: [],
    group_member: []
  };
  for (const reviewItem of items) {
    grouped[proposalTocGroupKey(reviewItem.item.change_type)].push(reviewItem);
  }
  const groups: TocProposalGroup[] = [
    { key: "account", label: "Accounts", items: grouped.account },
    { key: "snapshot", label: "Snapshots", items: grouped.snapshot },
    { key: "entity", label: "Entities", items: grouped.entity },
    { key: "tag", label: "Tags", items: grouped.tag },
    { key: "group", label: "Groups", items: grouped.group },
    { key: "entry", label: "Entries", items: grouped.entry },
    { key: "group_member", label: "Group members", items: grouped.group_member }
  ];
  return groups.filter((group) => group.items.length > 0);
}

export function tocStatusIndicator(status: AgentChangeStatus): TocStatusIndicator | null {
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

export function prettyDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function resolveErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Review action failed.";
}

export function isTextInputTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return Boolean(target.closest("input, textarea, select, [role='combobox']"));
}

export function replaceItem(items: ThreadReviewItem[], updated: AgentChangeItem): ThreadReviewItem[] {
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

export function findNextPendingItemId(items: ThreadReviewItem[], currentItemId: string | null): string | null {
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

export function findRelativeItemId(items: ThreadReviewItem[], currentItemId: string | null, delta: number): string | null {
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

export function collectCurrencyOptions(currencies: Currency[], draftCurrencyCode?: string): string[] {
  const codes = new Set(currencies.map((currency) => currency.code));
  if (draftCurrencyCode) {
    codes.add(draftCurrencyCode.toUpperCase());
  }
  return Array.from(codes).sort();
}

export function resolveProposalItemByReference(items: ThreadReviewItem[], referenceId: string | null): ThreadReviewItem | null {
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

export function isEditableReviewStatus(status: AgentChangeStatus): boolean {
  return status !== "APPLIED";
}

export function buildReviewHeading(isPending: boolean, noun: string): string {
  return isPending ? `Adjust the proposed ${noun} before approval.` : "Adjust the proposal payload before changing review status.";
}
