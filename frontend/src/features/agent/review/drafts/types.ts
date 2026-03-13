/**
 * CALLING SPEC:
 * - Purpose: provide the `types` frontend module.
 * - Inputs: callers that import `frontend/src/features/agent/review/drafts/types.ts` and pass module-defined arguments or framework events.
 * - Outputs: typed helpers, contracts, or exports from `types`.
 * - Side effects: module-local frontend behavior only.
 */
import type { EntryKind, GroupMemberRole, GroupType } from "../../../../lib/types";

export type JsonRecord = Record<string, unknown>;

export interface EntryReviewDraft {
  kind: EntryKind;
  date: string;
  name: string;
  amountMajor: string;
  currencyCode: string;
  fromEntity: string;
  toEntity: string;
  tags: string[];
  markdownNotes: string;
}

export interface TagReviewDraft {
  name: string;
  type: string;
}

export interface AccountReviewDraft {
  name: string;
  currencyCode: string;
  isActive: boolean;
  markdownBody: string;
}

export interface SnapshotReviewDraft {
  snapshotAt: string;
  balanceMajor: string;
  note: string;
}

export interface EntityReviewDraft {
  name: string;
  category: string;
}

export interface GroupReviewDraft {
  name: string;
  groupType: GroupType;
}

export interface GroupMembershipReviewDraft {
  groupId: string;
  entryId: string;
  childGroupId: string;
  memberRole: GroupMemberRole | "";
}

export interface ReviewOverrideState {
  hasChanges: boolean;
  payloadOverride?: JsonRecord;
  validationError: string | null;
}
