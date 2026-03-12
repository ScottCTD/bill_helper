import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EntryEditorModal } from "./EntryEditorModal";
import type { Entry } from "../lib/types";

vi.mock("./MarkdownBlockEditor", () => ({
  MarkdownBlockEditor: () => <div data-testid="markdown-editor" />
}));

const entryFixture: Entry = {
  id: "entry-1",
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
  direct_group: null,
  direct_group_member_role: null,
  group_path: [],
  tags: []
};

describe("EntryEditorModal", () => {
  it("renders the markdown editor under a Notes field label", async () => {
    render(
      <EntryEditorModal
        isOpen
        mode="edit"
        entry={entryFixture}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[{ id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }]}
        groups={[]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={() => {}}
        onSubmit={() => {}}
      />
    );

    const notesLabel = await screen.findByText("Notes:");
    expect(notesLabel).toBeInTheDocument();
    expect(screen.getByTestId("markdown-editor")).toBeInTheDocument();
    expect(notesLabel.closest(".entry-property-line")?.querySelector("[data-testid='markdown-editor']")).not.toBeNull();
  });

  it("explains preserved missing-entity labels while editing", async () => {
    render(
      <EntryEditorModal
        isOpen
        mode="edit"
        entry={entryFixture}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[{ id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }]}
        groups={[]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={() => {}}
        onSubmit={() => {}}
      />
    );

    expect(await screen.findByText(/preserved labels remain visible/i)).toBeInTheDocument();
  });

  it("shows a split role selector when assigning the entry to a split group", async () => {
    const user = userEvent.setup();

    render(
      <EntryEditorModal
        isOpen
        mode="create"
        entry={null}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[]}
        groups={[
          {
            id: "group-1",
            name: "Bundle Group",
            group_type: "BUNDLE",
            parent_group_id: null,
            direct_member_count: 0,
            direct_entry_count: 0,
            direct_child_group_count: 0,
            descendant_entry_count: 0,
            first_occurred_at: null,
            last_occurred_at: null
          },
          {
            id: "group-2",
            name: "Dinner Split",
            group_type: "SPLIT",
            parent_group_id: null,
            direct_member_count: 0,
            direct_entry_count: 0,
            direct_child_group_count: 0,
            descendant_entry_count: 0,
            first_occurred_at: null,
            last_occurred_at: null
          }
        ]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={() => {}}
        onSubmit={() => {}}
      />
    );

    await user.click(screen.getByRole("button", { name: "Group" }));
    await user.click(screen.getByRole("option", { name: /Dinner Split/i }));

    expect(screen.getByRole("button", { name: "Split role" })).toBeInTheDocument();
  });

  it("swaps the from and to values before submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const onClose = vi.fn();

    render(
      <EntryEditorModal
        isOpen
        mode="edit"
        entry={entryFixture}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[{ id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }]}
        groups={[]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    await user.click(screen.getByRole("button", { name: "Swap from and to" }));

    expect(screen.getByLabelText("From")).toHaveValue("Cafe");
    expect(screen.getByLabelText("To")).toHaveValue("Checking");

    await user.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          from_entity_id: "entity-2",
          from_entity: null,
          to_entity_id: null,
          to_entity: "Checking"
        })
      )
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it("keeps owner implicit and submits the current user id", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <EntryEditorModal
        isOpen
        mode="create"
        entry={null}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[]}
        groups={[]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={() => {}}
        onSubmit={onSubmit}
      />
    );

    expect(screen.queryByLabelText("Owner")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Name"), "Lunch");
    await user.type(screen.getByLabelText("Amount"), "12.50");
    await user.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          owner_user_id: "user-1",
          name: "Lunch",
          amount_minor: 1250
        })
      )
    );
  });

  it("submits when re-linking a preserved missing label to an existing entity with the same name", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const onClose = vi.fn();

    render(
      <EntryEditorModal
        isOpen
        mode="edit"
        entry={{
          ...entryFixture,
          kind: "TRANSFER",
          name: "Transfer to Saving Account",
          to_entity_id: null,
          to_entity: "Saving Account",
          to_entity_missing: true
        }}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[
          { id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 },
          {
            id: "entity-3",
            name: "Saving Account",
            category: "Account",
            is_account: true,
            from_count: 0,
            to_count: 1,
            account_count: 1,
            entry_count: 1
          }
        ]}
        groups={[]}
        tags={[]}
        currentUserId="user-1"
        defaultCurrencyCode="CAD"
        isSaving={false}
        onClose={onClose}
        onSubmit={onSubmit}
      />
    );

    await user.click(screen.getAllByRole("button", { name: "Toggle options" })[1]);
    await user.click(screen.getByRole("button", { name: "Saving Account" }));
    await user.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          to_entity_id: "entity-3",
          to_entity: null
        })
      )
    );
    expect(onClose).not.toHaveBeenCalled();
  });
});
