import { describe, expect, it } from "vitest";

import { buildEditForm, normalizeNullableText, normalizeOptionalText, toDateLabel } from "./helpers";
import type { Account } from "../../lib/types";

describe("accounts helpers", () => {
  it("formats date labels defensively", () => {
    expect(toDateLabel("")).toBe("-");
    expect(toDateLabel("2026-02-15T12:30:00Z")).toBe("2026-02-15");
  });

  it("normalizes optional and nullable text inputs", () => {
    expect(normalizeOptionalText("  ")).toBeUndefined();
    expect(normalizeOptionalText("  Savings  ")).toBe("Savings");

    expect(normalizeNullableText("  ")).toBeNull();
    expect(normalizeNullableText("  chequing  ")).toBe("chequing");
  });

  it("builds edit form state with owner fallback", () => {
    const account: Account = {
      id: "acc-1",
      owner_user_id: null,
      entity_id: null,
      name: "Main account",
      institution: null,
      account_type: "checking",
      currency_code: "CAD",
      is_active: true,
      created_at: "2026-02-15T00:00:00Z",
      updated_at: "2026-02-15T00:00:00Z"
    };

    expect(buildEditForm(account, "user-1")).toEqual({
      owner_user_id: "user-1",
      name: "Main account",
      institution: "",
      account_type: "checking",
      currency_code: "CAD",
      is_active: true
    });
  });
});
