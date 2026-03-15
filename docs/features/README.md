# Feature Documentation

This directory holds cross-cutting feature docs that describe product flows spanning multiple packages or layers.

## Files

- `agent_billing_assistant.md`: detailed billing assistant runtime, prompt, tool, and CLI contract doc.
- `agent_cli_workspace.md`: workspace-terminal and `bh` execution model for the agent.
- `entry_lifecycle.md`: entry creation, editing, grouping, deletion, and related review/apply flow references.
- `dashboard_analytics.md`: dashboard KPI, chart, and analytics behavior across backend and clients.
- `account_reconciliation.md`: account workspace, reconciliation, and snapshot behavior across backend and clients.

## Scope

- cross-cutting product behavior that spans backend, API, and one or more clients
- feature-level flows that do not belong to a single package-local docs tree
