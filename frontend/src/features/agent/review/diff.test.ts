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

  it("builds delete diff from target snapshot", () => {
    const diff = buildProposalDiff("delete_tag", {
      name: "groceries",
      target: { name: "groceries", color: "#7fb069" }
    });

    expect(diff.mode).toBe("delete");
    expect(diff.lines.every((line) => line.sign === "-")).toBe(true);
    expect(diff.lines.map((line) => line.path)).toEqual(["name", "color"]);
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
});
