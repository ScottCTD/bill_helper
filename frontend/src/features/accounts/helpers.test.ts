import { describe, expect, it } from "vitest";

import { buildEditForm, normalizeOptionalText, toDateLabel } from "./helpers";
import type { Account } from "../../lib/types";

describe("accounts helpers", () => {
  it("formats date labels defensively", () => {
    expect(toDateLabel("")).toBe("-");
    expect(toDateLabel("2026-02-15T12:30:00Z")).toBe("2026-02-15");
  });

  it("normalizes optional text inputs", () => {
    expect(normalizeOptionalText("  ")).toBeUndefined();
    expect(normalizeOptionalText("  Savings  ")).toBe("Savings");
  });

  it("builds edit form state with owner fallback", () => {
    const account: Account = {
      id: "acc-1",
      owner_user_id: null,
      name: "Main account",
      markdown_body: "## Notes",
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    };

    expect(buildEditForm(account, "user-1")).toEqual({
      owner_user_id: "user-1",
      name: "Main account",
      markdown_body: "## Notes",
      currency_code: "CAD",
      is_active: true
    });
  });
});
