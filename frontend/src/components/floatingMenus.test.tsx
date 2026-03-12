import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CreatableSingleSelect } from "./CreatableSingleSelect";
import { SingleSelect } from "./SingleSelect";
import { TagMultiSelect } from "./TagMultiSelect";

function renderInsideWorkspace(children: ReactNode) {
  render(<div data-testid="clip-shell" className="workspace-section">{children}</div>);
  return screen.getByTestId("clip-shell");
}

describe("floating select menus", () => {
  it("renders tag multiselect menus outside the workspace card", async () => {
    const shell = renderInsideWorkspace(
      <TagMultiSelect
        options={[{ id: 1, name: "coffee", color: "#5f6caf" }]}
        value={[]}
        onChange={() => undefined}
        ariaLabel="Tag filter"
        allowCreate={false}
      />
    );

    await userEvent.click(screen.getByRole("textbox", { name: "Tag filter" }));

    expect(await screen.findByText("coffee")).toBeInTheDocument();
    expect(shell.querySelector(".tag-multiselect-menu")).toBeNull();
    expect(document.body.querySelector(".tag-multiselect-menu")).not.toBeNull();
  });

  it("renders single-select menus outside the workspace card", async () => {
    const shell = renderInsideWorkspace(
      <SingleSelect
        options={[{ value: "food", label: "Food" }]}
        value=""
        onChange={() => undefined}
        ariaLabel="Category"
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Category" }));

    expect(await screen.findByRole("option", { name: "Food" })).toBeInTheDocument();
    expect(shell.querySelector(".single-select-menu")).toBeNull();
    expect(document.body.querySelector(".single-select-menu")).not.toBeNull();
  });

  it("renders creatable select menus outside the workspace card", async () => {
    const shell = renderInsideWorkspace(
      <CreatableSingleSelect
        options={["Cafe"]}
        value=""
        onChange={() => undefined}
        ariaLabel="Entity"
      />
    );

    await userEvent.click(screen.getByRole("textbox", { name: "Entity" }));

    expect(await screen.findByText("Cafe")).toBeInTheDocument();
    expect(shell.querySelector(".creatable-select-menu")).toBeNull();
    expect(document.body.querySelector(".creatable-select-menu")).not.toBeNull();
  });
});
