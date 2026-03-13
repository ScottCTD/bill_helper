/**
 * CALLING SPEC:
 * - Purpose: provide the `useAgentReviewDraftState` React hook or UI state helper.
 * - Inputs: callers that import `frontend/src/features/agent/review/useAgentReviewDraftState.ts` and pass module-defined arguments or framework events.
 * - Outputs: hooks and state helpers exported by `useAgentReviewDraftState`.
 * - Side effects: client-side state coordination and query wiring.
 */
import { useCallback, useMemo, useState } from "react";

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
  buildSnapshotOverrideState,
  buildSnapshotReviewDraft,
  buildTagOverrideState,
  buildTagReviewDraft,
  type AccountReviewDraft,
  type EntityReviewDraft,
  type EntryReviewDraft,
  type GroupMembershipReviewDraft,
  type GroupReviewDraft,
  type ReviewOverrideState,
  type SnapshotReviewDraft,
  type TagReviewDraft
} from "./drafts";
import type { ThreadReviewItem } from "./model";

export interface ReviewActiveDrafts {
  activeAccountDraft: AccountReviewDraft | null;
  activeEntityDraft: EntityReviewDraft | null;
  activeEntryDraft: EntryReviewDraft | null;
  activeGroupDraft: GroupReviewDraft | null;
  activeGroupMembershipDraft: GroupMembershipReviewDraft | null;
  activeSnapshotDraft: SnapshotReviewDraft | null;
  activeTagDraft: TagReviewDraft | null;
}

interface UseAgentReviewDraftStateArgs {
  activeReviewItem: ThreadReviewItem | null;
  defaultCurrencyCode: string;
}

export function useAgentReviewDraftState({
  activeReviewItem,
  defaultCurrencyCode
}: UseAgentReviewDraftStateArgs) {
  const [entryDrafts, setEntryDrafts] = useState<Record<string, EntryReviewDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<string, TagReviewDraft>>({});
  const [accountDrafts, setAccountDrafts] = useState<Record<string, AccountReviewDraft>>({});
  const [snapshotDrafts, setSnapshotDrafts] = useState<Record<string, SnapshotReviewDraft>>({});
  const [entityDrafts, setEntityDrafts] = useState<Record<string, EntityReviewDraft>>({});
  const [groupDrafts, setGroupDrafts] = useState<Record<string, GroupReviewDraft>>({});
  const [groupMembershipDrafts, setGroupMembershipDrafts] = useState<Record<string, GroupMembershipReviewDraft>>({});

  const clearReviewDrafts = useCallback(() => {
    setEntryDrafts({});
    setTagDrafts({});
    setAccountDrafts({});
    setSnapshotDrafts({});
    setEntityDrafts({});
    setGroupDrafts({});
    setGroupMembershipDrafts({});
  }, []);

  const resolveOverrideState = useCallback(
    (reviewItem: ThreadReviewItem): ReviewOverrideState => {
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
      if (reviewItem.item.change_type === "create_account" || reviewItem.item.change_type === "update_account") {
        return buildAccountOverrideState(
          reviewItem.item,
          accountDrafts[reviewItem.item.id] ?? buildAccountReviewDraft(reviewItem.item)
        );
      }
      if (reviewItem.item.change_type === "create_snapshot") {
        return buildSnapshotOverrideState(
          reviewItem.item,
          snapshotDrafts[reviewItem.item.id] ?? buildSnapshotReviewDraft(reviewItem.item)
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
    },
    [accountDrafts, defaultCurrencyCode, entityDrafts, entryDrafts, groupDrafts, groupMembershipDrafts, snapshotDrafts, tagDrafts]
  );

  const activeDrafts = useMemo<ReviewActiveDrafts>(
    () => ({
      activeAccountDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_account" || activeReviewItem.item.change_type === "update_account")
          ? accountDrafts[activeReviewItem.item.id] ?? buildAccountReviewDraft(activeReviewItem.item)
          : null,
      activeSnapshotDraft:
        activeReviewItem && activeReviewItem.item.change_type === "create_snapshot"
          ? snapshotDrafts[activeReviewItem.item.id] ?? buildSnapshotReviewDraft(activeReviewItem.item)
          : null,
      activeEntityDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_entity" || activeReviewItem.item.change_type === "update_entity")
          ? entityDrafts[activeReviewItem.item.id] ?? buildEntityReviewDraft(activeReviewItem.item)
          : null,
      activeEntryDraft:
        activeReviewItem && (activeReviewItem.item.change_type === "create_entry" || activeReviewItem.item.change_type === "update_entry")
          ? entryDrafts[activeReviewItem.item.id] ?? buildEntryReviewDraft(activeReviewItem.item, defaultCurrencyCode)
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
      defaultCurrencyCode,
      entityDrafts,
      entryDrafts,
      groupDrafts,
      groupMembershipDrafts,
      snapshotDrafts,
      tagDrafts
    ]
  );

  return {
    activeDrafts,
    clearReviewDrafts,
    resolveOverrideState,
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
    setActiveSnapshotDraft(nextDraft: SnapshotReviewDraft) {
      if (!activeReviewItem) {
        return;
      }
      setSnapshotDrafts((current) => ({
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
    }
  };
}
