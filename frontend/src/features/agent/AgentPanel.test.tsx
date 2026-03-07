import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { renderWithQueryClient } from "../../test/renderWithQueryClient";
import { buildChangeItem, buildRun } from "../../test/factories/agent";
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
    rejectAgentChangeItem: vi.fn(),
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

describe("AgentPanel", () => {
  beforeEach(() => {
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
    vi.mocked(api.getRuntimeSettings).mockResolvedValue({
      current_user_name: "Admin",
      user_memory: null,
      default_currency_code: "USD",
      dashboard_currency_code: "USD",
      agent_model: "gpt-test",
      agent_max_steps: 8,
      agent_retry_max_attempts: 3,
      agent_retry_initial_wait_seconds: 1,
      agent_retry_max_wait_seconds: 10,
      agent_retry_backoff_multiplier: 2,
      agent_max_image_size_bytes: 1000000,
      agent_max_images_per_message: 5,
      agent_base_url: null,
      agent_api_key_configured: true,
      overrides: {
        current_user_name: null,
        user_memory: null,
        default_currency_code: null,
        dashboard_currency_code: null,
        agent_model: null,
        agent_max_steps: null,
        agent_retry_max_attempts: null,
        agent_retry_initial_wait_seconds: null,
        agent_retry_max_wait_seconds: null,
        agent_retry_backoff_multiplier: null,
        agent_max_image_size_bytes: null,
        agent_max_images_per_message: null,
        agent_base_url: null,
        agent_api_key_configured: true
      }
    });
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
    vi.mocked(api.deleteAgentThread).mockResolvedValue();
    vi.mocked(api.interruptAgentRun).mockResolvedValue(buildRun({ status: "failed", error_text: "Run interrupted by user." }));
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
});
