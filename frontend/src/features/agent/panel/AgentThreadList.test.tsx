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
    pending_change_count: 0,
    has_running_run: false
  },
  {
    id: "thread-2",
    title: "Utilities",
    created_at: "2026-02-20T11:00:00Z",
    updated_at: "2026-02-20T11:01:00Z",
    last_message_preview: null,
    pending_change_count: 0,
    has_running_run: false
  }
];

describe("AgentThreadList", () => {
  it("selects thread rows and deletes via the row delete control", async () => {
    const onSelectThread = vi.fn();
    const onRenameThread = vi.fn().mockResolvedValue(undefined);
    const onDeleteThread = vi.fn();

    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={onSelectThread}
        onRenameThread={onRenameThread}
        onDeleteThread={onDeleteThread}
        renamingThreadId={null}
        deletingThreadId={null}
        isDeleteDisabled={false}
        isRenameDisabled={false}
        optimisticRunningThreadId={null}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Utilities" }));
    expect(onSelectThread).toHaveBeenCalledWith("thread-2");

    await userEvent.click(screen.getByRole("button", { name: "Delete thread Groceries" }));
    expect(onDeleteThread).toHaveBeenCalledWith("thread-1");
  });


  it("renames a thread on double click", async () => {
    const onRenameThread = vi.fn().mockResolvedValue(undefined);

    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={onRenameThread}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        isDeleteDisabled={false}
        isRenameDisabled={false}
        optimisticRunningThreadId={null}
      />
    );

    await userEvent.dblClick(screen.getByRole("button", { name: "Groceries" }));
    const input = screen.getByRole("textbox", { name: "Rename thread Groceries" });
    await userEvent.clear(input);
    await userEvent.type(input, "Monthly Budget{Enter}");

    expect(onRenameThread).toHaveBeenCalledWith("thread-1", "Monthly Budget");
  });

  it("disables the delete button for the thread currently being deleted", () => {
    render(
      <AgentThreadList
        threads={THREADS}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId="thread-1"
        isDeleteDisabled={false}
        isRenameDisabled={false}
        optimisticRunningThreadId={null}
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
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        isDeleteDisabled={true}
        isRenameDisabled={false}
        optimisticRunningThreadId={null}
      />
    );

    expect(screen.queryByRole("button", { name: "Delete thread Groceries" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete thread Utilities" })).not.toBeInTheDocument();
  });

  it("shows a running status indicator for active threads", () => {
    render(
      <AgentThreadList
        threads={[{ ...THREADS[0], has_running_run: true }]}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        isDeleteDisabled={false}
        isRenameDisabled={false}
        optimisticRunningThreadId={null}
      />
    );

    expect(screen.getByLabelText("Thread is processing")).toBeInTheDocument();
  });

  it("shows a running status indicator immediately for optimistic running thread id", () => {
    render(
      <AgentThreadList
        threads={[THREADS[0]]}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        isDeleteDisabled={false}
        isRenameDisabled={false}
        optimisticRunningThreadId="thread-1"
      />
    );

    expect(screen.getByLabelText("Thread is processing")).toBeInTheDocument();
  });
});
