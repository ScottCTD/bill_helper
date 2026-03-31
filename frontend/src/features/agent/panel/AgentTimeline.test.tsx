import { createRef, useRef, useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentMessage } from "../../../lib/types";
import { buildRun, buildRunEvent, buildToolCall } from "../../../test/factories/agent";
import { AgentTimeline, type AgentTimelineProps } from "./AgentTimeline";
import type { PendingAssistantMessage } from "./types";

const { markdownRenderSpy, requestBlobSpy } = vi.hoisted(() => ({
  markdownRenderSpy: vi.fn(),
  requestBlobSpy: vi.fn()
}));

vi.mock("../../../components/ui/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ markdown }: { markdown: string }) => {
    markdownRenderSpy(markdown);
    return <div>{markdown}</div>;
  }
}));

vi.mock("../../../lib/api/core", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api/core")>("../../../lib/api/core");
  return {
    ...actual,
    requestBlob: requestBlobSpy
  };
});

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
  overrides: Partial<AgentTimelineProps> = {}
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
    activeStreamReasoningText: "",
    activeStreamText: "",
    optimisticRunEventsByRunId: {},
    optimisticToolCallsByRunId: {},
    activeOptimisticEvents: [],
    activeOptimisticToolCalls: [],
    detachFromBottom: () => undefined,
    onHydrateToolCall: () => undefined,
    hydratingToolCallIds: new Set<string>(),
    isAtBottom: true,
    scrollToBottom: () => undefined,
    ...overrides
  };

  return render(<AgentTimeline {...props} />);
}

function expectArticleClasses(
  element: HTMLElement,
  expectedClasses: string[],
  unexpectedClasses: string[] = []
) {
  const article = element.closest("article");
  expect(article).not.toBeNull();
  for (const className of expectedClasses) {
    expect(article).toHaveClass(className);
  }
  for (const className of unexpectedClasses) {
    expect(article).not.toHaveClass(className);
  }
}

