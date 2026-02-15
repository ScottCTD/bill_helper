import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AgentRunBlock } from "./AgentRunBlock";
import { buildChangeItem, buildRun, buildToolCall } from "../../test/factories/agent";

describe("AgentRunBlock", () => {
  it("renders summary mode and forwards review actions", async () => {
    const onReviewRun = vi.fn();
    const run = buildRun({
      id: "run-summary",
      change_items: [buildChangeItem({ id: "change-1", status: "PENDING_REVIEW", change_type: "create_entry" })]
    });

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={onReviewRun} mode="summary" />);

    expect(screen.getByText("1 proposed changes pending review")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Click to review proposed changes" }));
    expect(onReviewRun).toHaveBeenCalledWith("run-summary");
  });

  it("renders interleaved activity timeline for reasoning updates", () => {
    const run = buildRun({
      id: "run-activity",
      status: "running",
      tool_calls: [
        buildToolCall({ id: "tool-1", tool_name: "list_entries", created_at: "2026-02-15T10:00:00Z" }),
        buildToolCall({
          id: "tool-2",
          tool_name: "send_intermediate_update",
          created_at: "2026-02-15T10:00:01Z",
          output_json: { message: "Validating candidate entries" }
        })
      ]
    });

    render(<AgentRunBlock run={run} isMutating={false} onReviewRun={() => undefined} mode="activity" />);

    expect(screen.getByText("Validating candidate entries")).toBeInTheDocument();
    expect(screen.getByText("1 tool call")).toBeInTheDocument();
  });
});
