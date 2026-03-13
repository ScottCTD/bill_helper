# ADR 0006: Adopt LLM-Oriented Design Policy For Non-iOS Code

- Status: accepted
- Date: 2026-03-13
- Deciders: Bill Helper maintainers

## Context

The repository already enforces thin routers, service-owned orchestration, split agent tool registries, and stable service seams, but the codebase did not have one explicit cross-repo policy for LLM-oriented structure. A new design baseline now exists in `docs/llm_oriented_design.md`, and the non-iOS codebase needs consistent enforcement for file size, calling specs, explicit contracts, and slim orchestrators.

The iOS client is intentionally excluded from this migration batch because it is being deferred as a separate follow-up effort.

## Decision

Adopt `docs/llm_oriented_design.md` as the mandatory design baseline for all non-iOS production code.

Enforce the policy through:

- explicit hard rules in `AGENTS.md`
- a repo-wide checker command, `uv run python scripts/check_llm_design.py`
- targeted structural refactors for oversized or mixed-responsibility modules
- required calling spec blocks on non-iOS production modules

Keep `ios/` as an explicitly documented temporary exception until a dedicated iOS cleanup pass is scheduled.

## Consequences

- New non-iOS code must satisfy the LLM-oriented hard rules by default.
- Existing non-iOS legacy modules must be refactored until they satisfy the same rules.
- Tooling and docs now need to stay synchronized with the new checker and policy text.
- The repository will not claim full repo-wide adherence while the iOS exception remains active.
