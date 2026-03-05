import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { AgentMessage } from "../../../lib/types";
import { buildRun, buildRunEvent, buildToolCall } from "../../../test/factories/agent";
import { AgentTimeline } from "./AgentTimeline";
import type { PendingAssistantMessage } from "./types";

function buildMessage(overrides: Partial<AgentMessage> = {}): AgentMessage {
  return {
    id: overrides.id ?? "message-1",
    thread_id: overrides.thread_id ?? "thread-1",
    role: overrides.role ?? "user",
    content_markdown: overrides.content_markdown ?? "Hello",
    created_at: overrides.created_at ?? "2026-02-15T10:00:00Z",
    attachments: overrides.attachments ?? []
  };
}

function buildPendingAssistantMessage(
  overrides: Partial<PendingAssistantMessage> = {}
): PendingAssistantMessage {
  return {
    id: overrides.id ?? "pending-assistant-1",
    threadId: overrides.threadId ?? "thread-1",
    createdAt: overrides.createdAt ?? "2026-02-15T10:00:00Z",
    baselineLastAssistantMessageId:
      overrides.baselineLastAssistantMessageId !== undefined
        ? overrides.baselineLastAssistantMessageId
        : null
  };
}

function renderTimeline(
  overrides: Partial<Parameters<typeof AgentTimeline>[0]> = {}
) {
  const props = {
    selectedThreadId: "thread-1",
    isLoading: false,
    errorMessage: null,
    messages: [],
    timelineScrollRef: createRef<HTMLDivElement>(),
    runsByAssistantMessageId: new Map(),
    pendingAssistantRuns: [],
    pendingAssistantRunsByUserMessageId: new Map(),
    pendingUserMessage: null,
    pendingAssistantMessage: null,
    shouldShowOptimisticAssistantBubble: false,
    pendingRunAttachedToOptimisticMessage: null,
    isMutating: false,
    activeStreamText: "",
    optimisticRunEventsByRunId: {},
    optimisticToolCallsByRunId: {},
    activeOptimisticEvents: [],
    activeOptimisticToolCalls: [],
    onHydrateToolCall: () => undefined,
    hydratingToolCallIds: new Set<string>(),
    onReviewRun: () => undefined,
    isAtBottom: true,
    scrollToBottom: () => undefined,
    ...overrides
  };

  return render(<AgentTimeline {...props} />);
}

describe("AgentTimeline", () => {
  it("shows the optimistic assistant caret before the first stream event arrives", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true
    });

    expect(screen.getByText("▍")).toBeInTheDocument();
    expect(container.querySelector(".agent-message-streaming-text")).not.toBeNull();
  });

  it("switches into the live activity bubble as soon as run_started arrives", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      activeOptimisticEvents: [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "run_started" })
      ]
    });

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
    expect(container.querySelector(".agent-message-streaming-text")).toBeNull();
  });

  it("keeps whitespace-only early stream chunks visible inside the live activity bubble", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      activeStreamText: "  "
    });

    expect(screen.getByText("1 update")).toBeInTheDocument();
    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
    expect(container.querySelector(".agent-message-streaming-text")).toBeNull();
  });

  it("anchors interrupted pending runs after the triggering user message without duplicating them", () => {
    const userMessage = buildMessage({
      id: "message-user-1",
      role: "user",
      content_markdown: "Please import the statement."
    });
    const interruptedRun = buildRun({
      id: "run-interrupted",
      user_message_id: userMessage.id,
      assistant_message_id: null,
      status: "failed",
      error_text: "Run interrupted by user."
    });

    renderTimeline({
      messages: [userMessage],
      pendingAssistantRuns: [interruptedRun],
      pendingAssistantRunsByUserMessageId: new Map([[userMessage.id, [interruptedRun]]])
    });

    expect(screen.getAllByText("Run interrupted by user.")).toHaveLength(1);
    expect(screen.getByText("Please import the statement.")).toBeInTheDocument();
  });

  it("does not render empty assistant shells for legacy tool-only runs without events", () => {
    const userMessage = buildMessage({
      id: "message-user-1",
      role: "user",
      content_markdown: "Show the old run."
    });
    const legacyRun = buildRun({
      id: "run-legacy-tool-only",
      user_message_id: userMessage.id,
      assistant_message_id: null,
      status: "completed",
      events: [],
      tool_calls: [buildToolCall({ id: "tool-legacy", run_id: "run-legacy-tool-only" })],
      change_items: [],
      error_text: null
    });

    renderTimeline({
      messages: [userMessage],
      pendingAssistantRuns: [legacyRun],
      pendingAssistantRunsByUserMessageId: new Map([[userMessage.id, [legacyRun]]])
    });

    expect(screen.getByText("Show the old run.")).toBeInTheDocument();
    expect(screen.queryAllByText("Assistant")).toHaveLength(0);
    expect(screen.queryByText("1 tool call")).not.toBeInTheDocument();
  });

  it("renders attached optimistic tool progress with hydrated tool details and no duplicate run card", async () => {
    const run = buildRun({
      id: "run-live-tools",
      status: "running",
      assistant_message_id: null,
      events: []
    });
    const toolCall = buildToolCall({
      id: "tool-1",
      run_id: run.id,
      tool_name: "list_tags",
      input_json: { include_descriptions: true },
      status: "queued",
      output_text: ""
    });

    renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      pendingAssistantRuns: [run],
      pendingRunAttachedToOptimisticMessage: run,
      activeOptimisticEvents: [
        buildRunEvent({
          id: "event-1",
          run_id: run.id,
          sequence_index: 1,
          event_type: "tool_call_queued",
          tool_call_id: toolCall.id
        })
      ],
      activeOptimisticToolCalls: [toolCall]
    });

    expect(screen.getAllByText("1 tool call")).toHaveLength(1);
    expect(document.querySelectorAll("article.agent-message-assistant")).toHaveLength(1);

    await userEvent.click(screen.getByText("list_tags"));

    expect(screen.getByText("Arguments")).toBeInTheDocument();
    expect(screen.queryByText("Waiting for tool snapshot...")).not.toBeInTheDocument();
  });

  it("shows persisted updates and in-flight streamed text together in order inside one live bubble", () => {
    const run = buildRun({
      id: "run-live-update",
      status: "running",
      assistant_message_id: null,
      events: []
    });

    renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      pendingRunAttachedToOptimisticMessage: run,
      activeOptimisticEvents: [
        buildRunEvent({
          id: "event-1",
          run_id: run.id,
          sequence_index: 1,
          event_type: "reasoning_update",
          source: "assistant_content",
          message: "Drafting the first batch now."
        })
      ],
      activeStreamText: "Still streaming the next sentence..."
    });

    expect(screen.getByText("2 updates")).toBeInTheDocument();
    expect(screen.getAllByText("Drafting the first batch now.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Still streaming the next sentence...").length).toBeGreaterThanOrEqual(1);

    const liveBubbleText = document.querySelector("article.agent-message-streaming")?.textContent ?? "";
    expect(liveBubbleText.indexOf("Drafting the first batch now.")).toBeGreaterThanOrEqual(0);
    expect(liveBubbleText.indexOf("Still streaming the next sentence...")).toBeGreaterThan(
      liveBubbleText.indexOf("Drafting the first batch now.")
    );
  });
});
