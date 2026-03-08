import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GroupsPage } from "./GroupsPage";
import { renderWithQueryClient } from "../test/renderWithQueryClient";
import type { Entry, GroupGraph, GroupSummary } from "../lib/types";
import {
  addGroupMember,
  createGroup,
  deleteGroup,
  deleteGroupMember,
  getGroup,
  listEntries,
  listGroups,
  updateGroup
} from "../lib/api";

vi.mock("../components/GroupGraphView", () => ({
  GroupGraphView: ({ graph }: { graph: GroupGraph }) => <div>Graph mock: {graph.name}</div>
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    listGroups: vi.fn(),
    getGroup: vi.fn(),
    listEntries: vi.fn(),
    createGroup: vi.fn(),
    updateGroup: vi.fn(),
    deleteGroup: vi.fn(),
    addGroupMember: vi.fn(),
    deleteGroupMember: vi.fn()
  };
});

const groupsFixture: GroupSummary[] = [
  {
    id: "group-1",
    name: "OpenAI ChatGPT Plus Subscription",
    group_type: "RECURRING",
    parent_group_id: null,
    direct_member_count: 3,
    direct_entry_count: 3,
    direct_child_group_count: 0,
    descendant_entry_count: 3,
    first_occurred_at: "2026-01-06",
    last_occurred_at: "2026-03-06"
  },
  {
    id: "group-2",
    name: "Payroll Deposit",
    group_type: "RECURRING",
    parent_group_id: null,
    direct_member_count: 2,
    direct_entry_count: 2,
    direct_child_group_count: 0,
    descendant_entry_count: 2,
    first_occurred_at: "2026-01-15",
    last_occurred_at: "2026-02-15"
  }
];

const entryFixture: Entry = {
  id: "entry-1",
  account_id: "account-1",
  kind: "EXPENSE",
  occurred_at: "2026-03-06",
  name: "OpenAI ChatGPT Subscription",
  amount_minor: 3178,
  currency_code: "CAD",
  from_entity_id: null,
  to_entity_id: null,
  owner_user_id: null,
  from_entity: "Scotiabank Credit",
  from_entity_missing: false,
  to_entity: "OpenAI",
  to_entity_missing: false,
  owner: null,
  markdown_body: null,
  created_at: "2026-03-06T00:00:00Z",
  updated_at: "2026-03-06T00:00:00Z",
  tags: [],
  direct_group: null,
  direct_group_member_role: null,
  group_path: []
};

const graphFixture: GroupGraph = {
  id: "group-1",
  name: "OpenAI ChatGPT Plus Subscription",
  group_type: "RECURRING",
  parent_group_id: null,
  direct_member_count: 3,
  direct_entry_count: 3,
  direct_child_group_count: 0,
  descendant_entry_count: 3,
  first_occurred_at: "2026-01-06",
  last_occurred_at: "2026-03-06",
  nodes: [
    {
      graph_id: "node-1",
      membership_id: "membership-1",
      subject_id: "entry-1",
      node_type: "ENTRY",
      name: "OpenAI ChatGPT Subscription",
      member_role: null,
      representative_occurred_at: "2026-03-06",
      kind: "EXPENSE",
      amount_minor: 3178,
      currency_code: "CAD",
      occurred_at: "2026-03-06",
      group_type: null,
      descendant_entry_count: null,
      first_occurred_at: null,
      last_occurred_at: null
    }
  ],
  edges: []
};

afterEach(() => {
  vi.clearAllMocks();
});

function mockGroupsPageData() {
  vi.mocked(listGroups).mockResolvedValue(groupsFixture);
  vi.mocked(getGroup).mockResolvedValue(graphFixture);
  vi.mocked(listEntries).mockResolvedValue({
    items: [entryFixture],
    total: 1,
    limit: 200,
    offset: 0
  });
  vi.mocked(createGroup).mockResolvedValue(groupsFixture[0]);
  vi.mocked(updateGroup).mockResolvedValue(groupsFixture[0]);
  vi.mocked(deleteGroup).mockResolvedValue(undefined);
  vi.mocked(addGroupMember).mockResolvedValue(graphFixture);
  vi.mocked(deleteGroupMember).mockResolvedValue(undefined);
}

describe("GroupsPage", () => {
  it("uses a table-first browser and opens group detail in a modal", async () => {
    mockGroupsPageData();

    renderWithQueryClient(<GroupsPage />);

    expect(await screen.findByText("Entry Groups")).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "Group" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Direct structure" })).toBeInTheDocument();
    expect(screen.queryByText("Derived graph")).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "View" })[0]);

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Statistics" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Direct members" })).toBeInTheDocument();
    expect(screen.getByText("Total cost")).toBeInTheDocument();
    expect(screen.getAllByText("CAD 31.78")).toHaveLength(3);
    expect(screen.getByRole("heading", { name: "Derived graph" })).toBeInTheDocument();
    expect(screen.getByText("Graph mock: OpenAI ChatGPT Plus Subscription")).toBeInTheDocument();
    expect(screen.getByText("OpenAI ChatGPT Subscription")).toBeInTheDocument();

    await waitFor(() => expect(getGroup).toHaveBeenCalledWith("group-1"));
  });
});
