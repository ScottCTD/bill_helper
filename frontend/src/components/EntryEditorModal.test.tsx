import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EntryEditorModal } from "./EntryEditorModal";
import type { Entry } from "../lib/types";

vi.mock("./MarkdownBlockEditor", () => ({
  MarkdownBlockEditor: () => <div data-testid="markdown-editor" />
}));

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
  tags: []
};

describe("EntryEditorModal", () => {
  it("explains preserved missing-entity labels while editing", async () => {
    render(
      <EntryEditorModal
        isOpen
        mode="edit"
        entry={entryFixture}
        currencies={[{ code: "CAD", name: "Canadian Dollar", entry_count: 1, is_placeholder: false }]}
        entities={[{ id: "entity-2", name: "Cafe", category: "Food", is_account: false, from_count: 0, to_count: 1, account_count: 0, entry_count: 1 }]}
        users={[{ id: "user-1", name: "Alice", is_current_user: true }]}
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
});
