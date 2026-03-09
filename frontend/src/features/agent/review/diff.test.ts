import { describe, expect, it } from "vitest";

import { buildProposalDiff, jsonRecordsAreEquivalent } from "./diff";

describe("proposal diff", () => {
  it("builds reviewer override diff for create proposals", () => {
    const diff = buildProposalDiff(
      "create_entry",
      { name: "Lunch", amount_minor: 1200, currency_code: "CAD" },
      { name: "Lunch", amount_minor: 1350, currency_code: "CAD" }
    );

    expect(diff.mode).toBe("update");
    expect(diff.title).toBe("Reviewer edits");
    expect(diff.note).toContain("reviewer-edited payload");
    expect(diff.stats.changed).toBe(1);
  });

  it("builds update patch diff with metadata", () => {
    const diff = buildProposalDiff("update_entry", {
      selector: { date: "2026-02-15", name: "Lunch", amount_minor: 1200 },
      current: { name: "Lunch", amount_minor: 1200 },
      patch: { amount_minor: 1350 }
    });

    expect(diff.mode).toBe("update");
    expect(diff.stats.changed).toBe(1);
    expect(diff.metadata.some((item) => item.label === "Selector")).toBe(true);
  });

  it("uses reviewer overrides for update proposal previews", () => {
    const diff = buildProposalDiff(
      "update_entity",
      {
        name: "Molly Tea",
        current: { name: "Molly Tea", category: "merchant" },
        patch: { category: "cafe" }
      },
      {
        name: "Molly Tea",
        patch: { category: "restaurant" }
      }
    );

    expect(diff.mode).toBe("update");
    expect(diff.note).toContain("reviewer-edited payload");
    expect(diff.lines.some((line) => line.value === "restaurant")).toBe(true);
    expect(diff.metadata.some((item) => item.label === "Patch fields" && item.value === "1")).toBe(true);
  });

  it("builds account update diffs from account records", () => {
    const diff = buildProposalDiff(
      "update_account",
      {
        name: "Travel Card",
        current: {
          name: "Travel Card",
          currency_code: "USD",
          is_active: true,
          markdown_body: null
        },
        patch: {
          currency_code: "CAD",
          is_active: false
        }
      },
      {
        name: "Travel Card",
        patch: {
          currency_code: "CAD",
          is_active: false,
          markdown_body: "Trip only"
        }
      }
    );

    expect(diff.mode).toBe("update");
    expect(diff.note).toContain("reviewer-edited payload");
    expect(diff.lines.some((line) => line.path === "currency" && line.value === "CAD")).toBe(true);
    expect(diff.lines.some((line) => line.path === "active" && line.value === "false")).toBe(true);
    expect(diff.lines.some((line) => line.path === "notes" && line.value === "Trip only")).toBe(true);
  });

  it("builds delete diff from target snapshot", () => {
    const diff = buildProposalDiff("delete_tag", {
      name: "groceries",
      target: { name: "groceries", color: "#7fb069" }
    });

    expect(diff.mode).toBe("delete");
    expect(diff.lines.every((line) => line.sign === "-")).toBe(true);
    expect(diff.lines.map((line) => line.path)).toEqual(["name", "color"]);
  });

  it("builds account delete diffs from impact previews", () => {
    const diff = buildProposalDiff("delete_account", {
      name: "Travel Card",
      impact_preview: {
        entry_count: 2,
        snapshot_count: 1,
        current: {
          name: "Travel Card",
          currency_code: "CAD",
          is_active: false,
          markdown_body: "Trip only"
        }
      }
    });

    expect(diff.mode).toBe("delete");
    expect(diff.lines.every((line) => line.sign === "-")).toBe(true);
    expect(diff.metadata.some((item) => item.label === "Impacted entries" && item.value === "2")).toBe(true);
    expect(diff.metadata.some((item) => item.label === "Snapshots" && item.value === "1")).toBe(true);
  });

  it("normalizes record equality regardless of key order", () => {
    expect(jsonRecordsAreEquivalent({ a: 1, b: { c: 2, d: 3 } }, { b: { d: 3, c: 2 }, a: 1 })).toBe(true);
  });

  it("formats entry fields with friendly labels and ordering", () => {
    const diff = buildProposalDiff("create_entry", {
      tags: ["food", "daily"],
      currency_code: "CAD",
      to_entity: "Coffee Shop",
      amount_minor: 1230,
      kind: "EXPENSE",
      from_entity: "Main Checking",
      date: "2026-02-18",
      name: "Coffee"
    });

    expect(diff.lines.map((line) => line.path)).toEqual([
      "date",
      "name",
      "kind",
      "amount",
      "currency",
      "from",
      "to",
      "tags"
    ]);
    expect(diff.lines.find((line) => line.path === "amount")?.value).toBe("12.3");
    expect(diff.lines.find((line) => line.path === "currency")?.value).toBe("CAD");
  });

  it("renders create-group-member proposals as a group assignment change", () => {
    const diff = buildProposalDiff("create_group_member", {
      action: "add",
      group_ref: { group_id: "group-1234" },
      entry_ref: { entry_id: "entry-1111" },
      child_group_ref: null,
      member_role: "CHILD",
      group_preview: { name: "Rent Timeline", group_type: "SPLIT" },
      member_preview: {
        date: "2026-03-01",
        name: "March Rent",
        kind: "EXPENSE",
        amount_minor: 250000,
        currency_code: "USD",
        from_entity: "Main Checking",
        to_entity: "Landlord",
        tags: ["housing"]
      }
    });

    expect(diff.mode).toBe("update");
    expect(diff.lines.some((line) => line.path === "group" && line.value === "Rent Timeline")).toBe(true);
    expect(diff.lines.some((line) => line.path === "date")).toBe(false);
    expect(diff.lines.some((line) => line.path === "name")).toBe(false);
    expect(diff.lines.some((line) => line.path === "amount")).toBe(false);
    expect(diff.lines.some((line) => line.path === "member ref")).toBe(false);
    expect(diff.lines.some((line) => line.path === "parent group ref")).toBe(false);
    expect(diff.metadata.some((line) => line.label === "Group" && line.value === "Rent Timeline")).toBe(true);
  });

  it("builds reviewer override diff for create-group-member split-role edits", () => {
    const diff = buildProposalDiff(
      "create_group_member",
      {
        action: "add",
        group_ref: { group_id: "group-1234" },
        entry_ref: { entry_id: "entry-1111" },
        child_group_ref: null,
        member_role: "CHILD",
        group_preview: { name: "Rent Timeline", group_type: "SPLIT" },
        member_preview: {
          date: "2026-03-01",
          name: "March Rent",
          kind: "EXPENSE",
          amount_minor: 250000,
          currency_code: "USD",
          from_entity: "Main Checking",
          to_entity: "Landlord",
          tags: ["housing"]
        }
      },
      {
        action: "add",
        group_ref: { group_id: "group-1234" },
        entry_ref: { entry_id: "entry-2222" },
        child_group_ref: null,
        member_role: "PARENT"
      }
    );

    expect(diff.mode).toBe("update");
    expect(diff.note).toContain("reviewer-edited payload");
    expect(diff.lines.some((line) => line.path === "split role" && line.value === "PARENT")).toBe(true);
    expect(diff.lines.some((line) => line.path === "member ref")).toBe(false);
    expect(diff.metadata.some((line) => line.label === "Group type" && line.value === "SPLIT")).toBe(true);
  });

  it("renders delete-group-member proposals as a group removal change", () => {
    const diff = buildProposalDiff("delete_group_member", {
      action: "remove",
      group_ref: { group_id: "group-1234" },
      entry_ref: { entry_id: "entry-1111" },
      child_group_ref: null,
      group_preview: { name: "Rent Timeline", group_type: "RECURRING" },
      member_preview: {
        date: "2026-03-01",
        name: "March Rent",
        kind: "EXPENSE",
        amount_minor: 250000,
        currency_code: "USD",
        from_entity: "Main Checking",
        to_entity: "Landlord",
        tags: ["housing"]
      }
    });

    expect(diff.mode).toBe("update");
    expect(diff.lines.some((line) => line.sign === "-" && line.path === "group" && line.value === "Rent Timeline")).toBe(true);
    expect(diff.lines.some((line) => line.path === "date")).toBe(false);
    expect(diff.lines.some((line) => line.path === "name")).toBe(false);
    expect(diff.metadata.some((line) => line.label === "Group" && line.value === "Rent Timeline")).toBe(true);
  });

  it("builds update-group diffs from current group snapshots", () => {
    const diff = buildProposalDiff("update_group", {
      group_id: "group-1234",
      current: {
        name: "Monthly Bills",
        group_type: "RECURRING"
      },
      patch: {
        name: "Core Bills"
      }
    });

    expect(diff.mode).toBe("update");
    expect(diff.lines.some((line) => line.path === "name" && line.value === "Core Bills")).toBe(true);
    expect(diff.metadata.some((line) => line.label === "Group ID" && line.value === "group-1234")).toBe(true);
  });
});
