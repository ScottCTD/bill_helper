import { Badge } from "../../../components/ui/badge";
import { FormField } from "../../../components/ui/form-field";
import { Input } from "../../../components/ui/input";
import { NativeSelect } from "../../../components/ui/native-select";
import type { AgentChangeItem, Currency, Entity, Tag } from "../../../lib/types";
import { cn } from "../../../lib/utils";
import { type GroupMembershipReviewDraft, type GroupReviewDraft } from "./drafts";
import { buildEntryReviewDraftFromPreview, ReviewEntryEditor } from "./ReviewCatalogEditors";
import {
  asRecord,
  isUnresolvedDependency,
  proposalReferenceId,
  proposalReferenceLabel,
  resolveProposalItemByReference,
  statusBadgeClass
} from "./modalHelpers";
import { buildReviewItemSummary, type ThreadReviewItem } from "./model";

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
