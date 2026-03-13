/**
 * CALLING SPEC:
 * - Purpose: re-export the public surface for `frontend/src/features/agent/review/diff`.
 * - Inputs: callers that import `frontend/src/features/agent/review/diff/index.ts` and pass module-defined arguments or framework events.
 * - Outputs: public exports for `frontend/src/features/agent/review/diff`.
 * - Side effects: module export wiring only.
 */
import type { AgentChangeType } from "../../../../lib/types";

import {
  asRecord,
  buildCreateDiff,
  buildDeleteDiff,
  buildRecordUpdateDiff,
  buildSnapshotLines,
  buildUpdateDiff,
  hasField,
  jsonRecordsAreEquivalent,
  pushMetadata,
  selectorSummary,
  withComputedStats
} from "./core";
import {
  buildAccountRecord,
  buildGroupMembershipDiff,
  buildGroupRecord,
  buildUpdateAccountAfterRecord,
  buildUpdateGroupAfterRecord,
  buildUpdateGroupBeforeRecord,
  previewName
} from "./domains";
import type { DiffMetadata, JsonRecord, ProposalDiff } from "./types";

export type { DiffLine, DiffLineSign, DiffMetadata, DiffStats, ProposalDiff } from "./types";
export { jsonRecordsAreEquivalent } from "./core";

export function buildProposalDiff(
  changeType: AgentChangeType,
  payload: JsonRecord,
  reviewerOverride?: JsonRecord
): ProposalDiff {
  const metadata: DiffMetadata[] = [];
  const effectivePatch =
    reviewerOverride && !jsonRecordsAreEquivalent(payload, reviewerOverride) ? asRecord(reviewerOverride.patch) : asRecord(payload.patch);

  if (hasField(payload, "name")) {
    pushMetadata(metadata, "Target", payload.name);
  }
  if (hasField(payload, "kind")) {
    pushMetadata(metadata, "Kind", payload.kind);
  }
  if (hasField(payload, "date")) {
    pushMetadata(metadata, "Date", payload.date);
  }

  const selector = asRecord(payload.selector);
  if (Object.keys(selector).length > 0) {
    pushMetadata(metadata, "Selector", selectorSummary(selector));
  }

  if (Object.keys(effectivePatch).length > 0) {
    pushMetadata(metadata, "Patch fields", Object.keys(effectivePatch).length);
  }

  const impactPreview = asRecord(payload.impact_preview);
  if (Object.keys(impactPreview).length > 0) {
    const entryCount = typeof impactPreview.entry_count === "number" ? impactPreview.entry_count : null;
    const accountCount = typeof impactPreview.account_count === "number" ? impactPreview.account_count : null;
    const snapshotCount = typeof impactPreview.snapshot_count === "number" ? impactPreview.snapshot_count : null;
    if (entryCount !== null) {
      pushMetadata(metadata, "Impacted entries", entryCount, entryCount > 0 ? "warning" : "neutral");
    }
    if (accountCount !== null) {
      pushMetadata(metadata, "Impacted accounts", accountCount, accountCount > 0 ? "warning" : "neutral");
    }
    if (snapshotCount !== null) {
      pushMetadata(metadata, "Snapshots", snapshotCount, snapshotCount > 0 ? "warning" : "neutral");
    }
  }

  switch (changeType) {
    case "create_account":
      return buildCreateDiff(buildAccountRecord(payload), metadata, reviewerOverride ? buildAccountRecord(reviewerOverride) : undefined);
    case "create_snapshot": {
      pushMetadata(metadata, "Account", payload.account_name);
      return buildCreateDiff(
        {
          snapshot_at: payload.snapshot_at,
          balance_minor: payload.balance_minor,
          note: payload.note ?? null
        },
        metadata,
        reviewerOverride
          ? {
              snapshot_at: reviewerOverride.snapshot_at,
              balance_minor: reviewerOverride.balance_minor,
              note: reviewerOverride.note ?? null
            }
          : undefined
      );
    }
    case "create_entry":
    case "create_tag":
    case "create_entity":
      return buildCreateDiff(payload, metadata, reviewerOverride);
    case "create_group":
      pushMetadata(metadata, "Group type", (reviewerOverride?.group_type as unknown) ?? payload.group_type);
      return buildCreateDiff(buildGroupRecord(payload), metadata, reviewerOverride ? buildGroupRecord(reviewerOverride) : undefined);
    case "update_account": {
      const { before, after, reviewerEdited } = buildUpdateAccountAfterRecord(payload, reviewerOverride);
      return buildRecordUpdateDiff(before, after, metadata, { reviewerEdited });
    }
    case "update_entry":
    case "update_tag":
    case "update_entity":
      return buildUpdateDiff(payload, metadata, reviewerOverride);
    case "update_group": {
      pushMetadata(metadata, "Group ID", payload.group_id);
      pushMetadata(metadata, "Group type", asRecord(payload.current).group_type);
      const { before, after, reviewerEdited } = buildUpdateGroupAfterRecord(payload, reviewerOverride);
      return buildRecordUpdateDiff(before, after, metadata, { reviewerEdited });
    }
    case "delete_entry":
      return buildDeleteDiff(payload, metadata, selector);
    case "delete_account":
      return buildDeleteDiff(payload, metadata, asRecord(impactPreview.current));
    case "delete_snapshot":
      pushMetadata(metadata, "Account", payload.account_name);
      pushMetadata(metadata, "Snapshot ID", payload.snapshot_id);
      return buildDeleteDiff(payload, metadata, asRecord(payload.target));
    case "delete_group":
      pushMetadata(metadata, "Group ID", payload.group_id);
      return buildDeleteDiff(payload, metadata, buildUpdateGroupBeforeRecord(payload));
    case "delete_tag":
    case "delete_entity": {
      const identity: JsonRecord = {};
      if (hasField(payload, "name")) {
        identity.name = payload.name;
      }
      return buildDeleteDiff(payload, metadata, identity);
    }
    case "create_group_member": {
      const parentGroup = asRecord(payload.group_preview);
      const memberPreview = asRecord(payload.member_preview);
      pushMetadata(metadata, "Group", previewName(parentGroup, "Unknown group"));
      pushMetadata(metadata, "Member", previewName(memberPreview, "Unknown member"));
      pushMetadata(metadata, "Group type", parentGroup.group_type);
      if (typeof payload.member_role === "string") {
        pushMetadata(metadata, "Split role", payload.member_role);
      }
      return buildGroupMembershipDiff(payload, metadata, "add", reviewerOverride);
    }
    case "delete_group_member": {
      const parentGroup = asRecord(payload.group_preview);
      const memberPreview = asRecord(payload.member_preview);
      pushMetadata(metadata, "Group", previewName(parentGroup, "Unknown group"));
      pushMetadata(metadata, "Member", previewName(memberPreview, "Unknown member"));
      pushMetadata(metadata, "Group type", parentGroup.group_type);
      return buildGroupMembershipDiff(payload, metadata, "remove");
    }
    default:
      return withComputedStats({
        mode: "snapshot",
        title: "Payload snapshot",
        lines: buildSnapshotLines(payload, "+"),
        metadata
      });
  }
}
