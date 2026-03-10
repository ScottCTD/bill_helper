import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

describe("MarkdownBlockEditor", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("./MarkdownBlockEditorImpl");
  });

  it("renders a loading fallback before the rich editor chunk loads", async () => {
    const { MarkdownBlockEditor } = await import("./MarkdownBlockEditor");

    render(<MarkdownBlockEditor markdown="Existing note" resetKey="account-create-open" onChange={() => undefined} />);

    expect(screen.getByText("Loading rich markdown editor...")).toBeInTheDocument();
    expect(screen.getByLabelText("Markdown")).toHaveValue("Existing note");
  });

  it("shows the runtime error in development while keeping the textarea usable", async () => {
    vi.doMock("./MarkdownBlockEditorImpl", () => ({
      MarkdownBlockEditorImpl: () => {
        throw new Error("Mock BlockNote failure");
      }
    }));

    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { MarkdownBlockEditor } = await import("./MarkdownBlockEditor");

    render(<MarkdownBlockEditor markdown="Existing note" resetKey="account-create-open" onChange={() => undefined} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Rich markdown editor failed to load.");
    expect(screen.getByRole("alert")).toHaveTextContent("Mock BlockNote failure");
    expect(screen.getByLabelText("Markdown")).toHaveValue("Existing note");

    consoleErrorSpy.mockRestore();
  });
});
