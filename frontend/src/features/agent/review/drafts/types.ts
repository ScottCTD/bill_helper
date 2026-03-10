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
