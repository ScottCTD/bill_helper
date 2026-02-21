import { afterEach, describe, expect, it, vi } from "vitest";

import {
  appendPendingReasoningUpdateToActivity,
  appendPendingToolCallToActivity,
  buildRunActivityTimeline,
  runsByAssistantMessage,
  runsWithoutAssistantMessage,
  sortRunsByCreatedAt,
  summarizeRunChangeTypes,
  latestRunMetric,
  totalRunMetric
} from "./activity";
import { buildChangeItem, buildRun, buildToolCall } from "../../test/factories/agent";
import type { AgentThreadDetail } from "../../lib/types";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("activity helpers", () => {
  it("builds interleaved run activity timeline from tool calls", () => {
    const timeline = buildRunActivityTimeline([
      buildToolCall({ id: "tool-1", created_at: "2026-02-15T10:00:00Z", tool_name: "list_entries" }),
      buildToolCall({
        id: "tool-2",
        created_at: "2026-02-15T10:00:01Z",
        tool_name: "send_intermediate_update",
        output_json: { message: "Looking up historical entries" }
      }),
      buildToolCall({ id: "tool-3", created_at: "2026-02-15T10:00:02Z", tool_name: "create_entry" })
    ]);

    expect(timeline).toHaveLength(3);
    expect(timeline[0]).toMatchObject({ type: "tool_batch", key: "tool-1-tool-1" });
    expect(timeline[1]).toMatchObject({ type: "reasoning_update", message: "Looking up historical entries" });
    expect(timeline[2]).toMatchObject({ type: "tool_batch", key: "tool-3-tool-3" });
  });

  it("batches pending tool calls and ignores intermediate update tool", () => {
    vi.spyOn(Date, "now").mockReturnValue(1700000000000);

    const first = appendPendingToolCallToActivity([], "list_entries");
    expect(first).toHaveLength(1);
    expect(first[0]).toMatchObject({ type: "tool_batch", toolNames: ["list_entries"] });

    const second = appendPendingToolCallToActivity(first, "create_entry");
    expect(second).toHaveLength(1);
    expect(second[0]).toMatchObject({ type: "tool_batch", toolNames: ["list_entries", "create_entry"] });

    const unchanged = appendPendingToolCallToActivity(second, "send_intermediate_update");
    expect(unchanged).toEqual(second);
  });

  it("appends trimmed reasoning updates only", () => {
    vi.spyOn(Date, "now").mockReturnValue(1700000000000);

    const withUpdate = appendPendingReasoningUpdateToActivity([], "  Step 1 complete  ");
    expect(withUpdate).toHaveLength(1);
    expect(withUpdate[0]).toMatchObject({ type: "reasoning_update", message: "Step 1 complete" });

    const unchanged = appendPendingReasoningUpdateToActivity(withUpdate, "   ");
    expect(unchanged).toEqual(withUpdate);
  });

  it("indexes runs by assistant message and separates unattached runs", () => {
    const threadDetail: AgentThreadDetail = {
      thread: {
        id: "thread-1",
        title: "Thread",
        created_at: "2026-02-15T10:00:00Z",
        updated_at: "2026-02-15T10:05:00Z"
      },
      messages: [],
      configured_model_name: "gpt-test",
      runs: [
        buildRun({ id: "run-b", created_at: "2026-02-15T10:02:00Z", assistant_message_id: "assistant-1" }),
        buildRun({ id: "run-a", created_at: "2026-02-15T10:01:00Z", assistant_message_id: "assistant-1" }),
        buildRun({ id: "run-c", created_at: "2026-02-15T10:03:00Z", assistant_message_id: null })
      ]
    };

    const indexed = runsByAssistantMessage(threadDetail);
    expect(indexed.get("assistant-1")?.map((run) => run.id)).toEqual(["run-a", "run-b"]);

    const unattached = runsWithoutAssistantMessage(threadDetail);
    expect(unattached.map((run) => run.id)).toEqual(["run-c"]);
  });

  it("aggregates metrics and change-type counts", () => {
    const runs = [
      buildRun({ id: "run-1", input_tokens: 10, total_cost_usd: 0.001 }),
      buildRun({ id: "run-2", input_tokens: 15, total_cost_usd: 0.002 }),
      buildRun({ id: "run-3", input_tokens: null, total_cost_usd: null })
    ];
    expect(totalRunMetric(runs, "input_tokens")).toBe(25);
    expect(totalRunMetric(runs, "total_cost_usd")).toBe(0.003);

    const none = [buildRun({ id: "run-4", input_tokens: null })];
    expect(totalRunMetric(none, "input_tokens")).toBeNull();
    expect(latestRunMetric(none, "input_tokens")).toBeNull();
    expect(latestRunMetric(runs, "input_tokens")).toBe(15);
    expect(latestRunMetric([buildRun({ id: "run-5", input_tokens: 33 })], "input_tokens")).toBe(33);

    const changeSummary = summarizeRunChangeTypes([
      buildChangeItem({ id: "change-1", change_type: "create_entry" }),
      buildChangeItem({ id: "change-2", change_type: "update_entry" }),
      buildChangeItem({ id: "change-3", change_type: "create_tag" }),
      buildChangeItem({ id: "change-4", change_type: "delete_entity" })
    ]);

    expect(changeSummary).toEqual({ entryCount: 2, tagCount: 1, entityCount: 1 });
  });

  it("sorts runs in chronological order", () => {
    const sorted = sortRunsByCreatedAt([
      buildRun({ id: "run-late", created_at: "2026-02-15T10:02:00Z" }),
      buildRun({ id: "run-early", created_at: "2026-02-15T10:01:00Z" })
    ]);

    expect(sorted.map((run) => run.id)).toEqual(["run-early", "run-late"]);
  });
});
