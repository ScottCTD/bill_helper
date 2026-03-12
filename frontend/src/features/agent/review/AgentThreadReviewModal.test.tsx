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
      user_memory: null,
      default_currency_code: "USD",
      dashboard_currency_code: "USD",
      agent_model: "gpt-test",
      entry_tagging_model: null,
      available_agent_models: ["gpt-test"],
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
        user_memory: null,
        default_currency_code: null,
        dashboard_currency_code: null,
        agent_model: null,
        entry_tagging_model: null,
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
      }
    });
    vi.mocked(listCurrencies).mockResolvedValue([
      { code: "USD", name: "US Dollar", entry_count: 1, is_placeholder: false },
      { code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }
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
          id: "change-pending-account",
          run_id: "run-pending",
          change_type: "create_account",
          payload_json: {
            name: "Savings Vault",
            currency_code: "USD",
            is_active: true,
            markdown_body: "Savings notes"
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
        onReopenItem={vi.fn()}
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
    expect(within(pendingSection).getByText("Accounts")).toBeInTheDocument();
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
        onReopenItem={vi.fn()}
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
        onReopenItem={vi.fn()}
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
            target: {
              target_type: "entry",
              entry_ref: {
                entry_id: "entry-1234"
              }
            },
            member_role: "CHILD",
            group_preview: {
              name: "Monthly Bills",
              group_type: "SPLIT"
            },
            member_preview: {
              date: "2026-03-01",
              kind: "EXPENSE",
              name: "March Rent",
              amount_minor: 250000,
              currency_code: "USD",
              from_entity: "Main Checking",
              to_entity: "Landlord",
              tags: ["housing"],
              markdown_notes: "Statement imported"
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
        onReopenItem={vi.fn()}
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
    expect(screen.getByLabelText("Parent group")).toHaveValue("Monthly Bills");
    expect(screen.getByLabelText("Parent group type")).toHaveValue("SPLIT");
    expect(screen.getByLabelText("Date")).toHaveValue("2026-03-01");
    expect(screen.getByLabelText("Name")).toHaveValue("March Rent");
    expect(screen.getByLabelText("Amount")).toHaveValue(2500);
    expect(screen.queryByLabelText("Parent group ref")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Entry ref")).not.toBeInTheDocument();
    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes.at(-1)).toHaveValue("CHILD");
  });

  it("hides dependency chips once the referenced proposal is already applied", async () => {
    const run = buildRun({
      id: "run-group",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "proposal-group-create",
          run_id: "run-group",
          change_type: "create_group",
          status: "APPLIED",
          applied_resource_type: "group",
          applied_resource_id: "group-1",
          payload_json: {
            name: "Payroll Deposit",
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
            target: {
              target_type: "entry",
              entry_ref: {
                entry_id: "entry-1234"
              }
            },
            member_role: null,
            group_preview: {
              name: "Payroll Deposit",
              group_type: "RECURRING"
            },
            member_preview: {
              date: "2026-01-15",
              kind: "INCOME",
              name: "Payroll Deposit",
              amount_minor: 179739,
              currency_code: "CAD",
              from_entity: "Employer",
              to_entity: "Checking",
              tags: ["salary_wages"],
              markdown_notes: "Payroll deposit"
            }
          }
        })
      ]
    });

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[run]}
        onOpenChange={() => undefined}
        onApproveItem={vi.fn()}
        onRejectItem={vi.fn()}
        onReopenItem={vi.fn()}
      />
    );

    const proposalButtons = await screen.findAllByText("Add Group Member: Payroll Deposit -> Payroll Deposit");
    await userEvent.click(proposalButtons[0]);

    expect(screen.queryByText("Parent group dependency")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Parent group")).toHaveValue("Payroll Deposit");
  });

  it("lets reviewers reopen rejected editable items with payload overrides", async () => {
    const run = buildRun({
      id: "run-tag",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "proposal-tag",
          run_id: "run-tag",
          change_type: "create_tag",
          status: "REJECTED",
          payload_json: {
            name: "subscriptions",
            type: "recurring"
          }
        })
      ]
    });
    const onReopenItem = vi.fn().mockResolvedValue({
      ...run.change_items[0],
      status: "PENDING_REVIEW",
      payload_json: {
        name: "streaming",
        type: "media"
      }
    });

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[run]}
        onOpenChange={() => undefined}
        onApproveItem={vi.fn()}
        onRejectItem={vi.fn()}
        onReopenItem={onReopenItem}
      />
    );

    const nameInput = await screen.findByLabelText("Name");
    const typeInput = screen.getByLabelText("Type");

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Streaming");
    await userEvent.clear(typeInput);
    await userEvent.type(typeInput, "Media");
    await userEvent.click(screen.getByRole("button", { name: "Move to Pending" }));

    await waitFor(() =>
      expect(onReopenItem).toHaveBeenCalledWith({
        itemId: "proposal-tag",
        payloadOverride: {
          name: "streaming",
          type: "Media"
        }
      })
    );
  });

  it("serializes account review edits into payload overrides", async () => {
    const run = buildRun({
      id: "run-account",
      created_at: "2026-03-06T10:00:00Z",
      change_items: [
        buildChangeItem({
          id: "proposal-account",
          run_id: "run-account",
          change_type: "create_account",
          payload_json: {
            name: "Travel Card",
            currency_code: "USD",
            is_active: true,
            markdown_body: null
          }
        })
      ]
    });
    const onApproveItem = vi.fn().mockResolvedValue({
      ...run.change_items[0],
      status: "APPLIED",
      applied_resource_type: "account",
      applied_resource_id: "account-1"
    });

    renderWithQueryClient(
      <AgentThreadReviewModal
        open
        runs={[run]}
        onOpenChange={() => undefined}
        onApproveItem={onApproveItem}
        onRejectItem={vi.fn()}
        onReopenItem={vi.fn()}
      />
    );

    const nameInput = await screen.findByLabelText("Name");
    const currencySelect = screen.getByLabelText("Currency");
    const statusSelect = screen.getByLabelText("Status");
    const notesInput = screen.getByLabelText("Notes");

    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Travel Card CAD");
    await userEvent.selectOptions(currencySelect, "CAD");
    await userEvent.selectOptions(statusSelect, "inactive");
    await userEvent.type(notesInput, "Trip only");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(onApproveItem).toHaveBeenCalledWith({
        itemId: "proposal-account",
        payloadOverride: {
          name: "Travel Card CAD",
          currency_code: "CAD",
          is_active: false,
          markdown_body: "Trip only"
        }
      })
    );
  });
});
