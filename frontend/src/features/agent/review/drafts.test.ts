import { describe, expect, it } from "vitest";

import { buildChangeItem } from "../../../test/factories/agent";
import {
  buildAccountOverrideState,
  buildAccountReviewDraft,
  buildGroupMembershipOverrideState,
  buildGroupMembershipReviewDraft,
  buildGroupOverrideState,
  buildGroupReviewDraft,
  buildEntityOverrideState,
  buildEntityReviewDraft,
  buildEntryOverrideState,
  buildEntryReviewDraft,
  buildTagOverrideState,
  buildTagReviewDraft
} from "./drafts";

describe("review draft serialization", () => {
  it("builds a full payload override for create-entry edits", () => {
    const item = buildChangeItem({
      change_type: "create_entry",
      payload_json: {
        kind: "EXPENSE",
        date: "2026-03-01",
        name: "Lunch",
        amount_minor: 1200,
        currency_code: "USD",
        from_entity: "Main Checking",
        to_entity: "Cafe",
        tags: ["food"],
        markdown_notes: "Original note"
      }
    });

    const draft = {
      ...buildEntryReviewDraft(item, "USD"),
      name: "Team lunch",
      amountMajor: "13.50",
      tags: ["food", "team"]
    };

    expect(buildEntryOverrideState(item, draft, "USD")).toEqual({
      hasChanges: true,
      payloadOverride: {
        kind: "EXPENSE",
        date: "2026-03-01",
        name: "Team lunch",
        amount_minor: 1350,
        currency_code: "USD",
        from_entity: "Main Checking",
        to_entity: "Cafe",
        tags: ["food", "team"],
        markdown_notes: "Original note"
      },
      validationError: null
    });
  });

  it("rebuilds update-entry overrides from the full merged entry form", () => {
    const item = buildChangeItem({
      change_type: "update_entry",
      payload_json: {
        selector: {
          date: "2026-03-01",
          name: "Lunch",
          amount_minor: 1200,
          from_entity: "Main Checking",
          to_entity: "Cafe"
        },
        patch: {
          name: "Lunch with team"
        },
        target: {
          date: "2026-03-01",
          kind: "EXPENSE",
          name: "Lunch",
          amount_minor: 1200,
          currency_code: "USD",
          from_entity: "Main Checking",
          to_entity: "Cafe",
          tags: ["food"],
          markdown_notes: "Receipt attached"
        }
      }
    });

    const draft = {
      ...buildEntryReviewDraft(item, "USD"),
      amountMajor: "13.50",
      markdownNotes: "Receipt attached\nReviewed by finance"
    };

    expect(buildEntryOverrideState(item, draft, "USD")).toEqual({
      hasChanges: true,
      payloadOverride: {
        selector: {
          date: "2026-03-01",
          name: "Lunch",
          amount_minor: 1200,
          from_entity: "Main Checking",
          to_entity: "Cafe"
        },
        patch: {
          name: "Lunch with team",
          amount_minor: 1350,
          markdown_notes: "Receipt attached\nReviewed by finance"
        }
      },
      validationError: null
    });
  });

  it("emits an explicit no-op patch when an update-entry edit reverts the agent patch", () => {
    const item = buildChangeItem({
      change_type: "update_entry",
      payload_json: {
        selector: {
          date: "2026-03-01",
          name: "Lunch",
          amount_minor: 1200,
          from_entity: "Main Checking",
          to_entity: "Cafe"
        },
        patch: {
          name: "Lunch with team"
        },
        target: {
          date: "2026-03-01",
          kind: "EXPENSE",
          name: "Lunch",
          amount_minor: 1200,
          currency_code: "USD",
          from_entity: "Main Checking",
          to_entity: "Cafe",
          tags: ["food"],
          markdown_notes: null
        }
      }
    });

    const draft = {
      ...buildEntryReviewDraft(item, "USD"),
      name: "Lunch"
    };

    expect(buildEntryOverrideState(item, draft, "USD")).toEqual({
      hasChanges: true,
      payloadOverride: {
        selector: {
          date: "2026-03-01",
          name: "Lunch",
          amount_minor: 1200,
          from_entity: "Main Checking",
          to_entity: "Cafe"
        },
        patch: {
          name: "Lunch"
        }
      },
      validationError: null
    });
  });

  it("serializes create and update tag drafts within the review contract", () => {
    const createItem = buildChangeItem({
      change_type: "create_tag",
      payload_json: {
        name: "subscriptions",
        type: "recurring"
      }
    });
    const updateItem = buildChangeItem({
      change_type: "update_tag",
      payload_json: {
        name: "subscriptions",
        current: {
          name: "subscriptions",
          type: "recurring"
        },
        patch: {
          type: "monthly"
        }
      }
    });

    expect(
      buildTagOverrideState(createItem, {
        ...buildTagReviewDraft(createItem),
        name: "streaming",
        type: "media"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "streaming",
        type: "media"
      },
      validationError: null
    });

    expect(
      buildTagOverrideState(updateItem, {
        ...buildTagReviewDraft(updateItem),
        type: "recurring"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "subscriptions",
        patch: {
          type: "recurring"
        }
      },
      validationError: null
    });
  });

  it("serializes create and update entity drafts within the review contract", () => {
    const createItem = buildChangeItem({
      change_type: "create_entity",
      payload_json: {
        name: "Molly Tea",
        category: "merchant"
      }
    });
    const updateItem = buildChangeItem({
      change_type: "update_entity",
      payload_json: {
        name: "Molly Tea",
        current: {
          name: "Molly Tea",
          category: "merchant"
        },
        patch: {
          category: "food"
        }
      }
    });

    expect(
      buildEntityOverrideState(createItem, {
        ...buildEntityReviewDraft(createItem),
        name: "Molly Tea Downtown",
        category: "cafe"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "Molly Tea Downtown",
        category: "cafe"
      },
      validationError: null
    });

    expect(
      buildEntityOverrideState(updateItem, {
        ...buildEntityReviewDraft(updateItem),
        category: "merchant"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "Molly Tea",
        patch: {
          category: "merchant"
        }
      },
      validationError: null
    });
  });

  it("serializes create and update account drafts within the review contract", () => {
    const createItem = buildChangeItem({
      change_type: "create_account",
      payload_json: {
        name: "Travel Card",
        currency_code: "USD",
        is_active: true,
        markdown_body: null
      }
    });
    const updateItem = buildChangeItem({
      change_type: "update_account",
      payload_json: {
        name: "Travel Card",
        current: {
          name: "Travel Card",
          currency_code: "USD",
          is_active: true,
          markdown_body: null
        },
        patch: {
          is_active: false
        }
      }
    });

    expect(
      buildAccountOverrideState(createItem, {
        ...buildAccountReviewDraft(createItem),
        currencyCode: "CAD",
        markdownBody: "Trip only"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "Travel Card",
        currency_code: "CAD",
        is_active: true,
        markdown_body: "Trip only"
      },
      validationError: null
    });

    expect(
      buildAccountOverrideState(updateItem, {
        ...buildAccountReviewDraft(updateItem),
        name: "Travel Card CAD",
        markdownBody: "Closed after trip"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "Travel Card",
        patch: {
          name: "Travel Card CAD",
          is_active: false,
          markdown_body: "Closed after trip"
        }
      },
      validationError: null
    });
  });

  it("serializes create and update group drafts within the review contract", () => {
    const createItem = buildChangeItem({
      change_type: "create_group",
      payload_json: {
        name: "Monthly Bills",
        group_type: "RECURRING"
      }
    });
    const updateItem = buildChangeItem({
      change_type: "update_group",
      payload_json: {
        group_id: "group-1234",
        current: {
          name: "Monthly Bills",
          group_type: "RECURRING"
        },
        patch: {
          name: "Core Bills"
        }
      }
    });

    expect(
      buildGroupOverrideState(createItem, {
        ...buildGroupReviewDraft(createItem),
        name: "Core Bills"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        name: "Core Bills",
        group_type: "RECURRING"
      },
      validationError: null
    });

    expect(
      buildGroupOverrideState(updateItem, {
        ...buildGroupReviewDraft(updateItem),
        name: "Monthly Bills"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        group_id: "group-1234",
        patch: {
          name: "Monthly Bills"
        }
      },
      validationError: null
    });
  });

  it("serializes add-member group drafts within the review contract while keeping pending refs locked", () => {
    const item = buildChangeItem({
      change_type: "create_group_member",
      payload_json: {
        action: "add",
        group_ref: {
          create_group_proposal_id: "proposal-group-1234"
        },
        entry_ref: {
          entry_id: "entry-1234"
        },
        child_group_ref: null,
        member_role: "CHILD",
        group_preview: {
          name: "Rent Timeline",
          group_type: "SPLIT"
        },
        member_preview: {
          name: "March Rent",
          resource_type: "entry"
        }
      }
    });

    expect(
      buildGroupMembershipOverrideState(item, {
        ...buildGroupMembershipReviewDraft(item),
        entryId: "entry-5678",
        memberRole: "PARENT"
      })
    ).toEqual({
      hasChanges: true,
      payloadOverride: {
        action: "add",
        group_ref: {
          create_group_proposal_id: "proposal-group-1234"
        },
        entry_ref: {
          entry_id: "entry-5678"
        },
        child_group_ref: null,
        member_role: "PARENT"
      },
      validationError: null
    });
  });
});
