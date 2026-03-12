import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TagMultiSelect } from "./TagMultiSelect";
import type { Tag } from "../lib/types";

const options: Tag[] = [
  { id: 1, name: "coffee", color: null },
  { id: 2, name: "cafe", color: null },
  { id: 3, name: "caffeine", color: null },
  { id: 4, name: "tea", color: null }
];

function optionLabels() {
  return Array.from(document.querySelectorAll<HTMLButtonElement>(".tag-multiselect-option")).map((option) =>
    option.textContent?.replace(/\s+/g, " ").trim()
  );
}

describe("TagMultiSelect", () => {
  it("shows fuzzy matches and ranks the tightest matches first", async () => {
    const user = userEvent.setup();

    render(<TagMultiSelect options={options} value={[]} onChange={() => {}} ariaLabel="Tags" />);

    await user.type(screen.getByLabelText("Tags"), "cfe");

    expect(optionLabels().slice(0, 3)).toEqual(["cafe", "coffee", "caffeine"]);
    expect(screen.queryByText("No matching tags.")).not.toBeInTheDocument();
  });

  it("adds the top fuzzy match first when submitting from the keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<TagMultiSelect options={options} value={[]} onChange={onChange} ariaLabel="Tags" />);

    await user.type(screen.getByLabelText("Tags"), "cfe{enter}");

    expect(onChange).toHaveBeenLastCalledWith(["cafe"]);
  });
});
