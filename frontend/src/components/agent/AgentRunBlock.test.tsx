import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AgentRunBlock } from "./AgentRunBlock";
import { buildChangeItem, buildRun, buildRunEvent, buildToolCall } from "../../test/factories/agent";

describe("AgentRunBlock", () => {
  it("renders summary mode and forwards review actions", async () => {
    const onReviewRun = vi.fn();
    const run = buildRun({
      id: "run-summary",
      change_items: [buildChangeItem({ id: "change-1", status: "PENDING_REVIEW", change_type: "create_entry" })]
    });

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={onReviewRun} mode="summary" />);

    expect(screen.getByText("1 proposed changes pending review")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Click to review proposed changes" }));
    expect(onReviewRun).toHaveBeenCalledWith("run-summary");
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

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={() => undefined} mode="activity" />);

    expect(screen.getAllByText("Validating candidate entries").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1 tool call, 1 update")).toBeInTheDocument();
  });

  it("renders model-visible tool output in tool-call details", async () => {
    const toolCall = buildToolCall({
      id: "tool-1",
      tool_name: "list_entries",
      output_text: "OK\nsummary: returned 2 of 2 matching entries",
      output_json: { status: "OK", summary: "returned 2 of 2 matching entries" }
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

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={() => undefined} mode="activity" />);

    await userEvent.click(screen.getByText("1 tool call"));
    await userEvent.click(screen.getByText("list_entries"));

    expect(screen.getByText("Model-visible tool result")).toBeInTheDocument();
    expect(screen.getByText(/OK\s+summary: returned 2 of 2 matching entries/i)).toBeInTheDocument();
    expect(screen.getByText("Structured output (debug)")).toBeInTheDocument();
  });

  it("renders placeholder tool rows from optimistic events before tool snapshot arrives", async () => {
    const optimisticToolCall = buildToolCall({
      id: "tool-1",
      tool_name: "list_tags",
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
        onReviewRun={() => undefined}
        mode="activity"
        optimisticEvents={[
          buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_queued", tool_call_id: "tool-1" })
        ]}
        optimisticToolCalls={[optimisticToolCall]}
      />
    );

    await userEvent.click(screen.getByText("1 tool call"));
    await userEvent.click(screen.getByText("list_tags"));

    expect(screen.queryByText("Waiting for tool snapshot...")).not.toBeInTheDocument();
    expect(screen.getByText("Arguments")).toBeInTheDocument();
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
        onReviewRun={() => undefined}
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

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={() => undefined} mode="activity" />);

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
        onReviewRun={() => undefined}
        mode="activity"
        streamingAssistantText={"  "}
      />
    );

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
  });

  it("keeps tool rows collapsed by default while streaming", () => {
    const toolCall = buildToolCall({ id: "tool-1", tool_name: "list_entries" });
    const run = buildRun({
      id: "run-running-tool",
      status: "running",
      events: [buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "tool_call_started", tool_call_id: "tool-1" })],
      tool_calls: [toolCall]
    });

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={() => undefined} mode="activity" />);

    const toolDetails = screen.getByText("list_entries").closest("details");
    expect(toolDetails).not.toHaveAttribute("open");
  });
});
