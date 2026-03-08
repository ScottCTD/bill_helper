import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountsPage } from "./AccountsPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { RuntimeSettings } from "../lib/types";
import {
  createAccount,
  createSnapshot,
  deleteAccount,
  getReconciliation,
  getRuntimeSettings,
  listAccounts,
  listCurrencies,
  listSnapshots,
  listUsers,
  updateAccount
} from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listAccounts: vi.fn(),
    listCurrencies: vi.fn(),
    listUsers: vi.fn(),
    getRuntimeSettings: vi.fn(),
    listSnapshots: vi.fn(),
    getReconciliation: vi.fn(),
    createAccount: vi.fn(),
    updateAccount: vi.fn(),
    createSnapshot: vi.fn(),
    deleteAccount: vi.fn()
  };
});

const runtimeSettingsFixture: RuntimeSettings = {
  current_user_name: "Alice",
  user_memory: null,
  default_currency_code: "CAD",
  dashboard_currency_code: "CAD",
  agent_model: "gpt-5",
  agent_max_steps: 20,
  agent_retry_max_attempts: 2,
  agent_retry_initial_wait_seconds: 1,
  agent_retry_max_wait_seconds: 8,
  agent_retry_backoff_multiplier: 2,
  agent_max_image_size_bytes: 5_000_000,
  agent_max_images_per_message: 4,
  agent_base_url: null,
  agent_api_key_configured: false,
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
    agent_api_key_configured: false
  }
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("AccountsPage", () => {
  it("creates an account from the dialog flow", async () => {
    vi.mocked(listAccounts).mockResolvedValue([
      {
        id: "acc-1",
        owner_user_id: "user-1",
        name: "Main",
        markdown_body: null,
        currency_code: "CAD",
        is_active: true,
        created_at: "2026-02-15T00:00:00Z",
        updated_at: "2026-02-15T00:00:00Z"
      }
    ]);
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true, account_count: 1, entry_count: 0 }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listSnapshots).mockResolvedValue([]);
    vi.mocked(getReconciliation).mockResolvedValue({
      account_id: "acc-1",
      account_name: "Main",
      currency_code: "CAD",
      as_of: "2026-02-15",
      ledger_balance_minor: 100_00,
      snapshot_balance_minor: 100_00,
      snapshot_at: "2026-02-15",
      delta_minor: 0
    });
    vi.mocked(createAccount).mockResolvedValue({
      id: "acc-2",
      owner_user_id: "user-1",
      name: "Travel Card",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(updateAccount).mockResolvedValue({
      id: "acc-1",
      owner_user_id: "user-1",
      name: "Main",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(createSnapshot).mockResolvedValue({
      id: "snap-1",
      account_id: "acc-1",
      snapshot_at: "2026-02-15",
      balance_minor: 100_00,
      note: null,
      created_at: "2026-02-15T00:00:00Z"
    });

    renderWithQueryClient(<AccountsPage />);

    await screen.findByText("Accounts");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    const createDialog = await screen.findByRole("dialog", { name: "Create Account" });
    const nameInput = within(createDialog).getByLabelText("Name");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Travel Card");
    await userEvent.click(within(createDialog).getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(createAccount).toHaveBeenCalled();
    });
    expect(vi.mocked(createAccount).mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({
        name: "Travel Card",
        currency_code: "CAD",
        is_active: true
      })
    );
  });

  it("opens account editing on row double-click and keeps delete isolated", async () => {
    vi.mocked(listAccounts).mockResolvedValue([
      {
        id: "acc-1",
        owner_user_id: "user-1",
        name: "Main",
        markdown_body: null,
        currency_code: "CAD",
        is_active: true,
        created_at: "2026-02-15T00:00:00Z",
        updated_at: "2026-02-15T00:00:00Z"
      }
    ]);
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true, account_count: 1, entry_count: 0 }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listSnapshots).mockResolvedValue([]);
    vi.mocked(getReconciliation).mockResolvedValue({
      account_id: "acc-1",
      account_name: "Main",
      currency_code: "CAD",
      as_of: "2026-02-15",
      ledger_balance_minor: 100_00,
      snapshot_balance_minor: 100_00,
      snapshot_at: "2026-02-15",
      delta_minor: 0
    });
    vi.mocked(updateAccount).mockResolvedValue({
      id: "acc-1",
      owner_user_id: "user-1",
      name: "Main",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(deleteAccount).mockResolvedValue(undefined);

    renderWithQueryClient(<AccountsPage />);

    const nameCell = await screen.findByText("Main");
    const row = nameCell.closest("tr");
    expect(row).not.toBeNull();
    if (!row) {
      throw new Error("Expected account row");
    }

    await userEvent.dblClick(row);
    const editDialog = await screen.findByRole("dialog", { name: "Edit Account" });
    expect(within(editDialog).getByLabelText("Name")).toHaveValue("Main");

    await userEvent.click(within(editDialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Edit Account" })).not.toBeInTheDocument();
    });

    await userEvent.dblClick(screen.getByRole("button", { name: "Delete account Main" }));
    expect(await screen.findByRole("dialog", { name: "Delete Main?" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Edit Account" })).not.toBeInTheDocument();
  });

  it("creates snapshots for the selected account", async () => {
    vi.mocked(listAccounts).mockResolvedValue([
      {
        id: "acc-1",
        owner_user_id: "user-1",
        name: "Main",
        markdown_body: null,
        currency_code: "CAD",
        is_active: true,
        created_at: "2026-02-15T00:00:00Z",
        updated_at: "2026-02-15T00:00:00Z"
      }
    ]);
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true, account_count: 1, entry_count: 0 }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listSnapshots).mockResolvedValue([]);
    vi.mocked(getReconciliation).mockResolvedValue({
      account_id: "acc-1",
      account_name: "Main",
      currency_code: "CAD",
      as_of: "2026-02-15",
      ledger_balance_minor: 100_00,
      snapshot_balance_minor: 100_00,
      snapshot_at: "2026-02-15",
      delta_minor: 0
    });
    vi.mocked(createAccount).mockResolvedValue({
      id: "acc-2",
      owner_user_id: "user-1",
      name: "Travel Card",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(updateAccount).mockResolvedValue({
      id: "acc-1",
      owner_user_id: "user-1",
      name: "Main",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(createSnapshot).mockResolvedValue({
      id: "snap-1",
      account_id: "acc-1",
      snapshot_at: "2026-02-16",
      balance_minor: 123_45,
      note: "manual",
      created_at: "2026-02-16T00:00:00Z"
    });

    renderWithQueryClient(<AccountsPage />);

    await screen.findByText("Main");
    const balanceInput = await screen.findByLabelText("Balance (CAD)");
    await userEvent.clear(balanceInput);
    await userEvent.type(balanceInput, "123.45");
    await userEvent.type(screen.getByLabelText("Note"), "manual");
    await userEvent.click(screen.getByRole("button", { name: "Add snapshot" }));

    await waitFor(() => {
      expect(createSnapshot).toHaveBeenCalled();
    });
    expect(vi.mocked(createSnapshot).mock.calls[0]?.[0]).toBe("acc-1");
    expect(vi.mocked(createSnapshot).mock.calls[0]?.[1]).toEqual(expect.objectContaining({ balance_minor: 12345, note: "manual" }));
  });

  it("deletes an account from the confirmation dialog", async () => {
    vi.mocked(listAccounts).mockResolvedValue([
      {
        id: "acc-1",
        owner_user_id: "user-1",
        name: "Main",
        markdown_body: null,
        currency_code: "CAD",
        is_active: true,
        created_at: "2026-02-15T00:00:00Z",
        updated_at: "2026-02-15T00:00:00Z"
      }
    ]);
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 0, is_placeholder: false }]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true, account_count: 1, entry_count: 0 }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listSnapshots).mockResolvedValue([]);
    vi.mocked(getReconciliation).mockResolvedValue({
      account_id: "acc-1",
      account_name: "Main",
      currency_code: "CAD",
      as_of: "2026-02-15",
      ledger_balance_minor: 100_00,
      snapshot_balance_minor: 100_00,
      snapshot_at: "2026-02-15",
      delta_minor: 0
    });
    vi.mocked(createAccount).mockResolvedValue({
      id: "acc-2",
      owner_user_id: "user-1",
      name: "Travel Card",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(updateAccount).mockResolvedValue({
      id: "acc-1",
      owner_user_id: "user-1",
      name: "Main",
      markdown_body: null,
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(createSnapshot).mockResolvedValue({
      id: "snap-1",
      account_id: "acc-1",
      snapshot_at: "2026-02-15",
      balance_minor: 100_00,
      note: null,
      created_at: "2026-02-15T00:00:00Z"
    });
    vi.mocked(deleteAccount).mockResolvedValue(undefined);

    renderWithQueryClient(<AccountsPage />);

    await screen.findByText("Main");
    await userEvent.click(screen.getByRole("button", { name: "Delete account Main" }));

    const deleteDialog = await screen.findByRole("dialog", { name: "Delete Main?" });
    expect(within(deleteDialog).getByText(/snapshot history for this account is deleted/i)).toBeInTheDocument();

    await userEvent.click(within(deleteDialog).getByRole("button", { name: "Delete account" }));

    await waitFor(() => {
      expect(vi.mocked(deleteAccount).mock.calls[0]?.[0]).toBe("acc-1");
    });
  });
});
