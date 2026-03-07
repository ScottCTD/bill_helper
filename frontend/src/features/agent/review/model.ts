import type { AgentChangeItem, AgentChangeStatus, AgentChangeType, AgentRun } from "../../../lib/types";

export interface ThreadReviewItem {
  item: AgentChangeItem;
  runId: string;
  runCreatedAt: string;
  runIndex: number;
}

type JsonRecord = Record<string, unknown>;

const CHANGE_TYPE_LABEL: Record<AgentChangeType, string> = {
  create_entry: "Create Entry",
  update_entry: "Update Entry",
  delete_entry: "Delete Entry",
  create_tag: "Create Tag",
  update_tag: "Update Tag",
  delete_tag: "Delete Tag",
  create_entity: "Create Entity",
  update_entity: "Update Entity",
  delete_entity: "Delete Entity"
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
    case "update_tag": {
      const currentName = typeof payload.name === "string" ? payload.name : "Untitled";
      return `Update Tag: ${currentName}`;
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
