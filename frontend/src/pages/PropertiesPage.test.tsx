import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PropertiesPage } from "./PropertiesPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import {
  createEntity,
  createTag,
  createTaxonomyTerm,
  createUser,
  listCurrencies,
  listEntities,
  listTags,
  listTaxonomies,
  listTaxonomyTerms,
  listUsers,
  updateEntity,
  updateTag,
  updateTaxonomyTerm,
  updateUser
} from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
    listUsers: vi.fn(),
    listTags: vi.fn(),
    listCurrencies: vi.fn(),
    listTaxonomies: vi.fn(),
    listTaxonomyTerms: vi.fn(),
    createEntity: vi.fn(),
    createTag: vi.fn(),
    createUser: vi.fn(),
    updateEntity: vi.fn(),
    updateTag: vi.fn(),
    updateUser: vi.fn(),
    createTaxonomyTerm: vi.fn(),
    updateTaxonomyTerm: vi.fn()
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

function mockBasePropertiesApi() {
  vi.mocked(listEntities).mockResolvedValue([{ id: "entity-1", name: "Grocer", category: "Food" }]);
  vi.mocked(listUsers).mockResolvedValue([{ id: "user-1", name: "Alice", is_current_user: true }]);
  vi.mocked(listTags).mockResolvedValue([{ id: 1, name: "groceries", color: "#22aa66", category: "Food" }]);
  vi.mocked(listCurrencies).mockResolvedValue([{ code: "CAD", name: "Canadian Dollar", entry_count: 3, is_placeholder: false }]);
  vi.mocked(listTaxonomies).mockResolvedValue([
    {
      id: "taxonomy-entity",
      key: "entity_category",
      applies_to: "entity",
      cardinality: "single",
      display_name: "Entity Categories"
    },
    {
      id: "taxonomy-tag",
      key: "tag_category",
      applies_to: "tag",
      cardinality: "single",
      display_name: "Tag Categories"
    }
  ]);
  vi.mocked(listTaxonomyTerms).mockImplementation(async (taxonomyKey: string) => {
    if (taxonomyKey === "entity_category") {
      return [{ id: "term-entity-1", taxonomy_id: "taxonomy-entity", name: "Food", normalized_name: "food", parent_term_id: null, usage_count: 1 }];
    }
    return [{ id: "term-tag-1", taxonomy_id: "taxonomy-tag", name: "Food", normalized_name: "food", parent_term_id: null, usage_count: 1 }];
  });
  vi.mocked(createEntity).mockResolvedValue({ id: "entity-2", name: "Landlord", category: "Housing" });
  vi.mocked(updateEntity).mockResolvedValue({ id: "entity-1", name: "Grocer", category: "Food" });
  vi.mocked(createTag).mockResolvedValue({ id: 2, name: "rent", color: null, category: "Housing" });
  vi.mocked(updateTag).mockResolvedValue({ id: 1, name: "groceries", color: "#22aa66", category: "Food" });
  vi.mocked(createUser).mockResolvedValue({ id: "user-2", name: "Bob", is_current_user: false });
  vi.mocked(updateUser).mockResolvedValue({ id: "user-1", name: "Alice", is_current_user: true });
  vi.mocked(createTaxonomyTerm).mockImplementation(async (_taxonomyKey, payload) => ({
    id: `term-${payload.name}`,
    taxonomy_id: "taxonomy",
    name: payload.name,
    normalized_name: payload.name.toLowerCase(),
    parent_term_id: null,
    usage_count: 0
  }));
  vi.mocked(updateTaxonomyTerm).mockImplementation(async (_taxonomyKey, termId, payload) => ({
    id: termId,
    taxonomy_id: "taxonomy",
    name: payload.name ?? "Updated",
    normalized_name: (payload.name ?? "Updated").toLowerCase(),
    parent_term_id: null,
    usage_count: 0
  }));
}

describe("PropertiesPage", () => {
  it("creates users from the Users section", async () => {
    mockBasePropertiesApi();
    renderWithQueryClient(<PropertiesPage />);

    await screen.findByText("Property Databases");
    await userEvent.click(screen.getByRole("button", { name: "Users" }));
    await userEvent.click(screen.getByRole("button", { name: "Add user" }));

    const createButton = screen.getByRole("button", { name: "Create" });
    const nameInput = screen.getByPlaceholderText("e.g. Alice");

    await userEvent.type(nameInput, "Bob");
    await userEvent.click(createButton);

    await waitFor(() => {
      expect(createUser).toHaveBeenCalled();
    });
    expect(vi.mocked(createUser).mock.calls[0]?.[0]).toEqual({ name: "Bob" });
  });

  it("creates tag taxonomy terms from the taxonomy section", async () => {
    mockBasePropertiesApi();
    renderWithQueryClient(<PropertiesPage />);

    await screen.findByText("Property Databases");
    await userEvent.click(screen.getByRole("button", { name: "Tag Categories" }));
    await userEvent.click(screen.getByRole("button", { name: "Add category" }));

    const termNameInput = screen.getByPlaceholderText("e.g. food");
    await userEvent.type(termNameInput, "Household");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createTaxonomyTerm).toHaveBeenCalled();
    });
    expect(vi.mocked(createTaxonomyTerm).mock.calls[0]?.[0]).toBe("tag_category");
    expect(vi.mocked(createTaxonomyTerm).mock.calls[0]?.[1]).toEqual({ name: "Household" });
  });
});
