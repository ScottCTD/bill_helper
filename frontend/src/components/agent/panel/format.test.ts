import { describe, expect, it } from "vitest";

import { formatUsdCost, formatUsagePercent, formatUsageTokens } from "./format";

describe("agent usage formatting", () => {
  it("formats token metrics in compact K units", () => {
    expect(formatUsageTokens(null)).toBe("-");
    expect(formatUsageTokens(0)).toBe("0.00K");
    expect(formatUsageTokens(123)).toBe("0.12K");
    expect(formatUsageTokens(1980)).toBe("1.98K");
    expect(formatUsageTokens(44829)).toBe("44.83K");
  });

  it("formats cache hit rate percentages", () => {
    expect(formatUsagePercent(null)).toBe("-");
    expect(formatUsagePercent(0.049)).toBe("4.9%");
    expect(formatUsagePercent(0.128)).toBe("13%");
  });

  it("formats USD costs to 2 significant digits", () => {
    expect(formatUsdCost(null)).toBe("-");
    expect(formatUsdCost(0.0031)).toContain("0.0031".slice(0, 5));
    expect(formatUsdCost(1.234)).toContain("1.2");
  });
});
