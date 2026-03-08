import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { renderWithQueryClient } from "../../test/renderWithQueryClient";
import { buildChangeItem, buildRun, buildRunEvent, buildToolCall } from "../../test/factories/agent";
import { AgentPanel } from "./AgentPanel";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    approveAgentChangeItem: vi.fn(),
    createAgentThread: vi.fn(),
    deleteAgentThread: vi.fn(),
    getAgentThread: vi.fn(),
    getAgentToolCall: vi.fn(),
    getRuntimeSettings: vi.fn(),
    interruptAgentRun: vi.fn(),
    listAgentThreads: vi.fn(),
    listCurrencies: vi.fn(),
    listEntities: vi.fn(),
    listTags: vi.fn(),
    reopenAgentChangeItem: vi.fn(),
    renameAgentThread: vi.fn(),
    rejectAgentChangeItem: vi.fn(),
    sendAgentMessage: vi.fn(),
    streamAgentMessage: vi.fn()
  };
});

function buildThreadSummary(overrides: Partial<Awaited<ReturnType<typeof api.listAgentThreads>>[number]> = {}) {
  return {
    id: overrides.id ?? "thread-1",
    title: overrides.title ?? "Review thread",
    created_at: overrides.created_at ?? "2026-03-06T10:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-06T10:05:00Z",
    last_message_preview: overrides.last_message_preview ?? "Latest update",
    pending_change_count: overrides.pending_change_count ?? 1,
    has_running_run: overrides.has_running_run ?? false
  };
}

function buildThreadDetail(runs: ReturnType<typeof buildRun>[]) {
  return {
    thread: {
      id: "thread-1",
      title: "Review thread",
      created_at: "2026-03-06T10:00:00Z",
      updated_at: "2026-03-06T10:05:00Z"
    },
    messages: [],
    runs,
    configured_model_name: "gpt-test",
    current_context_tokens: 42
  };
}

type RuntimeSettingsResponse = Awaited<ReturnType<typeof api.getRuntimeSettings>>;
type RuntimeSettingsOverrideInput = Partial<Omit<RuntimeSettingsResponse, "overrides">> & {
  overrides?: Partial<RuntimeSettingsResponse["overrides"]>;
};

function buildRuntimeSettings(overrides: RuntimeSettingsOverrideInput = {}) {
  const baseOverrides: RuntimeSettingsResponse["overrides"] = {
    current_user_name: null,
    user_memory: null,
    default_currency_code: null,
    dashboard_currency_code: null,
    agent_model: null,
    available_agent_models: null,
    agent_max_steps: null,
    agent_bulk_max_concurrent_threads: null,
    agent_retry_max_attempts: null,
    agent_retry_initial_wait_seconds: null,
    agent_retry_max_wait_seconds: null,
    agent_retry_backoff_multiplier: null,
    agent_max_image_size_bytes: null,
    agent_max_images_per_message: null,
    agent_base_url: null,
    agent_api_key_configured: true
  };

  return {
    current_user_name: "Admin",
    user_memory: null,
    default_currency_code: "USD",
    dashboard_currency_code: "USD",
    agent_model: "gpt-test",
    available_agent_models: ["gpt-test", "openai/gpt-4.1-mini", "openrouter/qwen/qwen3.5-27b"],
    agent_max_steps: 8,
    agent_bulk_max_concurrent_threads: 4,
    agent_retry_max_attempts: 3,
    agent_retry_initial_wait_seconds: 1,
    agent_retry_max_wait_seconds: 10,
    agent_retry_backoff_multiplier: 2,
    agent_max_image_size_bytes: 1000000,
    agent_max_images_per_message: 5,
    agent_base_url: null,
    agent_api_key_configured: true,
    ...overrides,
    overrides: {
      ...baseOverrides,
      ...overrides.overrides
    }
  };
}

function buildPdfFile(name: string) {
  return new File(["%PDF-1.7"], name, { type: "application/pdf" });
}

