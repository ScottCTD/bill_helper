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
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
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
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
      />
    );

    await userEvent.dblClick(screen.getByRole("button", { name: "Groceries" }));
    const input = screen.getByRole("textbox", { name: "Rename thread Groceries" });
    expect(input.closest(".agent-thread-row")).toHaveClass("editing");
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
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
      />
    );

    expect(screen.getByRole("button", { name: "Delete thread Groceries" })).toBeDisabled();
  });

  it("hides delete controls only for threads whose delete action is disabled", () => {
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
        deleteDisabledThreadIds={["thread-1", "thread-2"]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
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
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
      />
    );

    expect(screen.getByLabelText("Thread is processing")).toBeInTheDocument();
  });

  it("renders the full normalized thread title text before CSS truncation", () => {
    render(
      <AgentThreadList
        threads={[
          {
            ...THREADS[0],
            title: "  Very   long    thread title that should stay available to the layout system  "
          }
        ]}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
      />
    );

    expect(
      screen.getByRole("button", {
        name: "Very long thread title that should stay available to the layout system"
      })
    ).toBeInTheDocument();
    expect(screen.getByText("Very long thread title that should stay available to the layout system")).toBeInTheDocument();
  });

  it("keeps the full thread title value in the inline rename input", async () => {
    render(
      <AgentThreadList
        threads={[
          {
            ...THREADS[0],
            title: "Very long thread title that should stay editable past the current view"
          }
        ]}
        selectedThreadId="thread-1"
        isLoading={false}
        errorMessage={null}
        onSelectThread={() => undefined}
        onRenameThread={vi.fn().mockResolvedValue(undefined)}
        onDeleteThread={() => undefined}
        renamingThreadId={null}
        deletingThreadId={null}
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={[]}
      />
    );

    await userEvent.dblClick(
      screen.getByRole("button", {
        name: "Very long thread title that should stay editable past the current view"
      })
    );

    expect(screen.getByRole("textbox", { name: "Rename thread Very long thread title that should stay editable past the current view" })).toHaveValue(
      "Very long thread title that should stay editable past the current view"
    );
  });

  it("shows running status indicators immediately for optimistic running thread ids", () => {
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
        deleteDisabledThreadIds={[]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={["thread-1", "thread-2"]}
      />
    );

    expect(screen.getAllByLabelText("Thread is processing")).toHaveLength(2);
  });

  it("keeps idle thread delete controls available while another thread is running", () => {
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
        deleteDisabledThreadIds={["thread-1"]}
        renameDisabledThreadIds={[]}
        optimisticRunningThreadIds={["thread-1"]}
      />
    );

    expect(screen.queryByRole("button", { name: "Delete thread Groceries" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete thread Utilities" })).toBeInTheDocument();
  });
});
