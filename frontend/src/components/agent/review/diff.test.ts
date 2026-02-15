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

  it("builds delete diff from target snapshot", () => {
    const diff = buildProposalDiff("delete_tag", {
      name: "groceries",
      target: { name: "groceries", color: "#7fb069" }
    });

    expect(diff.mode).toBe("delete");
    expect(diff.lines.every((line) => line.sign === "-")).toBe(true);
    expect(diff.lines.map((line) => line.path)).toEqual(["color", "name"]);
  });

  it("normalizes record equality regardless of key order", () => {
    expect(jsonRecordsAreEquivalent({ a: 1, b: { c: 2, d: 3 } }, { b: { d: 3, c: 2 }, a: 1 })).toBe(true);
  });
});
