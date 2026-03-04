import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentThreadUsageBar } from "./AgentThreadUsageBar";

describe("AgentThreadUsageBar", () => {
  it("renders the current context metric separately from cumulative input", () => {
    render(
      <AgentThreadUsageBar
        selectedThreadId="thread-1"
        totals={{
          context: 87654,
          input: 12345,
          output: 6789,
          cacheRead: 2000,
          totalCost: 0.0123,
        }}
      />
    );

    expect(screen.getByText("Context")).toBeInTheDocument();
    expect(screen.getByText("87.65K")).toBeInTheDocument();
    expect(screen.getByText("Total input")).toBeInTheDocument();
    expect(screen.getByText("12.35K")).toBeInTheDocument();
    expect(screen.queryByText("Input")).not.toBeInTheDocument();
  });
});
