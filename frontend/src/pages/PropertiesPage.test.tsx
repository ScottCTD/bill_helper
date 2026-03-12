import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PropertiesPage } from "./PropertiesPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import {
  createTag,
  createTaxonomyTerm,
  deleteTag,
  listCurrencies,
  listTags,
  listTaxonomies,
  listTaxonomyTerms,
  updateTag,
  updateTaxonomyTerm
} from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listUsers: vi.fn(),
    listTags: vi.fn(),
    listCurrencies: vi.fn(),
    listTaxonomies: vi.fn(),
    listTaxonomyTerms: vi.fn(),
    createTag: vi.fn(),
    deleteTag: vi.fn(),
    updateTag: vi.fn(),
    createTaxonomyTerm: vi.fn(),
    updateTaxonomyTerm: vi.fn()
  };
});

afterEach(() => {
  vi.clearAllMocks();
});

function mockBasePropertiesApi() {
  vi.mocked(listTags).mockResolvedValue([{ id: 1, name: "groceries", color: "#22aa66", type: "Food", entry_count: 2 }]);
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
      key: "tag_type",
      applies_to: "tag",
      cardinality: "single",
      display_name: "Tag Types"
    }
  ]);
  vi.mocked(listTaxonomyTerms).mockImplementation(async (taxonomyKey: string) => {
    if (taxonomyKey === "entity_category") {
      return [{ id: "term-entity-1", taxonomy_id: "taxonomy-entity", name: "Food", normalized_name: "food", parent_term_id: null, usage_count: 1 }];
    }
    return [{ id: "term-tag-1", taxonomy_id: "taxonomy-tag", name: "Food", normalized_name: "food", parent_term_id: null, usage_count: 1 }];
  });
  vi.mocked(createTag).mockResolvedValue({ id: 2, name: "rent", color: null, type: "Housing", entry_count: 0 });
  vi.mocked(updateTag).mockResolvedValue({ id: 1, name: "groceries", color: "#22aa66", type: "Food", entry_count: 2 });
  vi.mocked(deleteTag).mockResolvedValue(undefined);
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
  it("creates tag taxonomy terms from the taxonomy section", async () => {
    mockBasePropertiesApi();
    renderWithQueryClient(<PropertiesPage />);

    await screen.findByText("Property Databases");
    await userEvent.click(screen.getByRole("button", { name: "Tag Types" }));
    await userEvent.click(screen.getByRole("button", { name: "Add term" }));

    const termNameInput = screen.getByPlaceholderText("e.g. food");
    await userEvent.type(termNameInput, "Household");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createTaxonomyTerm).toHaveBeenCalled();
    });
    expect(vi.mocked(createTaxonomyTerm).mock.calls[0]?.[0]).toBe("tag_type");
    expect(vi.mocked(createTaxonomyTerm).mock.calls[0]?.[1]).toEqual({ name: "Household" });
  });

  it("deletes tags from the warning dialog", async () => {
    mockBasePropertiesApi();
    renderWithQueryClient(<PropertiesPage />);

    await screen.findByText("Property Databases");
    await userEvent.click(screen.getByRole("button", { name: "Tags" }));

    await userEvent.click(screen.getByRole("button", { name: "Delete tag groceries" }));

    const deleteDialog = await screen.findByRole("dialog", { name: "Delete groceries?" });
    expect(within(deleteDialog).getByText(/removed from those entries/i)).toBeInTheDocument();

    await userEvent.click(within(deleteDialog).getByRole("button", { name: "Delete tag" }));

    await waitFor(() => {
      expect(vi.mocked(deleteTag).mock.calls[0]?.[0]).toBe(1);
    });
  });

  it("opens tag editing on row double-click and keeps delete isolated", async () => {
    mockBasePropertiesApi();
    renderWithQueryClient(<PropertiesPage />);

    await screen.findByText("Property Databases");
    await userEvent.click(screen.getByRole("button", { name: "Tags" }));
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();

    const tagRow = screen.getByText("groceries").closest("tr");
    expect(tagRow).not.toBeNull();
    if (!tagRow) {
      throw new Error("Expected tag row");
    }

    await userEvent.dblClick(tagRow);
    const editDialog = await screen.findByRole("dialog", { name: "Edit Tag" });
    expect(within(editDialog).getByLabelText("Name")).toHaveValue("groceries");

    await userEvent.click(within(editDialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Edit Tag" })).not.toBeInTheDocument();
    });

    await userEvent.dblClick(screen.getByRole("button", { name: "Delete tag groceries" }));
    expect(await screen.findByRole("dialog", { name: "Delete groceries?" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Edit Tag" })).not.toBeInTheDocument();
  });

});
