"""Canonical `bh` command reference and prompt-friendly cheat sheet.

CALLING SPEC:
    render_bh_cheat_sheet() -> str
    compact_schema_for(render_key) -> str | None

Inputs:
    - optional render key names from the CLI output layer
Outputs:
    - concise markdown guidance for agent prompt/doc embedding and compact row schemas
Side effects:
    - none
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompactSchema:
    render_key: str
    schema: str


_COMPACT_SCHEMAS: tuple[CompactSchema, ...] = (
    CompactSchema("entries_list", "id|date|kind|amount_minor|currency|name|from|to|tags"),
    CompactSchema(
        "entries_detail",
        "id|date|kind|amount_minor|currency|name|from|to|tags|account_id|direct_group_id|direct_group_role",
    ),
    CompactSchema("accounts_list", "id|name|currency|active"),
    CompactSchema("accounts_snapshots", "id|date|balance_minor|note"),
    CompactSchema("accounts_reconciliation", "start|end|open|tracked_change_minor|bank_change_minor|delta_minor|entry_count"),
    CompactSchema("groups_list", "id|type|name|descendants|first_date|last_date"),
    CompactSchema("groups_nodes", "node_id|node_type|name|member_role|date|kind|amount_minor|group_type|descendants"),
    CompactSchema("groups_edges", "source|target|relation"),
    CompactSchema("entities_list", "name|category"),
    CompactSchema("tags_list", "name|type|description"),
    CompactSchema("proposals_list", "id|status|change_type|summary"),
    CompactSchema("proposals_detail", "id|status|proposal_type|change_action|change_type|summary|applied_resource"),
)


def compact_schema_for(render_key: str) -> str | None:
    for item in _COMPACT_SCHEMAS:
        if item.render_key == render_key:
            return item.schema
    return None


def render_bh_cheat_sheet() -> str:
    schema_lines = "\n".join(
        f"- `{item.render_key}` -> `{item.schema}`"
        for item in _COMPACT_SCHEMAS
        if item.render_key
        in {
            "entries_list",
            "accounts_list",
            "groups_list",
            "entities_list",
            "tags_list",
            "proposals_list",
        }
    )
    return (
        "Use `bh` for Bill Helper app reads and current-thread proposal creation.\n"
        "\n"
        "- Agent calls should expect `compact` output by default; use `--format text` or `--format json` only when needed.\n"
        "- List output uses 8-character ids when unique in the current result set; collisions fall back to full ids.\n"
        "- Compact output is line-oriented: one `schema:` line defines column order, then one escaped `|`-delimited row per record.\n"
        "- Read commands work in the human IDE terminal. Any `create`, `update`, `remove`, `add-member`, `remove-member`, or `proposals` command requires the current agent-run env (`BH_THREAD_ID` and `BH_RUN_ID`).\n"
        "- Inspect before mutating: read entries/tags/accounts/entities/groups/proposals first, then create resource-scoped proposals.\n"
        "\n"
        "Common commands:\n"
        "- `bh status`\n"
        "- `bh entries list [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--kind KIND] [--currency CODE] [--account-id ID] [--source TEXT] [--tag NAME] [--filter-group-id ID] [--limit N] [--offset N]`\n"
        "- `bh entries get <entry_id>`\n"
        "- `bh entries create (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh entries update <entry_id> (--patch-json JSON | --patch-file PATH)`\n"
        "- `bh entries remove <entry_id>`\n"
        "- `bh accounts list`\n"
        "- `bh accounts snapshots <account_id>`\n"
        "- `bh accounts reconciliation <account_id> [--as-of YYYY-MM-DD]`\n"
        "- `bh accounts create (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh accounts update <account_ref> (--patch-json JSON | --patch-file PATH)`\n"
        "- `bh accounts remove <account_ref>`\n"
        "- `bh groups list`\n"
        "- `bh groups get <group_id>`\n"
        "- `bh groups create (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh groups update <group_id> (--patch-json JSON | --patch-file PATH)`\n"
        "- `bh groups remove <group_id>`\n"
        "- `bh groups add-member (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh groups remove-member (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh entities list`\n"
        "- `bh entities create (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh entities update <entity_name> (--patch-json JSON | --patch-file PATH)`\n"
        "- `bh entities remove <entity_name>`\n"
        "- `bh tags list`\n"
        "- `bh tags create (--payload-json JSON | --payload-file PATH)`\n"
        "- `bh tags update <tag_name> (--patch-json JSON | --patch-file PATH)`\n"
        "- `bh tags remove <tag_name>`\n"
        "- `bh proposals list [--proposal-type TYPE] [--proposal-status STATUS] [--change-action ACTION] [--proposal-id ID] [--limit N]`\n"
        "- `bh proposals get <proposal_id>`\n"
        "\n"
        "Compact list schemas:\n"
        f"{schema_lines}\n"
        "\n"
        "Common flows:\n"
        "- Inspect recent matching entries: `bh entries list --source \"farm boy\" --limit 10`\n"
        "- Inspect current proposal state: `bh proposals list --proposal-status PENDING_REVIEW --limit 20`\n"
        "- Create a tag proposal: `bh tags create --payload-json '{\"name\":\"grocery\",\"type\":\"expense\"}'`\n"
        "- Create an entry-update proposal: `bh entries update 8bf2fa83 --patch-json '{\"tags\":[\"grocery\",\"one_time\"]}'`\n"
        "- Create an account proposal: `bh accounts create --payload-json '{\"name\":\"Wealthsimple Cash\",\"currency_code\":\"CAD\",\"is_active\":true}'`\n"
        "- Create a group-membership add proposal: `bh groups add-member --payload-json '{\"action\":\"add\",\"group_ref\":{\"group_id\":\"a971c92e\"},\"target\":{\"target_type\":\"entry\",\"entry_ref\":{\"entry_id\":\"8bf2fa83\"}}}'`\n"
    )