describe("AgentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.createAgentThread).mockResolvedValue({
      id: "thread-created",
      title: null,
      created_at: "2026-03-06T10:00:00Z",
      updated_at: "2026-03-06T10:00:00Z"
    });
    vi.mocked(api.listCurrencies).mockResolvedValue([
      { code: "USD", name: "US Dollar", entry_count: 1, is_placeholder: false }
    ]);
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "entity-1", name: "Main Checking", category: "account", is_account: true }
    ]);
    vi.mocked(api.listTags).mockResolvedValue([
      { id: 1, name: "food", color: "#7fb069", type: "daily" }
    ]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(buildRuntimeSettings());
    vi.mocked(api.getAgentToolCall).mockResolvedValue(
      buildRun({}).tool_calls[0] ?? {
        id: "tool-call-1",
        run_id: "run-1",
        llm_tool_call_id: null,
        tool_name: "list_entries",
        input_json: {},
        output_json: {},
        output_text: "",
        has_full_payload: true,
        status: "ok",
        created_at: "2026-03-06T10:00:00Z",
        started_at: "2026-03-06T10:00:00Z",
        completed_at: "2026-03-06T10:00:00Z"
      }
    );
    vi.mocked(api.approveAgentChangeItem).mockResolvedValue(
      buildChangeItem({ status: "APPLIED", applied_resource_type: "tag", applied_resource_id: "1" })
    );
    vi.mocked(api.rejectAgentChangeItem).mockResolvedValue(buildChangeItem({ status: "REJECTED" }));
    vi.mocked(api.reopenAgentChangeItem).mockResolvedValue(buildChangeItem({ status: "PENDING_REVIEW" }));
    vi.mocked(api.deleteAgentThread).mockResolvedValue();
    vi.mocked(api.interruptAgentRun).mockResolvedValue(buildRun({ status: "failed", error_text: "Run interrupted by user." }));
    vi.mocked(api.renameAgentThread).mockResolvedValue({
      id: "thread-1",
      title: "Review thread",
      created_at: "2026-03-06T10:00:00Z",
      updated_at: "2026-03-06T10:05:00Z"
    });
    vi.mocked(api.sendAgentMessage).mockResolvedValue(
      buildRun({
        status: "running",
        assistant_message_id: null,
        completed_at: null
      })
    );
    vi.mocked(api.streamAgentMessage).mockResolvedValue();
  });

  it("opens the thread review modal from the header button", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({
          id: "run-1",
          assistant_message_id: null,
          change_items: [
            buildChangeItem({
              id: "change-1",
              run_id: "run-1",
              change_type: "create_tag",
              payload_json: {
                name: "subscriptions",
                type: "recurring"
              }
            })
          ]
        })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const reviewButton = await screen.findByRole("button", { name: /Review/i });
    await waitFor(() => expect(reviewButton).toBeEnabled());

    await userEvent.click(reviewButton);

    expect(await screen.findByText("Thread review")).toBeInTheDocument();
  });

  it("keeps the header review button disabled when the thread has no proposals", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary({ pending_change_count: 0 })]);
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({
          id: "run-1",
          assistant_message_id: null,
          change_items: []
        })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const reviewButton = await screen.findByRole("button", { name: "Review" });

    await waitFor(() => expect(reviewButton).toBeDisabled());
  });

  it("uses the pending review styling and shows a readable count badge", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary({ pending_change_count: 2 })]);
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({
          id: "run-1",
          assistant_message_id: null,
          change_items: [
            buildChangeItem({ id: "change-1", run_id: "run-1", status: "PENDING_REVIEW" }),
            buildChangeItem({ id: "change-2", run_id: "run-1", status: "PENDING_REVIEW" })
          ]
        })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const reviewButton = await screen.findByRole("button", { name: /Review/i });
    await waitFor(() => expect(reviewButton).toBeEnabled());
    expect(reviewButton).toHaveClass("agent-panel-review-button", "is-pending");

    const countBadge = screen.getByText("2");
    expect(countBadge).toHaveClass("agent-panel-review-badge");
  });

  it("shows Bulk mode help only in a tooltip and still requires at least one file", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));

    renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await userEvent.hover(screen.getByRole("button", { name: "Bulk mode help" }));

    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Each file starts a fresh thread using only the prompt typed here. Current thread history is not included."
    );

    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    expect(await screen.findByText("Attach at least one file to start Bulk mode.")).toBeInTheDocument();
    expect(api.sendAgentMessage).not.toHaveBeenCalled();
  });

  it("starts one fresh thread per file in Bulk mode without reusing the selected thread", async () => {
    let createCount = 0;
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.createAgentThread).mockImplementation(async ({ title } = {}) => {
      createCount += 1;
      return {
        id: `thread-created-${createCount}`,
        title: title ?? null,
        created_at: `2026-03-06T10:00:0${createCount}Z`,
        updated_at: `2026-03-06T10:00:0${createCount}Z`
      };
    });

    const { container } = renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const fileInput = container.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Expected file input");
    }

    await userEvent.upload(fileInput, [buildPdfFile("statement-january.pdf"), buildPdfFile("statement-february.pdf")]);
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));
    await userEvent.type(screen.getByRole("textbox"), "Review this statement");
    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    await waitFor(() => expect(api.createAgentThread).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Started 2 threads.")).toBeInTheDocument();
    expect(api.streamAgentMessage).not.toHaveBeenCalled();
    expect(vi.mocked(api.sendAgentMessage).mock.calls).toEqual([
      [
        {
          threadId: "thread-created-1",
          content: "Review this statement",
          files: [expect.objectContaining({ name: "statement-january.pdf" })],
          modelName: "gpt-test"
        }
      ],
      [
        {
          threadId: "thread-created-2",
          content: "Review this statement",
          files: [expect.objectContaining({ name: "statement-february.pdf" })],
          modelName: "gpt-test"
        }
      ]
    ]);
    expect(
      vi.mocked(api.getAgentThread).mock.calls.some(([threadId]) => threadId === "thread-created-1" || threadId === "thread-created-2")
    ).toBe(false);
  });

  it("caps Bulk mode launches at four concurrent sends", async () => {
    let createCount = 0;
    let activeSends = 0;
    let maxActiveSends = 0;
    const sendResolvers: Array<() => void> = [];

    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.createAgentThread).mockImplementation(async ({ title } = {}) => {
      createCount += 1;
      return {
        id: `thread-created-${createCount}`,
        title: title ?? null,
        created_at: `2026-03-06T10:00:${String(createCount).padStart(2, "0")}Z`,
        updated_at: `2026-03-06T10:00:${String(createCount).padStart(2, "0")}Z`
      };
    });
    vi.mocked(api.sendAgentMessage).mockImplementation(
      ({ threadId }) =>
        new Promise((resolve) => {
          activeSends += 1;
          maxActiveSends = Math.max(maxActiveSends, activeSends);
          sendResolvers.push(() => {
            activeSends -= 1;
            resolve(
              buildRun({
                thread_id: threadId,
                status: "running",
                assistant_message_id: null,
                completed_at: null
              })
            );
          });
        })
    );

    const { container } = renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const fileInput = container.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Expected file input");
    }

    await userEvent.upload(
      fileInput,
      Array.from({ length: 6 }, (_, index) => buildPdfFile(`statement-${index + 1}.pdf`))
    );
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));
    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(4));
    expect(maxActiveSends).toBe(4);

    await act(async () => {
      sendResolvers.shift()?.();
    });

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(5));

    await act(async () => {
      sendResolvers.shift()?.();
    });

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(6));

    await act(async () => {
      sendResolvers.splice(0).forEach((resolve) => resolve());
    });
  });

  it("uses the runtime settings Bulk concurrency limit", async () => {
    let createCount = 0;
    let activeSends = 0;
    let maxActiveSends = 0;
    const sendResolvers: Array<() => void> = [];

    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        agent_bulk_max_concurrent_threads: 2,
        overrides: { agent_bulk_max_concurrent_threads: 2 }
      })
    );
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.createAgentThread).mockImplementation(async ({ title } = {}) => {
      createCount += 1;
      return {
        id: `thread-created-${createCount}`,
        title: title ?? null,
        created_at: `2026-03-06T10:00:${String(createCount).padStart(2, "0")}Z`,
        updated_at: `2026-03-06T10:00:${String(createCount).padStart(2, "0")}Z`
      };
    });
    vi.mocked(api.sendAgentMessage).mockImplementation(
      ({ threadId }) =>
        new Promise((resolve) => {
          activeSends += 1;
          maxActiveSends = Math.max(maxActiveSends, activeSends);
          sendResolvers.push(() => {
            activeSends -= 1;
            resolve(
              buildRun({
                thread_id: threadId,
                status: "running",
                assistant_message_id: null,
                completed_at: null
              })
            );
          });
        })
    );

    const { container } = renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const fileInput = container.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Expected file input");
    }

    await userEvent.upload(
      fileInput,
      Array.from({ length: 4 }, (_, index) => buildPdfFile(`statement-${index + 1}.pdf`))
    );
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));
    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(2));
    expect(maxActiveSends).toBe(2);

    await act(async () => {
      sendResolvers.splice(0).forEach((resolve) => resolve());
    });

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(4));

    await act(async () => {
      sendResolvers.splice(0).forEach((resolve) => resolve());
    });
  });

  it("preserves failed files and the shared prompt after a partial Bulk mode failure", async () => {
    let createCount = 0;
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.createAgentThread).mockImplementation(async ({ title } = {}) => {
      createCount += 1;
      return {
        id: `thread-created-${createCount}`,
        title: title ?? null,
        created_at: `2026-03-06T10:00:0${createCount}Z`,
        updated_at: `2026-03-06T10:00:0${createCount}Z`
      };
    });
    vi.mocked(api.sendAgentMessage)
      .mockResolvedValueOnce(
        buildRun({
          thread_id: "thread-created-1",
          status: "running",
          assistant_message_id: null,
          completed_at: null
        })
      )
      .mockRejectedValueOnce(new Error("provider unavailable"));

    const { container } = renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const fileInput = container.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Expected file input");
    }

    await userEvent.upload(fileInput, [buildPdfFile("statement-ok.pdf"), buildPdfFile("statement-fail.pdf")]);
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));
    const composer = screen.getByRole("textbox");
    await userEvent.type(composer, "Use this shared prompt");
    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    expect(await screen.findByText("Started 1 thread. Failed 1.")).toBeInTheDocument();
    expect(screen.getByText("Files: statement-fail.pdf provider unavailable")).toBeInTheDocument();
    expect(screen.getByText("provider unavailable")).toBeInTheDocument();
    expect(composer).toHaveValue("Use this shared prompt");
    expect(screen.queryByText("statement-ok.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("statement-fail.pdf")).toBeInTheDocument();
    expect(api.deleteAgentThread).toHaveBeenCalledWith("thread-created-2");
  });

  it("updates the thread title immediately when rename_thread streams", async () => {
    let resolveStream: (() => void) | null = null;

    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getAgentThread)
      .mockResolvedValueOnce(buildThreadDetail([]))
      .mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.getAgentToolCall).mockResolvedValue(
      buildToolCall({
        id: "tool-call-rename",
        run_id: "run-1",
        tool_name: "rename_thread",
        input_json: { title: "Budget Review" },
        output_json: { status: "OK", title: "Budget Review" },
        output_text: "OK\nsummary: renamed thread to Budget Review",
        has_full_payload: true,
        status: "ok"
      })
    );
    vi.mocked(api.streamAgentMessage).mockImplementation(async ({ onEvent }) => {
      await act(async () => {
        onEvent({
          type: "run_event",
          run_id: "run-1",
          event: buildRunEvent({
            id: "event-started",
            run_id: "run-1",
            event_type: "tool_call_started",
            tool_call_id: "tool-call-rename"
          }),
          tool_call: buildToolCall({
            id: "tool-call-rename",
            run_id: "run-1",
            tool_name: "rename_thread",
            has_full_payload: false,
            input_json: null,
            output_json: null,
            output_text: null,
            status: "running"
          })
        });
      });
      await new Promise<void>((resolve) => {
        resolveStream = resolve;
      });
    });

    renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const composer = await screen.findByPlaceholderText(
      "Ask a question or ask the agent to propose entries/tags/entities..."
    );
    await userEvent.type(composer, "Rename the thread");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(api.getAgentToolCall).toHaveBeenCalledWith("tool-call-rename"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Budget Review" })).toBeInTheDocument());

    await act(async () => {
      resolveStream?.();
    });
  });

  it("initializes the composer model picker from the latest thread run model", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        agent_model: "bedrock/us.anthropic.claude-sonnet-4-6",
        available_agent_models: ["bedrock/us.anthropic.claude-sonnet-4-6", "openai/gpt-4.1-mini"],
        overrides: { agent_model: "bedrock/us.anthropic.claude-sonnet-4-6" }
      })
    );
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({ model_name: "openai/gpt-4.1-mini" })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const modelPicker = await screen.findByRole("combobox", { name: "Agent model" });
    await waitFor(() => expect(modelPicker).toHaveValue("openai/gpt-4.1-mini"));
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "bedrock/us.anthropic.claude-sonnet-4-6",
      "openai/gpt-4.1-mini"
    ]);
  });

  it("keeps the composer model picker empty when no models are available", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        agent_model: "bedrock/us.anthropic.claude-sonnet-4-6",
        available_agent_models: []
      })
    );
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({ model_name: "openai/gpt-4.1-mini" })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const modelPicker = await screen.findByRole("combobox", { name: "Agent model" });

    await waitFor(() => expect(modelPicker).toHaveValue(""));
    expect(modelPicker).toBeDisabled();
    expect(screen.getByRole("option", { name: "Loading models…" })).toBeInTheDocument();
  });

  it("updates the header model label immediately when the composer model picker changes", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        agent_model: "gpt-test",
        available_agent_models: ["gpt-test", "openai/gpt-4.1-mini"]
      })
    );
    vi.mocked(api.getAgentThread).mockResolvedValue(
      buildThreadDetail([
        buildRun({ model_name: "openai/gpt-4.1-mini" })
      ])
    );

    renderWithQueryClient(<AgentPanel isOpen />);

    const modelPicker = await screen.findByRole("combobox", { name: "Agent model" });
    await waitFor(() => expect(modelPicker).toHaveValue("openai/gpt-4.1-mini"));
    expect(await screen.findByRole("heading", { name: "Agent (openai/gpt-4.1-mini)" })).toBeInTheDocument();

    await userEvent.selectOptions(modelPicker, "gpt-test");

    expect(screen.getByRole("heading", { name: "Agent (gpt-test)" })).toBeInTheDocument();
  });

  it("uses the selected composer model for the next streamed send", async () => {
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        agent_model: "bedrock/us.anthropic.claude-sonnet-4-6",
        available_agent_models: ["bedrock/us.anthropic.claude-sonnet-4-6", "openai/gpt-4.1-mini"]
      })
    );
    vi.mocked(api.getAgentThread)
      .mockResolvedValueOnce(buildThreadDetail([]))
      .mockResolvedValue(buildThreadDetail([]));

    renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Agent model" }), "openai/gpt-4.1-mini");
    await userEvent.type(screen.getByRole("textbox"), "Use the faster model next");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(api.streamAgentMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          threadId: "thread-1",
          content: "Use the faster model next",
          modelName: "openai/gpt-4.1-mini"
        })
      )
    );
  });

  it("uses the selected composer model for bulk send requests", async () => {
    let createCount = 0;
    vi.mocked(api.listAgentThreads).mockResolvedValue([buildThreadSummary()]);
    vi.mocked(api.getRuntimeSettings).mockResolvedValue(
      buildRuntimeSettings({
        available_agent_models: ["gpt-test", "openai/gpt-4.1-mini"]
      })
    );
    vi.mocked(api.getAgentThread).mockResolvedValue(buildThreadDetail([]));
    vi.mocked(api.createAgentThread).mockImplementation(async ({ title } = {}) => {
      createCount += 1;
      return {
        id: `thread-created-${createCount}`,
        title: title ?? null,
        created_at: `2026-03-06T10:00:0${createCount}Z`,
        updated_at: `2026-03-06T10:00:0${createCount}Z`
      };
    });

    const { container } = renderWithQueryClient(<AgentPanel isOpen />);

    await screen.findByRole("button", { name: "Review thread" });
    const fileInput = container.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement)) {
      throw new Error("Expected file input");
    }

    await userEvent.upload(fileInput, [buildPdfFile("statement.pdf")]);
    await userEvent.click(screen.getByRole("switch", { name: "Bulk mode" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Agent model" }), "openai/gpt-4.1-mini");
    await userEvent.type(screen.getByRole("textbox"), "Review this statement");
    await userEvent.click(screen.getByRole("button", { name: "Start Bulk" }));

    await waitFor(() => expect(api.sendAgentMessage).toHaveBeenCalledTimes(1));
    expect(api.sendAgentMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "thread-created-1",
        content: "Review this statement",
        modelName: "openai/gpt-4.1-mini"
      })
    );
  });
});
