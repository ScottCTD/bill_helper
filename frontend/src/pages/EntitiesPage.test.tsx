import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EntitiesPage } from "./EntitiesPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import { createEntity, deleteEntity, listEntities, listTaxonomyTerms, updateEntity } from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
    listTaxonomyTerms: vi.fn(),
    createEntity: vi.fn(),
    updateEntity: vi.fn(),
    deleteEntity: vi.fn()
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

function mockEntitiesPageApi() {
  vi.mocked(listEntities).mockResolvedValue([
    {
      id: "entity-1",
      name: "Grocer",
      category: "Food",
      is_account: false,
      from_count: 1,
      to_count: 2,
      account_count: 0,
      entry_count: 3,
      net_amount_minor: -2550,
      net_amount_currency_code: "USD",
      net_amount_mixed_currencies: false
    },
    {
      id: "entity-2",
      name: "Airline",
      category: "Travel",
      is_account: false,
      from_count: 0,
      to_count: 2,
      account_count: 0,
      entry_count: 2,
      net_amount_minor: null,
      net_amount_currency_code: null,
      net_amount_mixed_currencies: true
    },
    {
      id: "entity-account",
      name: "Checking",
      category: null,
      is_account: true,
      from_count: 0,
      to_count: 0,
      account_count: 1,
      entry_count: 0,
      net_amount_minor: null,
      net_amount_currency_code: null,
      net_amount_mixed_currencies: false
    }
  ]);
  vi.mocked(listTaxonomyTerms).mockResolvedValue([
    { id: "term-entity-1", taxonomy_id: "taxonomy-entity", name: "Food", normalized_name: "food", parent_term_id: null, usage_count: 1 }
  ]);
  vi.mocked(createEntity).mockResolvedValue({
    id: "entity-2",
    name: "Landlord",
    category: "Housing",
    is_account: false,
    from_count: 0,
    to_count: 0,
    account_count: 0,
    entry_count: 0,
    net_amount_minor: null,
    net_amount_currency_code: null,
    net_amount_mixed_currencies: false
  });
  vi.mocked(updateEntity).mockResolvedValue({
    id: "entity-1",
    name: "Grocer",
    category: "Food",
    is_account: false,
    from_count: 1,
    to_count: 2,
    account_count: 0,
    entry_count: 3,
    net_amount_minor: -2550,
    net_amount_currency_code: "USD",
    net_amount_mixed_currencies: false
  });
  vi.mocked(deleteEntity).mockResolvedValue(undefined);
}

describe("EntitiesPage", () => {
  it("hides account-backed entities and deletes regular entities", async () => {
    mockEntitiesPageApi();
    renderWithQueryClient(<EntitiesPage />);

    expect(await screen.findByText("Grocer")).toBeInTheDocument();
    expect(screen.getByText("USD -25.50")).toBeInTheDocument();
    expect(screen.getByText("Mixed currencies")).toBeInTheDocument();
    expect(screen.queryByText("Checking")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Delete entity Grocer" }));

    const deleteDialog = await screen.findByRole("dialog", { name: "Delete Grocer?" });
    expect(screen.getByText(/missing-entity marker/i)).toBeInTheDocument();

    await userEvent.click(within(deleteDialog).getByRole("button", { name: "Delete entity" }));

    await waitFor(() => {
      expect(vi.mocked(deleteEntity).mock.calls[0]?.[0]).toBe("entity-1");
    });
  });

  it("opens entity editing on row double-click and keeps delete isolated", async () => {
    mockEntitiesPageApi();
    renderWithQueryClient(<EntitiesPage />);

    const entityRow = (await screen.findByText("Grocer")).closest("tr");
    expect(entityRow).not.toBeNull();
    if (!entityRow) {
      throw new Error("Expected entity row");
    }

    await userEvent.dblClick(entityRow);
    const editDialog = await screen.findByRole("dialog", { name: "Edit Entity" });
    expect(within(editDialog).getByLabelText("Name")).toHaveValue("Grocer");

    await userEvent.click(within(editDialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Edit Entity" })).not.toBeInTheDocument();
    });

    await userEvent.dblClick(screen.getByRole("button", { name: "Delete entity Grocer" }));
    expect(await screen.findByRole("dialog", { name: "Delete Grocer?" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Edit Entity" })).not.toBeInTheDocument();
  });
});
