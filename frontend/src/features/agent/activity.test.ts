import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildRunTimelineFromEvents,
  buildThreadUsageTotals,
  latestRunMetric,
  mergeRunEvents,
  mergeRunToolCalls,
  runsByAssistantMessage,
  runsWithoutAssistantMessageByUserMessage,
  runsWithoutAssistantMessage,
  sortRunsByCreatedAt,
  summarizeRunChangeTypes,
  totalRunMetric
} from "./activity";
import { buildChangeItem, buildRun, buildRunEvent, buildToolCall } from "../../test/factories/agent";
import type { AgentThreadDetail } from "../../lib/types";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("activity helpers", () => {
  it("builds interleaved timeline from run events and tool calls", () => {
    const toolCall = buildToolCall({ id: "tool-1", tool_name: "list_entries" });
    const timeline = buildRunTimelineFromEvents(
      [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" }),
        buildRunEvent({
          id: "event-2",
          sequence_index: 2,
          event_type: "reasoning_update",
          message: "Looking up historical entries",
          source: "tool_call"
        }),
        buildRunEvent({ id: "event-3", sequence_index: 3, event_type: "tool_call_completed", tool_call_id: "tool-1" })
      ],
      [toolCall]
    );

    expect(timeline).toHaveLength(2);
    expect(timeline[0]).toMatchObject({ type: "tool_call", toolCallId: "tool-1", lifecycleEventType: "tool_call_completed" });
    expect(timeline[1]).toMatchObject({ type: "reasoning_update", message: "Looking up historical entries" });
  });

  it("keeps placeholder tool rows when events arrive before tool snapshots", () => {
    const timeline = buildRunTimelineFromEvents(
      [buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" })],
      []
    );

    expect(timeline).toHaveLength(1);
    expect(timeline[0]).toMatchObject({ type: "tool_call", toolCallId: "tool-1", toolCall: null });
  });

  it("does not reconstruct activity from tool rows when run events are missing", () => {
    const timeline = buildRunTimelineFromEvents(
      [],
      [buildToolCall({ id: "tool-1", tool_name: "legacy_tool", status: "ok" })]
    );

    expect(timeline).toEqual([]);
  });

  it("keeps tool rows in original queue order while updating lifecycle in place", () => {
    const timeline = buildRunTimelineFromEvents(
      [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" }),
        buildRunEvent({ id: "event-2", sequence_index: 2, event_type: "tool_call_queued", tool_call_id: "tool-2" }),
        buildRunEvent({
          id: "event-3",
          sequence_index: 3,
          event_type: "reasoning_update",
          message: "Continuing with the next batch",
          source: "assistant_content"
        }),
        buildRunEvent({ id: "event-4", sequence_index: 4, event_type: "tool_call_started", tool_call_id: "tool-1" }),
        buildRunEvent({ id: "event-5", sequence_index: 5, event_type: "tool_call_completed", tool_call_id: "tool-2" })
      ],
      [
        buildToolCall({ id: "tool-1", tool_name: "first_tool", status: "running" }),
        buildToolCall({ id: "tool-2", tool_name: "second_tool", status: "ok" })
      ]
    );

    expect(timeline).toHaveLength(3);
    expect(timeline[0]).toMatchObject({ type: "tool_call", toolCallId: "tool-1", lifecycleEventType: "tool_call_started" });
    expect(timeline[1]).toMatchObject({ type: "tool_call", toolCallId: "tool-2", lifecycleEventType: "tool_call_completed" });
    expect(timeline[2]).toMatchObject({ type: "reasoning_update", message: "Continuing with the next batch" });
  });

  it("merges persisted and optimistic events without duplicates", () => {
    const merged = mergeRunEvents(
      [
        buildRunEvent({ id: "event-1", sequence_index: 1 }),
        buildRunEvent({ id: "event-2", sequence_index: 2 })
      ],
      [
        buildRunEvent({ id: "event-2", sequence_index: 2 }),
        buildRunEvent({ id: "event-3", sequence_index: 3 })
      ]
    );

    expect(merged.map((event) => event.id)).toEqual(["event-1", "event-2", "event-3"]);
  });

  it("orders merged events by sequence index before timestamp", () => {
    const merged = mergeRunEvents(
      [
        buildRunEvent({
          id: "event-2",
          sequence_index: 2,
          created_at: "2026-02-15T10:02:00Z"
        }),
        buildRunEvent({
          id: "event-3",
          sequence_index: 3,
          created_at: "2026-02-15T10:00:00Z"
        })
      ],
      [
        buildRunEvent({
          id: "event-1",
          sequence_index: 1,
          created_at: "2026-02-15T10:03:00Z"
        })
      ]
    );

    expect(merged.map((event) => event.id)).toEqual(["event-1", "event-2", "event-3"]);
  });

  it("merges optimistic tool snapshots over older persisted tool rows", () => {
    const merged = mergeRunToolCalls(
      [buildToolCall({ id: "tool-1", status: "queued", output_text: "" })],
      [buildToolCall({ id: "tool-1", status: "ok", output_text: "OK" })]
    );

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ id: "tool-1", status: "ok", output_text: "OK" });
  });

  it("preserves hydrated payloads when a later compact snapshot arrives", () => {
    const merged = mergeRunToolCalls(
      [
        buildToolCall({
          id: "tool-1",
          status: "running",
          has_full_payload: true,
          input_json: { entity_name: "ACME" },
          output_json: { status: "OK", proposal_id: "proposal-1" },
          output_text: "OK\nproposal_id: proposal-1"
        })
      ],
      [
        buildToolCall({
          id: "tool-1",
          status: "ok",
          has_full_payload: false,
          input_json: null,
          output_json: null,
          output_text: null
        })
      ]
    );

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: "tool-1",
      status: "ok",
      has_full_payload: true,
      input_json: { entity_name: "ACME" },
      output_json: { status: "OK", proposal_id: "proposal-1" },
      output_text: "OK\nproposal_id: proposal-1"
    });
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
      current_context_tokens: 42,
      runs: [
        buildRun({ id: "run-b", created_at: "2026-02-15T10:02:00Z", assistant_message_id: "assistant-1" }),
        buildRun({ id: "run-a", created_at: "2026-02-15T10:01:00Z", assistant_message_id: "assistant-1" }),
        buildRun({ id: "run-c", created_at: "2026-02-15T10:03:00Z", assistant_message_id: null, user_message_id: "user-3" })
      ]
    };

    const indexed = runsByAssistantMessage(threadDetail);
    expect(indexed.get("assistant-1")?.map((run) => run.id)).toEqual(["run-a", "run-b"]);

    const unattached = runsWithoutAssistantMessage(threadDetail);
    expect(unattached.map((run) => run.id)).toEqual(["run-c"]);

    const unattachedByUserMessage = runsWithoutAssistantMessageByUserMessage(threadDetail);
    expect(unattachedByUserMessage.get("user-3")?.map((run) => run.id)).toEqual(["run-c"]);
  });

  it("aggregates metrics and change-type counts", () => {
    const runs = [
      buildRun({ id: "run-1", input_tokens: 10, output_tokens: 20, total_cost_usd: 0.001 }),
      buildRun({ id: "run-2", input_tokens: 15, output_tokens: 40, total_cost_usd: 0.002 }),
      buildRun({ id: "run-3", input_tokens: null, output_tokens: null, total_cost_usd: null })
    ];
    expect(totalRunMetric(runs, "input_tokens")).toBe(25);
    expect(totalRunMetric(runs, "total_cost_usd")).toBe(0.003);

    const none = [buildRun({ id: "run-4", input_tokens: null })];
    expect(totalRunMetric(none, "input_tokens")).toBeNull();
    expect(latestRunMetric(none, "input_tokens")).toBeNull();
    expect(latestRunMetric(runs, "input_tokens")).toBe(15);
    expect(latestRunMetric([buildRun({ id: "run-5", input_tokens: 33 })], "input_tokens")).toBe(33);

    expect(
      buildThreadUsageTotals({
        thread: {
          id: "thread-1",
          title: "Thread",
          created_at: "2026-02-15T10:00:00Z",
          updated_at: "2026-02-15T10:05:00Z"
        },
        messages: [],
        runs,
        configured_model_name: "gpt-test",
        current_context_tokens: 88
      })
    ).toEqual({
      context: 88,
      input: 25,
      output: 60,
      cacheRead: 0,
      totalCost: 0.003
    });

    const changeSummary = summarizeRunChangeTypes([
      buildChangeItem({ id: "change-1", change_type: "create_entry" }),
      buildChangeItem({ id: "change-2", change_type: "update_entry" }),
      buildChangeItem({ id: "change-3", change_type: "create_group_member" }),
      buildChangeItem({ id: "change-4", change_type: "create_tag" }),
      buildChangeItem({ id: "change-5", change_type: "delete_entity" })
    ]);

    expect(changeSummary).toEqual({ entryCount: 2, groupCount: 1, tagCount: 1, entityCount: 1 });
  });

  it("sorts runs in chronological order", () => {
    const sorted = sortRunsByCreatedAt([
      buildRun({ id: "run-late", created_at: "2026-02-15T10:02:00Z" }),
      buildRun({ id: "run-early", created_at: "2026-02-15T10:01:00Z" })
    ]);

    expect(sorted.map((run) => run.id)).toEqual(["run-early", "run-late"]);
  });
});
