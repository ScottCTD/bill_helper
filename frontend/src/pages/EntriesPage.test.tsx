import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EntriesPage } from "./EntriesPage";
import { fallbackTagColor } from "../lib/tagColors";
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

function normalizeCssColor(color: string) {
  const element = document.createElement("div");
  element.style.color = color;
  return element.style.color;
}

function mockEntriesPageData(entry: Entry) {
  vi.mocked(listEntries).mockResolvedValue({
    items: [entry],
    total: 1,
    limit: 200,
    offset: 0
  });
  vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]);
  vi.mocked(listEntities).mockResolvedValue([
    { id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }
  ]);
  vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true }]);
  vi.mocked(listTags).mockResolvedValue(entry.tags.map((tag) => ({ ...tag })));
  vi.mocked(getRuntimeSettings).mockResolvedValue(runtimeSettingsFixture);
  vi.mocked(createEntry).mockResolvedValue(entry);
  vi.mocked(updateEntry).mockResolvedValue(entry);
  vi.mocked(deleteEntry).mockResolvedValue(undefined);
}

describe("EntriesPage", () => {
  it("shows a missing-entity badge for preserved labels in the entries table", async () => {
    mockEntriesPageData(entryFixture);

    renderWithQueryClient(<EntriesPage />);

    await screen.findByText("Coffee");
    expect(screen.getByText("Missing entity")).toBeInTheDocument();
  });

  it("renders explicit and fallback tag colors in the entries table", async () => {
    const entryWithFallbackTag: Entry = {
      ...entryFixture,
      tags: [
        entryFixture.tags[0],
        { id: 2, name: "travel", color: null, type: null, entry_count: 1 }
      ]
    };
    mockEntriesPageData(entryWithFallbackTag);

    renderWithQueryClient(<EntriesPage />);

    await screen.findByText("travel");

    const coffeeChip = screen.getByText("coffee").closest(".entries-tag-pill");
    const travelChip = screen.getByText("travel").closest(".entries-tag-pill");
    const coffeeDot = coffeeChip?.querySelector(".entries-tag-pill-color");
    const travelDot = travelChip?.querySelector(".entries-tag-pill-color");
    const fallbackColor = fallbackTagColor("travel");

    expect(coffeeChip).not.toBeNull();
    expect(travelChip).not.toBeNull();
    expect(coffeeDot).not.toBeNull();
    expect(travelDot).not.toBeNull();

    expect(coffeeChip?.style.borderColor).toBe(normalizeCssColor("#5f6caf"));
    expect(coffeeDot?.getAttribute("style")).toContain(normalizeCssColor("#5f6caf"));
    expect(travelChip?.style.borderColor).toBe(normalizeCssColor(fallbackColor));
    expect(travelDot?.getAttribute("style")).toContain(normalizeCssColor(fallbackColor));
  });
});
