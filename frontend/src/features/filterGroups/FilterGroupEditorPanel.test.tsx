import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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

function ControlledEditor({
  filterGroup,
  onSubmit
}: {
  filterGroup: FilterGroup;
  onSubmit: (nextFilterGroup: FilterGroup) => void;
}) {
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
        onSubmit={() =>
          onSubmit({
            ...filterGroup,
            name: session.formState.name,
            description: session.formState.description,
            color: session.formState.color,
            rule: session.formState.rule
          })
        }
      />
    </MemoryRouter>
  );
}

describe("FilterGroupEditorPanel", () => {
  it("uses the shared tag multi-select and shows AND/OR labels instead of the old copy", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const filterGroup = createFilterGroup({
      include: {
        type: "group",
        operator: "AND",
        children: [{ type: "condition", field: "tags", operator: "has_any", value: ["grocery"] }]
      },
      exclude: null
    });

    render(<ControlledEditor filterGroup={filterGroup} onSubmit={onSubmit} />);

    expect(screen.queryByText("All conditions")).not.toBeInTheDocument();
    expect(screen.queryByText("Any condition")).not.toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "AND" }).length).toBeGreaterThan(0);

    await user.click(screen.getByLabelText("Rule tags"));
    await user.type(screen.getByLabelText("Rule tags"), "coffee");
    await user.click(await screen.findByRole("button", { name: /coffee/i }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
    expect(onSubmit.mock.calls[0]?.[0].rule.include.children[0]).toEqual({
      type: "condition",
      field: "tags",
      operator: "has_any",
      value: ["grocery", "coffee"]
    });
  });

  it("opens nested rules in advanced mode and preserves the nested tree shape on save", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
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

    render(<ControlledEditor filterGroup={createFilterGroup(nestedRule)} onSubmit={onSubmit} />);

    expect(screen.getByRole("button", { name: "Guided" })).toBeDisabled();
    expect(screen.getByText(/guided mode stays locked/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Description"), " Updated");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
    expect(onSubmit.mock.calls[0]?.[0].rule).toEqual(nestedRule);
  });
});