describe("AgentTimeline", () => {
  let openSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    markdownRenderSpy.mockClear();
    requestBlobSpy.mockReset();
    openSpy = vi.spyOn(window, "open").mockReturnValue(null);
  });

  afterEach(() => {
    openSpy.mockRestore();
  });

  it("does not rerender stable historical markdown for unrelated draft typing", async () => {
    const user = userEvent.setup();
    const assistantMessage = buildMessage({
      id: "message-assistant-1",
      role: "assistant",
      content_markdown: "Historical **markdown** reply"
    });
    const stableProps: AgentTimelineProps = {
      selectedThreadId: "thread-1",
      isLoading: false,
      errorMessage: null,
      messages: [assistantMessage],
      timelineScrollRef: createRef<HTMLDivElement>(),
      runsByAssistantMessageId: new Map(),
      pendingAssistantRuns: [],
      pendingAssistantRunsByUserMessageId: new Map(),
      pendingUserMessage: null,
      pendingAssistantMessage: null,
      shouldShowOptimisticAssistantBubble: false,
      pendingRunAttachedToOptimisticMessage: null,
      activeStreamReasoningText: "",
      activeStreamText: "",
      optimisticRunEventsByRunId: {},
      optimisticToolCallsByRunId: {},
      activeOptimisticEvents: [],
      activeOptimisticToolCalls: [],
      detachFromBottom: () => undefined,
      onHydrateToolCall: () => undefined,
      hydratingToolCallIds: new Set<string>(),
      isAtBottom: true,
      scrollToBottom: () => undefined
    };

    function Harness() {
      const [draft, setDraft] = useState("");
      const timelinePropsRef = useRef(stableProps);

      return (
        <>
          <label>
            Draft
            <input value={draft} onChange={(event) => setDraft(event.target.value)} />
          </label>
          <AgentTimeline {...timelinePropsRef.current} />
        </>
      );
    }

    render(<Harness />);

    expect(markdownRenderSpy).toHaveBeenCalledTimes(1);

    await user.type(screen.getByLabelText("Draft"), "hello world");

    expect(markdownRenderSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Historical **markdown** reply")).toBeInTheDocument();
    expectArticleClasses(screen.getByText("Historical **markdown** reply"), ["agent-message", "agent-message-assistant"], ["agent-message-user"]);
  });

  it("keeps user messages as right-aligned bubbles", () => {
    renderTimeline({
      messages: [
        buildMessage({
          id: "message-user-1",
          role: "user",
          content_markdown: "Bubble me."
        })
      ]
    });

    expectArticleClasses(screen.getByText("Bubble me."), ["agent-message", "agent-message-user"], ["agent-message-assistant"]);
    expect(screen.getByText("Bubble me.").closest(".agent-message-user-bubble")).not.toBeNull();
  });

  it("shows the optimistic assistant caret before the first stream event arrives", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true
    });

    expect(screen.getByText("▍")).toBeInTheDocument();
    expect(container.querySelector(".agent-message-streaming-text")).not.toBeNull();
    expectArticleClasses(screen.getByText("▍"), ["agent-message", "agent-message-assistant", "agent-message-streaming"], ["agent-message-user"]);
  });

  it("switches into the live activity bubble as soon as run_started arrives", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      activeOptimisticEvents: [
        buildRunEvent({ id: "event-1", sequence_index: 1, event_type: "run_started" })
      ]
    });

    expect(screen.getAllByText("▍").length).toBeGreaterThanOrEqual(1);
    expect(container.querySelector(".agent-message-streaming-text")).toBeNull();
  });

  it("keeps whitespace-only early stream chunks visible inside the live activity bubble", () => {
    const { container } = renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      activeStreamText: "  "
    });

    expect(markdownRenderSpy).toHaveBeenCalledWith("  ");
    expect(container.querySelector(".agent-message-streaming-text")).toBeNull();
  });

  it("shows live reasoning text in the activity bubble before the persisted reasoning event lands", () => {
    renderTimeline({
      pendingAssistantMessage: buildPendingAssistantMessage(),
      shouldShowOptimisticAssistantBubble: true,
      activeStreamReasoningText: "Checking existing entities before proposing changes."
    });

    expect(screen.getAllByText("Checking existing entities before proposing changes.").length).toBeGreaterThanOrEqual(1);
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
    expectArticleClasses(screen.getByText("Run interrupted by user."), ["agent-message", "agent-message-assistant", "agent-message-activity"], ["agent-message-user"]);
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

  it("loads persisted image attachments through the authenticated preview fetch path", async () => {
    requestBlobSpy.mockResolvedValue(new Blob(["image-bytes"], { type: "image/png" }));

    renderTimeline({
      messages: [
        buildMessage({
          role: "assistant",
          attachments: [
            {
              id: "attachment-image-1",
              message_id: "message-1",
              display_name: "receipt.png",
              mime_type: "image/png",
              file_path: "/tmp/receipt.png",
              attachment_url: "/api/v1/agent/attachments/attachment-image-1",
              created_at: "2026-02-15T10:00:00Z"
            }
          ]
        })
      ]
    });

    await waitFor(() => expect(screen.getByAltText("receipt.png")).toHaveAttribute("src", expect.stringContaining("blob:")));
    expect(requestBlobSpy).toHaveBeenCalledWith(
      "/api/v1/agent/attachments/attachment-image-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it("opens image attachments in a browser-native tab", async () => {
    requestBlobSpy.mockResolvedValue(new Blob(["image-bytes"], { type: "image/png" }));

    renderTimeline({
      messages: [
        buildMessage({
          role: "assistant",
          attachments: [
            {
              id: "attachment-image-1",
              message_id: "message-1",
              display_name: "receipt.png",
              mime_type: "image/png",
              file_path: "/tmp/receipt.png",
              attachment_url: "/api/v1/agent/attachments/attachment-image-1",
              created_at: "2026-02-15T10:00:00Z"
            }
          ]
        })
      ]
    });

    await userEvent.click(await screen.findByRole("button", { name: "Open receipt.png" }));

    expect(openSpy).toHaveBeenCalledWith(expect.stringContaining("blob:"), "_blank", "noopener,noreferrer");
  });

  it("renders persisted pdf attachments as inline browser previews", async () => {
    requestBlobSpy.mockResolvedValue(new Blob(["pdf-bytes"], { type: "application/pdf" }));

    renderTimeline({
      messages: [
        buildMessage({
          role: "assistant",
          attachments: [
            {
              id: "attachment-pdf-1",
              message_id: "message-1",
              display_name: "statement.pdf",
              mime_type: "application/pdf",
              file_path: "/tmp/statement.pdf",
              attachment_url: "/api/v1/agent/attachments/attachment-pdf-1",
              created_at: "2026-02-15T10:00:00Z"
            }
          ]
        })
      ]
    });

    await waitFor(() => expect(screen.getByTitle("statement.pdf")).toHaveAttribute("src", expect.stringContaining("blob:")));
    expect(screen.getByText("statement.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "statement.pdf" })).not.toBeInTheDocument();
    expect(requestBlobSpy).toHaveBeenCalledWith(
      "/api/v1/agent/attachments/attachment-pdf-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it("opens pdf attachments in a browser-native tab", async () => {
    requestBlobSpy.mockResolvedValue(new Blob(["pdf-bytes"], { type: "application/pdf" }));

    renderTimeline({
      messages: [
        buildMessage({
          role: "assistant",
          attachments: [
            {
              id: "attachment-pdf-1",
              message_id: "message-1",
              display_name: "statement.pdf",
              mime_type: "application/pdf",
              file_path: "/tmp/statement.pdf",
              attachment_url: "/api/v1/agent/attachments/attachment-pdf-1",
              created_at: "2026-02-15T10:00:00Z"
            }
          ]
        })
      ]
    });

    await userEvent.click(await screen.findByRole("button", { name: "Open" }));

    expect(openSpy).toHaveBeenCalledWith(expect.stringContaining("blob:"), "_blank", "noopener,noreferrer");
  });

  it("renders user attachments as compact file rows above the message text", async () => {
    requestBlobSpy.mockResolvedValue(new Blob(["pdf-bytes"], { type: "application/pdf" }));

    renderTimeline({
      messages: [
        buildMessage({
          role: "user",
          content_markdown: "Please review these statements.",
          attachments: [
            {
              id: "attachment-pdf-1",
              message_id: "message-1",
              display_name: "statement.pdf",
              mime_type: "application/pdf",
              file_path: "/tmp/statement.pdf",
              attachment_url: "/api/v1/agent/attachments/attachment-pdf-1",
              created_at: "2026-02-15T10:00:00Z"
            }
          ]
        })
      ]
    });

    const bubble = screen.getByText("Please review these statements.").closest(".agent-message-user-bubble");
    expect(bubble).not.toBeNull();
    expect(await screen.findByRole("button", { name: "Open statement.pdf" })).toBeInTheDocument();
    expect(screen.getByText("statement.pdf")).toBeInTheDocument();
    expect(screen.queryByTitle("statement.pdf")).not.toBeInTheDocument();
    expect(requestBlobSpy).toHaveBeenCalledWith(
      "/api/v1/agent/attachments/attachment-pdf-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
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

    expect(screen.getByText("list_tags")).toBeInTheDocument();
    expect(document.querySelectorAll("article.agent-message-assistant")).toHaveLength(1);
    expect(document.querySelectorAll("article.agent-message-user")).toHaveLength(0);

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

    expect(screen.getAllByText("Drafting the first batch now.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Still streaming the next sentence...").length).toBeGreaterThanOrEqual(1);

    const liveBubbleText = document.querySelector("article.agent-message-streaming")?.textContent ?? "";
    expect(liveBubbleText.indexOf("Drafting the first batch now.")).toBeGreaterThanOrEqual(0);
    expect(liveBubbleText.indexOf("Still streaming the next sentence...")).toBeGreaterThan(
      liveBubbleText.indexOf("Drafting the first batch now.")
    );
    expect(document.querySelector("article.agent-message-streaming")).toHaveClass("agent-message-assistant");
    expect(document.querySelector("article.agent-message-streaming")).not.toHaveClass("agent-message-user");
  });
});
