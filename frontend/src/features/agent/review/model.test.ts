/**
 * CALLING SPEC:
 * - Purpose: unit tests for agent thread review ordering helpers in `model.ts`.
 * - Inputs: vitest runner.
 * - Outputs: assertions on `buildThreadReviewItems` and TOC keys.
 * - Side effects: none.
 */
import { describe, expect, it } from "vitest";

import { buildChangeItem, buildRun } from "../../../test/factories/agent";
import { buildThreadReviewItems, proposalReviewOrdinal, proposalTocGroupKey } from "./model";
import { groupReviewItems } from "./modalHelpers";

describe("proposalReviewOrdinal", () => {
  it("orders tags before entries and group members after entries", () => {
    expect(proposalReviewOrdinal("create_tag")).toBeLessThan(proposalReviewOrdinal("create_entry"));
    expect(proposalReviewOrdinal("create_entry")).toBeLessThan(proposalReviewOrdinal("create_group_member"));
  });
});

describe("proposalTocGroupKey", () => {
  it("splits group shell from membership", () => {
    expect(proposalTocGroupKey("create_group")).toBe("group");
    expect(proposalTocGroupKey("create_group_member")).toBe("group_member");
  });
});

describe("buildThreadReviewItems", () => {
  it("sorts by review ordinal before created_at", () => {
    const entry = buildChangeItem({
      id: "entry-item",
      change_type: "create_entry",
      created_at: "2026-01-01T12:00:00Z",
      payload_json: {
        kind: "EXPENSE",
        date: "2026-01-01",
        name: "Later entry",
        amount_minor: 100,
        from_entity: "A",
        to_entity: "B",
        tags: []
      }
    });
    const tag = buildChangeItem({
      id: "tag-item",
      change_type: "create_tag",
      created_at: "2026-01-02T12:00:00Z",
      payload_json: { name: "alpha", type: "daily" }
    });
    const run = buildRun({
      id: "run-1",
      created_at: "2026-01-01T00:00:00Z",
      change_items: [entry, tag]
    });
    const ordered = buildThreadReviewItems([run]);
    expect(ordered.map((row) => row.item.id)).toEqual(["tag-item", "entry-item"]);
  });

  it("sorts group member after entry when member is older", () => {
    const member = buildChangeItem({
      id: "member-item",
      change_type: "create_group_member",
      created_at: "2026-01-01T08:00:00Z",
      payload_json: {
        group_ref: { create_group_proposal_id: "g1" },
        target: { entry_ref: { create_entry_proposal_id: "e1" } },
        group_preview: { name: "G" },
        member_preview: { name: "M" }
      }
    });
    const entry = buildChangeItem({
      id: "entry-item",
      change_type: "create_entry",
      created_at: "2026-01-02T08:00:00Z",
      payload_json: {
        kind: "EXPENSE",
        date: "2026-01-02",
        name: "E",
        amount_minor: 50,
        from_entity: "A",
        to_entity: "B",
        tags: []
      }
    });
    const run = buildRun({
      id: "run-1",
      created_at: "2026-01-01T00:00:00Z",
      change_items: [member, entry]
    });
    const ordered = buildThreadReviewItems([run]);
    expect(ordered.map((row) => row.item.id)).toEqual(["entry-item", "member-item"]);
  });
});

describe("groupReviewItems", () => {
  it("lists Group members section after Entries", () => {
    const entry = buildChangeItem({
      id: "e1",
      change_type: "create_entry",
      created_at: "2026-01-01T12:00:00Z",
      payload_json: {
        kind: "EXPENSE",
        date: "2026-01-01",
        name: "X",
        amount_minor: 1,
        from_entity: "A",
        to_entity: "B",
        tags: []
      }
    });
    const member = buildChangeItem({
      id: "m1",
      change_type: "create_group_member",
      created_at: "2026-01-01T11:00:00Z",
      payload_json: {
        group_ref: {},
        target: { entry_ref: {} },
        group_preview: { name: "G" },
        member_preview: { name: "M" }
      }
    });
    const run = buildRun({ id: "r1", created_at: "2026-01-01T00:00:00Z", change_items: [member, entry] });
    const items = buildThreadReviewItems([run]);
    const groups = groupReviewItems(items);
    const keys = groups.map((g) => g.key);
    expect(keys.indexOf("entry")).toBeGreaterThan(-1);
    expect(keys.indexOf("group_member")).toBeGreaterThan(-1);
    expect(keys.indexOf("entry")).toBeLessThan(keys.indexOf("group_member"));
  });
});
