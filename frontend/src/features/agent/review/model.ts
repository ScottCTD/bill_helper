import type { AgentChangeItem, AgentChangeStatus, AgentChangeType, AgentRun } from "../../../lib/types";

export interface ThreadReviewItem {
  item: AgentChangeItem;
  runId: string;
  runCreatedAt: string;
  runIndex: number;
}

export type ProposalDomain = "entry" | "account" | "snapshot" | "entity" | "tag" | "group";

type JsonRecord = Record<string, unknown>;

const CHANGE_TYPE_LABEL: Record<AgentChangeType, string> = {
  create_entry: "Create Entry",
  update_entry: "Update Entry",
  delete_entry: "Delete Entry",
  create_account: "Create Account",
  update_account: "Update Account",
  delete_account: "Delete Account",
  create_snapshot: "Create Snapshot",
  delete_snapshot: "Delete Snapshot",
  create_group: "Create Group",
  update_group: "Update Group",
  delete_group: "Delete Group",
  create_group_member: "Add Group Member",
  delete_group_member: "Remove Group Member",
  create_tag: "Create Tag",
  update_tag: "Update Tag",
  delete_tag: "Delete Tag",
  create_entity: "Create Entity",
  update_entity: "Update Entity",
  delete_entity: "Delete Entity"
};

const CHANGE_TYPE_DOMAIN: Record<AgentChangeType, ProposalDomain> = {
  create_entry: "entry",
  update_entry: "entry",
  delete_entry: "entry",
  create_account: "account",
  update_account: "account",
  delete_account: "account",
  create_snapshot: "snapshot",
  delete_snapshot: "snapshot",
  create_group: "group",
  update_group: "group",
  delete_group: "group",
  create_group_member: "group",
  delete_group_member: "group",
  create_tag: "tag",
  update_tag: "tag",
  delete_tag: "tag",
  create_entity: "entity",
  update_entity: "entity",
  delete_entity: "entity"
};

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function compareIsoDateStrings(left: string, right: string): number {
  return left.localeCompare(right);
}

function itemSummaryFromPayload(changeType: AgentChangeType, payload: JsonRecord): string {
  switch (changeType) {
    case "create_entry": {
      const name = typeof payload.name === "string" ? payload.name : "Untitled";
      const date = typeof payload.date === "string" ? payload.date : "unknown date";
      return `Create Entry: ${name} on ${date}`;
    }
    case "update_entry":
    case "delete_entry": {
      const selector = asRecord(payload.selector);
      const name = typeof selector.name === "string" ? selector.name : "Unknown entry";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${name}`;
    }
    case "create_tag":
    case "delete_tag": {
      const name = typeof payload.name === "string" ? payload.name : "Untitled";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${name}`;
    }
    case "create_account":
    case "delete_account": {
      const name = typeof payload.name === "string" ? payload.name : "Untitled";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${name}`;
    }
    case "create_snapshot": {
      const accountName = typeof payload.account_name === "string" ? payload.account_name : "Untitled";
      const snapshotAt = typeof payload.snapshot_at === "string" ? payload.snapshot_at : "unknown date";
      return `Create Snapshot: ${accountName} on ${snapshotAt}`;
    }
    case "delete_snapshot": {
      const accountName = typeof payload.account_name === "string" ? payload.account_name : "Untitled";
      const target = asRecord(payload.target);
      const snapshotAt = typeof target.snapshot_at === "string" ? target.snapshot_at : "unknown date";
      return `Delete Snapshot: ${accountName} on ${snapshotAt}`;
    }
    case "create_group":
    case "delete_group": {
      const target = asRecord(payload.target);
      const name =
        typeof payload.name === "string"
          ? payload.name
          : typeof target.name === "string"
            ? target.name
            : "Untitled";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${name}`;
    }
    case "update_group": {
      const current = asRecord(payload.current);
      const name = typeof current.name === "string" ? current.name : "Untitled";
      return `Update Group: ${name}`;
    }
    case "create_group_member":
    case "delete_group_member": {
      const groupPreview = asRecord(payload.group_preview);
      const memberPreview = asRecord(payload.member_preview);
      const groupName = typeof groupPreview.name === "string" ? groupPreview.name : "Group";
      const memberName = typeof memberPreview.name === "string" ? memberPreview.name : "Member";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${groupName} -> ${memberName}`;
    }
    case "update_tag": {
      const currentName = typeof payload.name === "string" ? payload.name : "Untitled";
      return `Update Tag: ${currentName}`;
    }
    case "update_account": {
      const currentName = typeof payload.name === "string" ? payload.name : "Untitled";
      return `Update Account: ${currentName}`;
    }
    case "create_entity":
    case "delete_entity": {
      const name = typeof payload.name === "string" ? payload.name : "Untitled";
      return `${CHANGE_TYPE_LABEL[changeType]}: ${name}`;
    }
    case "update_entity": {
      const currentName = typeof payload.name === "string" ? payload.name : "Untitled";
      return `Update Entity: ${currentName}`;
    }
    default:
      return CHANGE_TYPE_LABEL[changeType];
  }
}

export function buildThreadReviewItems(runs: AgentRun[]): ThreadReviewItem[] {
  const orderedRuns = [...runs].sort((left, right) => compareIsoDateStrings(left.created_at, right.created_at));

  return orderedRuns
    .flatMap((run, runIndex) =>
      run.change_items.map((item) => ({
        item,
        runId: run.id,
        runCreatedAt: run.created_at,
        runIndex: runIndex + 1
      }))
    )
    .sort((left, right) => {
      const createdAtComparison = compareIsoDateStrings(left.item.created_at, right.item.created_at);
      if (createdAtComparison !== 0) {
        return createdAtComparison;
      }
      return left.item.id.localeCompare(right.item.id);
    });
}

export function isPendingReviewStatus(status: AgentChangeStatus): boolean {
  return status === "PENDING_REVIEW";
}

export function buildReviewItemSummary(item: AgentChangeItem): string {
  return itemSummaryFromPayload(item.change_type, item.payload_json);
}

export function shortId(value: string): string {
  return value.slice(0, 8);
}

export function changeTypeLabel(changeType: AgentChangeType): string {
  return CHANGE_TYPE_LABEL[changeType];
}

export function proposalDomain(changeType: AgentChangeType): ProposalDomain {
  return CHANGE_TYPE_DOMAIN[changeType];
}
