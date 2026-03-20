# Agent review system: dependency and consistency audit

Status: **completed** — tag/entity approval gates and review UI ordering shipped; a full per-`AgentChangeType` policy matrix remains an optional follow-up.

## Shipped (2026-03-20)

- **Backend:** `validate_entry_dependencies_ready_for_approval` extended so `create_entry` / `update_entry` cannot be approved while matching tag names have a pending `create_tag`, or while rejected/apply_failed `create_tag` / `create_entity` / `create_account` proposals would still collide with implicit ensure-by-name behavior.
- **Frontend:** Stable per-change-type ordering for thread review items and TOC; group members grouped after entry-related sections.
- **Tests:** `backend/tests/test_agent_review_entry_tag_dependencies.py`; `frontend/src/features/agent/review/model.test.ts` and related modal tests.
- **Docs:** `docs/api/agent.md`, `backend/docs/agent_subsystem.md`, `frontend/docs/agent_workspace.md`.

## Motivation

Some resource relationships are enforced at **approval** time (e.g. entries vs missing entities vs pending `create_entity` proposals), while others are **not** modeled the same way or are satisfied at **apply** time by creating rows implicitly (e.g. tags on `create_entry` via `ensure_tags`). That asymmetry is easy to miss in UX, docs, and agent prompts, and can feel like bugs (e.g. approving an entry “before” a related `create_tag` proposal).

The `bh groups add-member` / `remove-member` CLI **stays JSON-only** by product decision (see [2026_03_16-groups_member_cli_followup.md](./2026_03_16-groups_member_cli_followup.md)); any future CLI sugar should follow an explicit design pass tied to this audit.

## Audit goals (original scope; partial)

1. **Inventory** every `AgentChangeType` (and any non-agent proposal path) with: payload shape, what it references, and whether references may use **persisted ids** vs **pending proposal ids**.
2. **Map approval gates**: for each change type, document what `backend/services/agent/reviews/dependencies.py` (and related review code) blocks or allows, and what errors users see.
3. **Map apply behavior**: for each change type, document what happens if referenced names/ids are missing (auto-create, hard fail, silent reuse).
4. **Identify inconsistencies** where mental model (“depends on X”) does not match enforcement (tags vs entities vs group members vs accounts).
5. **Deliverables**:
   - A short **policy matrix** (resource A referenced from proposal B: required pre-apply? pending proposal ok? auto-create on apply?).
   - Recommended **fixes or doc-only** outcomes per finding (no drive-by behavior change without an explicit decision).
   - Updates to stable docs (`backend/docs/agent_subsystem.md` or equivalent) once policy is agreed.

## Starting points (non-exhaustive)

- `validate_entry_dependencies_ready_for_approval` — entities only; no tag symmetry.
- `apply_create_entry` / `set_entry_tags` / `ensure_tags` — implicit tag creation vs `create_tag` proposals.
- `CreateGroupMemberPayload` / `DeleteGroupMemberPayload` — proposal ids allowed on add; remove existing-only.
- Group dependency validation in the same `dependencies` module for membership proposals.
- Any ordering assumptions documented in `system_prompt.j2` vs actual enforcement.

## Verification

After any behavioral change from this audit: run the usual backend test suite and `uv run python scripts/check_docs_sync.py`; regenerate `docs/features/system_prompt_example.md` if `backend/cli/reference.py` or the prompt template changes.
