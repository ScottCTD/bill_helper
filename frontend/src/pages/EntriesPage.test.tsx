import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EntriesPage } from "./EntriesPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { Entry, RuntimeSettings } from "../lib/types";
import {
  createEntry,
  deleteEntry,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listEntries,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listEntries: vi.fn(),
    listCurrencies: vi.fn(),
    listEntities: vi.fn(),
    listUsers: vi.fn(),
    listTags: vi.fn(),
    getRuntimeSettings: vi.fn(),
    createEntry: vi.fn(),
    updateEntry: vi.fn(),
    deleteEntry: vi.fn()
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

const entryFixture: Entry = {
  id: "entry-1",
  group_id: "group-1",
  account_id: "acc-1",
  kind: "EXPENSE",
  occurred_at: "2026-03-05",
  name: "Coffee",
  amount_minor: 575,
  currency_code: "CAD",
  from_entity_id: null,
  to_entity_id: "entity-2",
  owner_user_id: "user-1",
  from_entity: "Checking",
  from_entity_missing: true,
  to_entity: "Cafe",
  to_entity_missing: false,
  owner: "Alice",
  markdown_body: null,
  created_at: "2026-03-05T00:00:00Z",
  updated_at: "2026-03-05T00:00:00Z",
  tags: [{ id: 1, name: "coffee", color: "#5f6caf", type: "Food", entry_count: 1 }]
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("EntriesPage", () => {
  it("shows a missing-entity badge for preserved labels in the entries table", async () => {
    vi.mocked(listEntries).mockResolvedValue({
      items: [entryFixture],
      total: 1,
      limit: 200,
      offset: 0
    });
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]);
    vi.mocked(listEntities).mockResolvedValue([
      { id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }
    ]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true }]);
    vi.mocked(listTags).mockResolvedValue([{ id: 1, name: "coffee", color: "#5f6caf", type: "Food", entry_count: 1 }]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(createEntry).mockResolvedValue(entryFixture);
    vi.mocked(updateEntry).mockResolvedValue(entryFixture);
    vi.mocked(deleteEntry).mockResolvedValue(undefined);

    renderWithQueryClient(<EntriesPage />);

    await screen.findByText("Coffee");
    expect(screen.getByText("Missing entity")).toBeInTheDocument();
  });
});
