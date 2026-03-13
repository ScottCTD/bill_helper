# CLI as Unified App Interface

## Status
- Proposed

## Summary
Build a first-class CLI for Bill Helper that serves two roles: a practical human client for local workflows, and a unified execution surface for the agent. Instead of expanding the number of bespoke tools, we expose a stable command interface over the existing service layer and let the agent use that surface through structured calls.

## Goal
Create a canonical CLI that mirrors core app capabilities and can be safely used by both humans and the agent, while keeping business logic in shared services and preserving the proposal/review workflow.

## Why
- Gives the product another useful client surface for developers and power users
- Reduces agent tool sprawl and prompt/context overhead
- Creates one consistent operational interface across app, automation, and agent usage
- Improves maintainability, observability, and long-term extensibility

## Core Direction
- Add a `billengine` CLI as a stable interface over the existing domain services
- Treat the CLI as a client layer, not a new home for business logic
- Design the CLI so the agent can use it as a unified tool surface
- Keep agent-facing flows aligned with proposal/review semantics rather than direct unchecked mutation

## Principles
- Shared service layer remains the source of truth
- CLI commands should be stable, predictable, and scriptable
- Machine-readable output should be a first-class concern
- Agent access should be constrained to safe, intentional commands
- Exact command shape is flexible as long as the interface stays coherent

## Scope
- Define the top-level CLI structure
- Cover core domains such as entries, accounts, groups, proposals, threads, reviews, and status
- Add structured output support for command results
- Integrate the CLI into the agent runtime as a unified execution surface
- Reuse existing application services instead of duplicating logic

## Non-Goals
- Finalizing every command or flag up front
- Reworking business logic for CLI-specific needs
- Allowing the agent to use arbitrary unrestricted shell access
- Bypassing review or approval workflows

## Deliverables
- A minimal but coherent CLI surface for core app actions
- A clear mapping from CLI commands to shared services
- Structured output mode suitable for agent consumption
- A lightweight agent integration path using the CLI as the backend interface
- Basic documentation for human usage and agent-facing expectations

## Success Criteria
- Humans can perform common local workflows through the CLI
- The agent can use the CLI as a unified interface instead of many separate tools
- Core flows remain consistent with existing app behavior and review gates
- The interface is simple enough to grow without becoming fragmented