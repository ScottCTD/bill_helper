import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getRuntimeSettings, listCurrencies, listEntities, listTags } from "../../../lib/api";
import { buildChangeItem, buildRun } from "../../../test/factories/agent";
import { renderWithQueryClient } from "../../../test/renderWithQueryClient";
import { AgentThreadReviewModal } from "./AgentThreadReviewModal";

vi.mock("../../../lib/api", () => ({
  listCurrencies: vi.fn(),
  listEntities: vi.fn(),
  listTags: vi.fn(),
  getRuntimeSettings: vi.fn()
}));

describe("AgentThreadReviewModal", () => {
  beforeEach(() => {
    vi.mocked(getRuntimeSettings).mockResolvedValue({
      current_user_name: "Admin",
      user_memory: null,
      default_currency_code: "USD",
      dashboard_currency_code: "USD",
      agent_model: "gpt-test",
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
      overrides: {
        current_user_name: null,
        user_memory: null,
        default_currency_code: null,
        dashboard_currency_code: null,
        agent_model: null,
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
      }
    });
    vi.mocked(listCurrencies).mockResolvedValue([
      { code: "USD", name: "US Dollar", entry_count: 1, is_placeholder: false }
    ]);
    vi.mocked(listEntities).mockResolvedValue([
      { id: "entity-1", name: "Main Checking", category: "account", is_account: true },
      { id: "entity-2", name: "Cafe", category: "merchant", is_account: false }
    ]);
    vi.mocked(listTags).mockResolvedValue([
      { id: 1, name: "food", color: "#7fb069", type: "daily" }
    ]);
  });

  it("renders pending and resolved sections and lets the user navigate from the toc", async () => {
    const pendingRun = buildRun({
      id: "run-pending",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "change-pending",
          run_id: "run-pending",
          change_type: "create_entry",
          payload_json: {
            kind: "EXPENSE",
            date: "2026-03-05",
            name: "Lunch",
            amount_minor: 1200,
            currency_code: "USD",
            from_entity: "Main Checking",
            to_entity: "Cafe",
            tags: ["food"]
          }
        }),
        buildChangeItem({
          id: "change-pending-entity",
          run_id: "run-pending",
          change_type: "create_entity",
          payload_json: {
            name: "Savings Vault",
            category: "account"
          }
        }),
        buildChangeItem({
          id: "change-pending-tag",
          run_id: "run-pending",
          change_type: "create_tag",
          payload_json: {
            name: "travel",
            type: "trip"
          }
        })
      ]
    });
    const resolvedRun = buildRun({
      id: "run-resolved",
      created_at: "2026-03-06T10:05:00Z",
      change_items: [
        buildChangeItem({
          id: "change-resolved",
          run_id: "run-resolved",
          change_type: "delete_tag",
          status: "REJECTED",
          payload_json: {
            name: "groceries",
            target: {
              name: "groceries"
            }
          }
        })
      ]
    });

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[pendingRun, resolvedRun]}
        onOpenChange={() => undefined}
        onApproveItem={vi.fn()}
        onRejectItem={vi.fn()}
      />
    );

    expect(await screen.findByText("Thread review")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Reviewed / Failed")).toBeInTheDocument();
    expect(screen.queryByText(/Review proposals across the whole thread/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("PENDING_REVIEW")).toHaveLength(1);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveClass("w-[96vw]", "max-w-none", "xl:w-[78rem]", "p-0");

    const controlsBar = dialog.querySelector(".agent-review-controls-bar");
    expect(controlsBar).not.toBeNull();
    expect(within(controlsBar as HTMLElement).getByRole("button", { name: "Approve All" })).toBeInTheDocument();
    expect(within(controlsBar as HTMLElement).getByRole("button", { name: "Previous" })).toBeInTheDocument();
    expect(within(controlsBar as HTMLElement).getByRole("button", { name: "Hide list" })).toHaveAttribute("aria-expanded", "true");

    const sidebar = dialog.querySelector(".agent-review-sidebar");
    expect(sidebar).not.toBeNull();
    expect(within(sidebar as HTMLElement).queryByRole("button", { name: "Approve All" })).not.toBeInTheDocument();
    const pendingSection = within(sidebar as HTMLElement).getByLabelText("Pending");
    expect(within(pendingSection).getByText("Entries")).toBeInTheDocument();
    expect(within(pendingSection).getByText("Entities")).toBeInTheDocument();
    expect(within(pendingSection).getByText("Tags")).toBeInTheDocument();
    expect(within(sidebar as HTMLElement).queryByText("REJECTED")).not.toBeInTheDocument();
    expect(within(sidebar as HTMLElement).getByLabelText("Rejected")).toBeInTheDocument();
    expect(dialog.querySelector(".agent-review-sidebar-scroll")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Create Entry: Lunch on 2026-03-05" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Hide list" }));
    expect(screen.getByRole("button", { name: "Show list" })).toHaveAttribute("aria-expanded", "false");
    expect(dialog.querySelector(".agent-review-sidebar")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Show list" }));
    expect(await screen.findByRole("button", { name: "Hide list" })).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(screen.getByText("Delete Tag: groceries"));

    expect(screen.getByRole("heading", { name: "Delete Tag: groceries" })).toBeInTheDocument();
    expect(screen.getAllByText("REJECTED").length).toBeGreaterThan(0);
  });

  it("auto-advances to the next pending proposal after approval", async () => {
    const firstRun = buildRun({
      id: "run-1",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "change-1",
          run_id: "run-1",
          change_type: "create_tag",
          payload_json: {
            name: "subscriptions",
            type: "recurring"
          }
        }),
        buildChangeItem({
          id: "change-2",
          run_id: "run-1",
          change_type: "create_entity",
          payload_json: {
            name: "Molly Tea",
            category: "merchant"
          }
        })
      ]
    });
    const onApproveItem = vi
      .fn()
      .mockResolvedValueOnce({
        ...firstRun.change_items[0],
        status: "APPLIED",
        applied_resource_type: "tag",
        applied_resource_id: "1"
      });

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[firstRun]}
        onOpenChange={() => undefined}
        onApproveItem={onApproveItem}
        onRejectItem={vi.fn()}
      />
    );

    expect(await screen.findByRole("heading", { name: "Create Tag: subscriptions" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Create Entity: Molly Tea" })).toBeInTheDocument());
    expect(onApproveItem).toHaveBeenCalledWith({
      itemId: "change-1",
      payloadOverride: undefined
    });
  });

  it("ignores keyboard approve shortcuts while focus is inside an editor field", async () => {
    const run = buildRun({
      id: "run-1",
      created_at: "2026-03-06T10:00:00Z",
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
    });
    const onApproveItem = vi.fn();

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[run]}
        onOpenChange={() => undefined}
        onApproveItem={onApproveItem}
        onRejectItem={vi.fn()}
      />
    );

    const nameInput = await screen.findByLabelText("Name");
    nameInput.focus();
    await userEvent.keyboard("a");

    expect(onApproveItem).not.toHaveBeenCalled();
  });

  it("renders group proposal editors and dependency chips", async () => {
    const run = buildRun({
      id: "run-group",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "proposal-group-create",
          run_id: "run-group",
          change_type: "create_group",
          payload_json: {
            name: "Monthly Bills",
            group_type: "RECURRING"
          }
        }),
        buildChangeItem({
          id: "proposal-group-member",
          run_id: "run-group",
          change_type: "create_group_member",
          payload_json: {
            action: "add",
            group_ref: {
              create_group_proposal_id: "proposal-group-create"
            },
            entry_ref: {
              entry_id: "entry-1234"
            },
            child_group_ref: null,
            member_role: "CHILD",
            group_preview: {
              name: "Monthly Bills",
              group_type: "SPLIT"
            },
            member_preview: {
              name: "March Rent"
            }
          }
        })
      ]
    });
    const onApproveItem = vi.fn().mockResolvedValue(run.change_items[1]);

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[run]}
        onOpenChange={() => undefined}
        onApproveItem={onApproveItem}
        onRejectItem={vi.fn()}
      />
    );

    const dialog = await screen.findByRole("dialog");
    const pendingSection = within(dialog.querySelector(".agent-review-sidebar") as HTMLElement).getByLabelText("Pending");
    expect(within(pendingSection).getByText("Groups")).toBeInTheDocument();

    expect(screen.getByLabelText("Group name")).toHaveValue("Monthly Bills");
    expect(screen.getByLabelText("Group type")).toHaveValue("RECURRING");

    await userEvent.click(screen.getByText("Add Group Member: Monthly Bills -> March Rent"));

    expect(screen.getByText("Parent group dependency")).toBeInTheDocument();
    expect(screen.getAllByText("Create Group: Monthly Bills").length).toBeGreaterThan(0);
    expect(screen.getByRole("combobox")).toHaveValue("CHILD");
  });
});
