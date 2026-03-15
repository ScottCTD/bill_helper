import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { FilterGroupEditorPanel } from "./FilterGroupEditorPanel";
import { createExistingEditorSession, updateSessionFormState } from "./filterGroupEditorState";
import type { FilterGroup, Tag } from "../../lib/types";

const tags: Tag[] = [
  { id: 1, name: "grocery", color: "#33aa66" },
  { id: 2, name: "coffee", color: "#aa6633" },
  { id: 3, name: "housing", color: "#4466cc" }
];

function createFilterGroup(rule: FilterGroup["rule"]): FilterGroup {
  return {
    id: "fg-1",
    key: "custom",
    name: "Routine",
    description: "Regular spending.",
    color: "#64748b",
    is_default: false,
    position: 0,
    rule,
    rule_summary: "kind is expense",
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z"
  };
}

function ControlledEditor({ filterGroup }: { filterGroup: FilterGroup }) {
  const [session, setSession] = useState(() => createExistingEditorSession(filterGroup));

  return (
    <MemoryRouter>
      <FilterGroupEditorPanel
        session={session}
        tags={tags}
        preferredTagName={tags[0]?.name}
        isDirty={JSON.stringify(session.formState) !== JSON.stringify(session.baselineState)}
        isPending={false}
        onChange={(nextFormState) => setSession((current) => updateSessionFormState(current, nextFormState))}
      />
    </MemoryRouter>
  );
}

describe("FilterGroupEditorPanel", () => {
  it("uses the shared tag multi-select and no longer renders the footer save button", async () => {
    const user = userEvent.setup();
    const filterGroup = createFilterGroup({
      include: {
        type: "group",
        operator: "AND",
        children: [{ type: "condition", field: "tags", operator: "has_any", value: ["grocery"] }]
      },
      exclude: null
    });

    render(<ControlledEditor filterGroup={filterGroup} />);

    expect(screen.queryByText("All conditions")).not.toBeInTheDocument();
    expect(screen.queryByText("Any condition")).not.toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "AND" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("Rule tags"));
    await user.type(screen.getByLabelText("Rule tags"), "coffee");
    await user.click(await screen.findByRole("button", { name: /coffee/i }));

    expect(screen.getByDisplayValue("Routine")).toBeInTheDocument();
  });

  it("opens nested rules in advanced mode and keeps guided mode locked", () => {
    const nestedRule: FilterGroup["rule"] = {
      include: {
        type: "group",
        operator: "AND",
        children: [
          { type: "condition", field: "entry_kind", operator: "is", value: "EXPENSE" },
          {
            type: "group",
            operator: "OR",
            children: [
              { type: "condition", field: "tags", operator: "has_any", value: ["grocery"] },
              { type: "condition", field: "is_internal_transfer", operator: "is", value: true }
            ]
          }
        ]
      },
      exclude: null
    };

    render(<ControlledEditor filterGroup={createFilterGroup(nestedRule)} />);

    expect(screen.getByRole("button", { name: "Guided" })).toBeDisabled();
    expect(screen.getByText(/guided mode stays locked/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });
});
