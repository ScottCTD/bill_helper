import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FilterGroupsPage } from "../../pages/FilterGroupsPage";
import type { FilterGroup, Tag } from "../../lib/types";
import { createFilterGroup, deleteFilterGroup, listFilterGroups, listTags, updateFilterGroup } from "../../lib/api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listFilterGroups: vi.fn(),
    listTags: vi.fn(),
    createFilterGroup: vi.fn(),
    updateFilterGroup: vi.fn(),
    deleteFilterGroup: vi.fn()
  };
});

const tags: Tag[] = [
  { id: 1, name: "grocery", color: "#33aa66" },
  { id: 2, name: "coffee", color: "#aa6633" },
  { id: 3, name: "housing", color: "#4466cc" }
];

function createFilterGroupFixture(overrides: Partial<FilterGroup> & Pick<FilterGroup, "id" | "name" | "key" | "position">): FilterGroup {
  return {
    id: overrides.id,
    key: overrides.key,
    name: overrides.name,
    description: overrides.description ?? `${overrides.name} description`,
    color: overrides.color ?? "#64748b",
    is_default: overrides.is_default ?? true,
    position: overrides.position,
    rule:
      overrides.rule ??
      {
        include: {
          type: "group",
          operator: "AND",
          children: [{ type: "condition", field: "entry_kind", operator: "is", value: "EXPENSE" }]
        },
        exclude: null
      },
    rule_summary: overrides.rule_summary ?? "kind is expense",
    created_at: overrides.created_at ?? "2026-03-01T00:00:00Z",
    updated_at: overrides.updated_at ?? "2026-03-01T00:00:00Z"
  };
}

function cloneFilterGroups(value: FilterGroup[]): FilterGroup[] {
  return JSON.parse(JSON.stringify(value)) as FilterGroup[];
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <FilterGroupsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("FilterGroupsPage", () => {
  let currentFilterGroups: FilterGroup[];

  beforeEach(() => {
    currentFilterGroups = [
      createFilterGroupFixture({
        id: "fg-day",
        key: "day_to_day",
        name: "day-to-day",
        position: 0,
        is_default: true,
        rule_summary:
          "(kind is expense and tags include alcohol_bars, coffee_snacks, dining_out, entertainment, fitness, grocery, health_medical, home, personal_care, pets, pharmacy, subscriptions, or transportation); excluding (tags include one_time or is an internal transfer)"
      }),
      createFilterGroupFixture({
        id: "fg-travel",
        key: "travel",
        name: "Travel",
        position: 1,
        is_default: false,
        description: "Trips and travel."
      }),
      createFilterGroupFixture({
        id: "fg-fixed",
        key: "fixed",
        name: "Fixed",
        position: 2,
        is_default: true,
        description: "Recurring obligations."
      }),
      createFilterGroupFixture({
        id: "fg-untagged",
        key: "untagged",
        name: "untagged",
        position: 3,
        is_default: true,
        description: "Expense entries with no tags, or tagged expense entries that do not match any other saved filter group. This group is computed automatically and cannot be edited.",
        rule_summary: "kind is expense and is not an internal transfer and (has no tags or matches no other saved filter group)"
      })
    ];

    vi.mocked(listFilterGroups).mockImplementation(async () => cloneFilterGroups(currentFilterGroups));
    vi.mocked(listTags).mockResolvedValue(tags);
    vi.mocked(createFilterGroup).mockImplementation(async (payload) => {
      const createdFilterGroup = createFilterGroupFixture({
        id: "fg-new",
        key: "custom",
        name: payload.name,
        position: currentFilterGroups.length,
        is_default: false,
        description: payload.description ?? "",
        color: payload.color,
        rule: payload.rule,
        rule_summary: "kind is expense"
      });
      currentFilterGroups = [...currentFilterGroups, createdFilterGroup];
      return cloneFilterGroups([createdFilterGroup])[0];
    });
    vi.mocked(updateFilterGroup).mockImplementation(async (filterGroupId, payload) => {
      currentFilterGroups = currentFilterGroups.map((filterGroup) =>
        filterGroup.id === filterGroupId
          ? {
              ...filterGroup,
              name: payload.name ?? filterGroup.name,
              description: payload.description ?? filterGroup.description,
              color: payload.color ?? filterGroup.color,
              rule: payload.rule ?? filterGroup.rule
            }
          : filterGroup
      );
      return cloneFilterGroups(currentFilterGroups).find((filterGroup) => filterGroup.id === filterGroupId)!;
    });
    vi.mocked(deleteFilterGroup).mockImplementation(async (filterGroupId) => {
      currentFilterGroups = currentFilterGroups.filter((filterGroup) => filterGroup.id !== filterGroupId);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("selects the first group and does not render the raw backend rule summary", async () => {
    renderPage();

    expect(await screen.findByDisplayValue("day-to-day")).toBeInTheDocument();
    expect(screen.queryByText(/tags include alcohol_bars/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guided" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("protects unsaved changes when switching away from a new draft", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByDisplayValue("day-to-day");
    await user.click(screen.getByRole("button", { name: "New custom group" }));
    await user.type(screen.getByLabelText("Name"), "Trip budget");

    await user.click(screen.getByRole("button", { name: /Fixed/ }));
    expect(await screen.findByRole("dialog", { name: "Discard unsaved changes?" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(screen.getByDisplayValue("Trip budget")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Fixed/ }));
    await user.click(await screen.findByRole("button", { name: "Discard changes" }));

    expect(await screen.findByDisplayValue("Fixed")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Trip budget")).not.toBeInTheDocument();
  });

  it("creates a new custom group from the page header and keeps the returned group selected", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByDisplayValue("day-to-day");
    await user.click(screen.getByRole("button", { name: "New custom group" }));
    const createButton = screen.getByRole("button", { name: "Create group" });
    expect(createButton).toBeDisabled();

    await user.type(screen.getByLabelText("Name"), "Trips");
    await user.type(screen.getByLabelText("Description"), "Travel expenses.");
    expect(screen.getByRole("button", { name: "Create group" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Create group" }));

    await waitFor(() => {
      expect(createFilterGroup).toHaveBeenCalled();
    });
    expect(await screen.findByDisplayValue("Trips")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View matching entries" })).toHaveAttribute("href", "/entries?filter_group_id=fg-new");
  });

  it("deletes the selected custom group and moves selection to the next group", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByDisplayValue("day-to-day");
    await user.click(screen.getByRole("button", { name: /Travel/ }));
    expect(await screen.findByDisplayValue("Travel")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(vi.mocked(deleteFilterGroup).mock.calls[0]?.[0]).toBe("fg-travel");
    });
    expect(await screen.findByDisplayValue("Fixed")).toBeInTheDocument();
  });

  it("renders untagged as a read-only system panel and hides the header save action", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByDisplayValue("day-to-day");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /untagged/i }));

    expect(await screen.findByText("Computed automatically")).toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View matching entries" })).toHaveAttribute("href", "/entries?filter_group_id=fg-untagged");
  });
});
