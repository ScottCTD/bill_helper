import { describe, expect, it } from "vitest";

import { includesFilter, normalizeFilterValue, taxonomyTermNames, uniqueOptionValues } from "./catalogs";

describe("catalog helpers", () => {
  it("normalizes filter text", () => {
    expect(normalizeFilterValue("  HeLLo ")).toBe("hello");
  });

  it("matches values with case-insensitive contains logic", () => {
    expect(includesFilter("Coffee Shop", "shop")).toBe(true);
    expect(includesFilter("Coffee Shop", "tea")).toBe(false);
    expect(includesFilter("Coffee Shop", "   ")).toBe(true);
  });

  it("builds sorted unique option values", () => {
    expect(uniqueOptionValues([" Travel ", "travel", "Food", null, "", " food "])).toEqual(["Food", "Travel"]);
  });

  it("extracts taxonomy term names safely", () => {
    expect(taxonomyTermNames(undefined)).toEqual([]);
    expect(
      taxonomyTermNames([
        {
          id: "term-1",
          taxonomy_id: "taxonomy-1",
          name: "Bills",
          normalized_name: "bills",
          parent_term_id: null,
          usage_count: 3
        }
      ])
    ).toEqual(["Bills"]);
  });
});
