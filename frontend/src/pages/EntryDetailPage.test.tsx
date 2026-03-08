import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { EntryDetailPage } from "./EntryDetailPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { EntryDetail, RuntimeSettings } from "../lib/types";
import {
  createLink,
  deleteLink,
  getEntry,
  getGroup,
  getRuntimeSettings,
  listCurrencies,
  listEntities,
  listEntries,
  listTags,
  listUsers,
  updateEntry
} from "../lib/api";

vi.mock("../components/GroupGraphView", () => ({
  GroupGraphView: () => <div data-testid="group-graph-view">Graph</div>
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getEntry: vi.fn(),
    getGroup: vi.fn(),
    listCurrencies: vi.fn(),
    listEntities: vi.fn(),
    listUsers: vi.fn(),
    listTags: vi.fn(),
    getRuntimeSettings: vi.fn(),
    listEntries: vi.fn(),
    updateEntry: vi.fn(),
    createLink: vi.fn(),
    deleteLink: vi.fn()
  };
});

const runtimeSettingsFixture: RuntimeSettings = {
  current_user_name: "Alice",
  user_memory: null,
  default_currency_code: "CAD",
  dashboard_currency_code: "CAD",
  agent_model: "gpt-5",
  agent_max_steps: 20,
  agent_bulk_max_concurrent_threads: 4,
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
    agent_bulk_max_concurrent_threads: null,
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

const entryFixture: EntryDetail = {
  id: "entry-1",
  group_id: "group-1",
  account_id: "acc-1",
  kind: "TRANSFER",
  occurred_at: "2026-03-05",
  name: "Move funds",
  amount_minor: 5000,
  currency_code: "CAD",
  from_entity_id: null,
  to_entity_id: null,
  owner_user_id: "user-1",
  from_entity: "Old Checking",
  from_entity_missing: true,
  to_entity: "Archived Savings",
  to_entity_missing: true,
  owner: "Alice",
  markdown_body: null,
  created_at: "2026-03-05T00:00:00Z",
  updated_at: "2026-03-05T00:00:00Z",
  tags: [],
  links: []
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("EntryDetailPage", () => {
  it("shows missing-entity badges for preserved from/to labels", async () => {
    vi.mocked(getEntry).mockResolvedValue(entryFixture);
    vi.mocked(getGroup).mockResolvedValue({ group_id: "group-1", nodes: [], edges: [] });
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]);
    vi.mocked(listEntities).mockResolvedValue([]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true }]);
    vi.mocked(listTags).mockResolvedValue([]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listEntries).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.mocked(updateEntry).mockResolvedValue(entryFixture);
    vi.mocked(createLink).mockResolvedValue({
      id: "link-1",
      source_entry_id: "entry-1",
      target_entry_id: "entry-2",
      link_type: "BUNDLE",
      note: null,
      created_at: "2026-03-05T00:00:00Z"
    });
    vi.mocked(deleteLink).mockResolvedValue(undefined);

    renderWithQueryClient(
      <MemoryRouter initialEntries={["/entries/entry-1"]}>
        <Routes>
          <Route path="/entries/:entryId" element={<EntryDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText("Entry Details");
    expect(screen.getAllByText("Missing entity")).toHaveLength(2);
  });

  it("renders icon delete controls for links with accessible labels", async () => {
    vi.mocked(getEntry).mockResolvedValue({
      ...entryFixture,
      links: [
        {
          id: "link-1",
          source_entry_id: "entry-1",
          target_entry_id: "entry-2",
          link_type: "BUNDLE",
          note: null,
          created_at: "2026-03-05T00:00:00Z"
        }
      ]
    });
    vi.mocked(getGroup).mockResolvedValue({ group_id: "group-1", nodes: [], edges: [] });
    vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]);
    vi.mocked(listEntities).mockResolvedValue([]);
    vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true }]);
    vi.mocked(listTags).mockResolvedValue([]);
    vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
    vi.mocked(listEntries).mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    vi.mocked(updateEntry).mockResolvedValue(entryFixture);
    vi.mocked(createLink).mockResolvedValue({
      id: "link-2",
      source_entry_id: "entry-1",
      target_entry_id: "entry-3",
      link_type: "BUNDLE",
      note: null,
      created_at: "2026-03-05T00:00:00Z"
    });
    vi.mocked(deleteLink).mockResolvedValue(undefined);

    renderWithQueryClient(
      <MemoryRouter initialEntries={["/entries/entry-1"]}>
        <Routes>
          <Route path="/entries/:entryId" element={<EntryDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText("Entry Details");
    expect(screen.getByRole("button", { name: "Delete link entry-1 to entry-2" })).toBeInTheDocument();
  });
});
