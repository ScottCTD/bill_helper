import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AgentThreadSummary } from "../../../lib/types";
import { AgentThreadList } from "./AgentThreadList";

const THREADS: AgentThreadSummary[] = [
  {
    id: "thread-1",
    title: "Groceries",
    created_at: "2026-02-20T10:00:00Z",
    updated_at: "2026-02-20T10:01:00Z",
    last_message_preview: null,
    pending_change_count: 0
  },
  {
    id: "thread-2",
    title: "Utilities",
    created_at: "2026-02-20T11:00:00Z",
    updated_at: "2026-02-20T11:01:00Z",
    last_message_preview: null,
    pending_change_count: 0
  }
];

describe("AgentThreadList", () => {
  it("selects thread rows and deletes via the row delete control", async () => {
    const onSelectThread = vi.fn();
    const onDeleteThread = vi.fn();

    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={onSelectThread}
        onDeleteThread={onDeleteThread}
        deletingThreadId={null}
        isDeleteDisabled={false}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Utilities" }));
    expect(onSelectThread).toHaveBeenCalledWith("thread-2");

    await userEvent.click(screen.getByRole("button", { name: "Delete thread Groceries" }));
    expect(onDeleteThread).toHaveBeenCalledWith("thread-1");
  });

  it("disables the delete button for the thread currently being deleted", () => {
    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onDeleteThread={() => undefined}
        deletingThreadId="thread-1"
        isDeleteDisabled={false}
      />
    );

    expect(screen.getByRole("button", { name: "Delete thread Groceries" })).toBeDisabled();
  });

  it("hides delete controls when thread deletion is globally disabled", () => {
    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onDeleteThread={() => undefined}
        deletingThreadId={null}
        isDeleteDisabled={true}
      />
    );

    expect(screen.queryByRole("button", { name: "Delete thread Groceries" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete thread Utilities" })).not.toBeInTheDocument();
  });
});
