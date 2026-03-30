import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AgentRunBlock } from "./AgentRunBlock";
import { buildChangeItem, buildRun, buildRunEvent, buildToolCall } from "../../test/factories/agent";

describe("AgentRunBlock", () => {
  it("renders summary mode without a per-run review button", () => {
    const run = buildRun({
      id: "run-summary",
      change_items: [buildChangeItem({ id: "change-1", status: "PENDING_REVIEW", change_type: "create_entry" })]
    });

    render(<AgentRunBlock run={run} isMutating={false} mode="summary" />);

    expect(screen.getByText("1 proposed changes pending review")).toBeInTheDocument();
    expect(screen.getByText("Use the thread header Review button to process proposals.")).toBeInTheDocument();
  });

  it("renders interleaved activity timeline for reasoning updates", () => {
    const toolCall = buildToolCall({ id: "tool-1", tool_name: "list_entries", created_at: "2026-02-15T10:00:00Z" });
    const run = buildRun({
      id: "run-activity",
      status: "running",
      events: [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" }),
        buildRunEvent({
          id: "event-2",
          sequence_index: 2,
          event_type: "reasoning_update",
          message: "Validating candidate entries",
          source: "tool_call"
        })
      ]
      ,
      tool_calls: [toolCall]
    });

    render(<AgentRunBlock run={run} isMutating={false} mode="activity" />);

    expect(screen.getAllByText("Validating candidate entries").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1 tool call, 1 update")).toBeInTheDocument();
  });

  it("renders model-visible tool output in tool-call details", async () => {
    const toolCall = buildToolCall({
      id: "tool-1",
      tool_name: "list_entries",
      display_label: "Listed entries",
      output_text: "OK\nsummary: returned 2 of 2 matching entries",
      output_json: { status: "ok", summary: "returned 2 of 2 matching entries" }
    });
    const run = buildRun({
      id: "run-tool-output",
      status: "completed",
      events: [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" }),
        buildRunEvent({ id: "event-2", sequence_index: 2, event_type: "tool_call_completed", tool_call_id: "tool-1" })
      ]
      ,
      tool_calls: [toolCall]
    });

    render(<AgentRunBlock run={run} isMutating={false} mode="activity" />);

    await userEvent.click(screen.getByText("1 tool call"));
    await userEvent.click(screen.getByText("Listed entries"));

    expect(screen.getByText("Model-visible tool result")).toBeInTheDocument();
    expect(screen.getByText(/OK\s+summary: returned 2 of 2 matching entries/i)).toBeInTheDocument();
    expect(screen.getByText("Structured output (debug)")).toBeInTheDocument();
  });

  it("renders placeholder tool rows from optimistic events before tool snapshot arrives", async () => {
    const optimisticToolCall = buildToolCall({
      id: "tool-1",
      tool_name: "list_tags",
      display_label: "Listed tags",
      input_json: { include_descriptions: true }
    });
    const run = buildRun({
      id: "run-optimistic",
      status: "running",
      events: []
    });

    render(
      <AgentRunBlock
        run={run}
        isMutating={false}
        mode="activity"
        optimisticEvents={[
          buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" })
        ]}
        optimisticToolCalls={[optimisticToolCall]}
      />
    );

    await userEvent.click(screen.getByText("1 tool call"));
    await userEvent.click(screen.getByText("Listed tags"));

    expect(screen.queryByText("Waiting for tool snapshot...")).not.toBeInTheDocument();
    expect(screen.getByText("Arguments")).toBeInTheDocument();
  });

  it("hydrates compact tool call payloads when the row is expanded", async () => {
    const onHydrateToolCall = vi.fn();
    const onInspectActivity = vi.fn();
    const toolCall = buildToolCall({
      id: "tool-compact",
      run_id: "run-compact",
      tool_name: "list_tags",
      display_label: "Listed tags",
      has_full_payload: false,
      input_json: null,
      output_json: null,
      output_text: null
    });
    const run = buildRun({
      id: "run-compact",
      status: "running",
      events: [
        buildRunEvent({
          id: "event-1",
          run_id: "run-compact",
          sequence_index: 1,
          event_type: "tool_call_started",
          tool_call_id: "tool-compact"
        })
      ],
      tool_calls: [toolCall]
    });

    render(
      <AgentRunBlock
        run={run}
        isMutating={false}
        onInspectActivity={onInspectActivity}
        onHydrateToolCall={onHydrateToolCall}
        mode="activity"
      />
    );

    await userEvent.click(screen.getByText("Listed tags"));

    expect(onInspectActivity).toHaveBeenCalled();
    expect(onHydrateToolCall).toHaveBeenCalledWith("run-compact", "tool-compact");
    expect(screen.getByText("Tool details")).toBeInTheDocument();
  });

  it("renders streamed compact tool display labels before hydration", async () => {
    const compactToolCall = buildToolCall({
      id: "tool-streamed-compact",
      run_id: "run-streamed-compact",
      tool_name: "propose_create_entity",
      display_label: "Proposed entity creation",
      has_full_payload: false,
      input_json: null,
      output_json: null,
      output_text: null,
      status: "queued"
    });
    const run = buildRun({
      id: "run-streamed-compact",
      status: "running",
      events: []
    });

    render(
      <AgentRunBlock
        run={run}
        isMutating={false}
        mode="activity"
        optimisticEvents={[
          buildRunEvent({
            id: "event-1",
            run_id: "run-streamed-compact",
            sequence_index: 1,
            event_type: "tool_call_queued",
            tool_call_id: "tool-streamed-compact"
          })
        ]}
        optimisticToolCalls={[compactToolCall]}
      />
    );

    expect(screen.getByText("Proposed entity creation")).toBeInTheDocument();

    await userEvent.click(screen.getByText("Proposed entity creation"));

    expect(screen.getByText("Tool details")).toBeInTheDocument();
    expect(screen.getByText("Loading on demand...")).toBeInTheDocument();
  });

  it("renders transient streaming assistant text inside the activity bubble", () => {
    const run = buildRun({
      id: "run-streaming",
      status: "running",
      events: []
    });

    render(
      <AgentRunBlock
        run={run}
        isMutating={false}
        mode="activity"
        streamingAssistantText={"Working through the next batch of entries."}
      />
    );

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("Working through the next batch of entries.").length).toBeGreaterThanOrEqual(1);
  });

  it("renders a live assistant placeholder as soon as the run starts", () => {
    const run = buildRun({
      id: "run-started",
      status: "running",
      events: [buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "run_started" })]
    });

    render(<AgentRunBlock run={run} isMutating={false} mode="activity" />);

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
  });

  it("keeps whitespace-only early stream chunks visible inside the activity bubble", () => {
    const run = buildRun({
      id: "run-whitespace-stream",
      status: "running",
      events: []
    });

    render(
      <AgentRunBlock
        run={run}
        isMutating={false}
        mode="activity"
        streamingAssistantText={"  "}
      />
    );

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
  });

  it("keeps tool rows collapsed by default while streaming", () => {
    const toolCall = buildToolCall({ id: "tool-1", tool_name: "list_entries", display_label: "Listed entries" });
    const run = buildRun({
      id: "run-running-tool",
      status: "running",
      events: [buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_started", tool_call_id: "tool-1" })],
      tool_calls: [toolCall]
    });

    render(<AgentRunBlock run={run} isMutating={false} mode="activity" />);

    const toolDetails = screen.getByText("Listed entries").closest("details");
    expect(toolDetails).not.toHaveAttribute("open");
  });
});
