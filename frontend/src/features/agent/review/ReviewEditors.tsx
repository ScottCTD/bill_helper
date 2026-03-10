import { useMemo } from "react";

import { CreatableSingleSelect } from "../../../components/CreatableSingleSelect";
import { TagMultiSelect } from "../../../components/TagMultiSelect";
import { Badge } from "../../../components/ui/badge";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { NativeSelect } from "../../../components/ui/native-select";
import { Textarea } from "../../../components/ui/textarea";
import type { AgentChangeItem, AgentChangeStatus, Currency, Entity, Tag } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import {
  type AccountReviewDraft,
  buildEntryReviewDraftFromPreview,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type GroupMembershipReviewDraft,
  type GroupReviewDraft,
  type TagReviewDraft,
  uniqueEntityOptionNames
} from "./drafts";
import {
  asRecord,
  collectCurrencyOptions,
  groupReviewItems,
  isUnresolvedDependency,
  KIND_OPTIONS,
  proposalReferenceId,
  proposalReferenceLabel,
  resolveProposalItemByReference,
  reviewModeClass,
  statusBadgeClass,
  tocStatusIndicator
} from "./modalHelpers";
import { buildReviewItemSummary, isPendingReviewStatus, shortId, type ThreadReviewItem } from "./model";

export function ReviewTocSection({
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

export function ReviewEntryEditor({
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
  const currencyOptions = useMemo(
    () => collectCurrencyOptions(currencies, draft.currencyCode),
    [currencies, draft.currencyCode]
  );
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

export function ReviewTagEditor({
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

export function ReviewAccountEditor({
  draft,
  currencies,
  validationError,
  isDisabled,
  onDraftChange
}: {
  draft: AccountReviewDraft;
  currencies: Currency[];
  validationError: string | null;
  isDisabled: boolean;
  onDraftChange: (nextDraft: AccountReviewDraft) => void;
}) {
  const currencyOptions = useMemo(
    () => collectCurrencyOptions(currencies, draft.currencyCode),
    [currencies, draft.currencyCode]
  );
  const nameError = validationError === "Name is required." ? validationError : undefined;
  const currencyError = validationError === "Currency is required." ? validationError : undefined;

  return (
    <div className="agent-review-editor-grid">
      <FormField label="Name" error={nameError}>
        <Input value={draft.name} disabled={isDisabled} onChange={(event) => onDraftChange({ ...draft, name: event.target.value })} />
      </FormField>

      <div className="agent-review-editor-row">
        <FormField label="Currency" error={currencyError}>
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
        <FormField label="Status">
          <NativeSelect
            value={draft.isActive ? "active" : "inactive"}
            disabled={isDisabled}
            onChange={(event) => onDraftChange({ ...draft, isActive: event.target.value === "active" })}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </NativeSelect>
        </FormField>
      </div>

      <FormField label="Notes">
        <Textarea
          rows={5}
          value={draft.markdownBody}
          disabled={isDisabled}
          onChange={(event) => onDraftChange({ ...draft, markdownBody: event.target.value })}
        />
      </FormField>
    </div>
  );
}

export function ReviewEntityEditor({
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

export function PendingDependencyChip({
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

export function ReviewGroupEditor({
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

export function ReviewGroupMembershipEditor({
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
  const target = asRecord(payload.target);
  const entryRef = target.target_type === "entry" ? asRecord(target.entry_ref) : {};
  const childGroupRef = target.target_type === "child_group" ? asRecord(target.group_ref) : {};
  const groupPreview = asRecord(payload.group_preview);
  const memberPreview = asRecord(payload.member_preview);
  const isEntryTarget = target.target_type === "entry";
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
