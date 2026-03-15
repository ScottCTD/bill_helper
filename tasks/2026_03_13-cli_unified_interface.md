# CLI as Unified App Interface

## Status

* Proposed

## Priority

* High
* Follows the workspace scaffold
* Should be designed before adding many more bespoke agent tools

## Summary

Build a first-class `billengine` CLI that serves two roles:

* a practical human-facing interface for local and developer workflows
* a unified execution surface for the agent

The CLI should be a thin client over the existing backend service layer. It must not become a second backend, a second business-logic layer, or a direct database writer.

The CLI may run both:

* outside the sandbox container
* inside the per-user workspace container

In both cases, canonical app state remains outside the workspace and is owned by the backend.

## Goal

Create a stable, coherent, machine-friendly command interface that mirrors core Bill Helper capabilities while preserving the current review-gated architecture.

The CLI should reduce tool sprawl, give developers and power users a useful interface, and give the agent one consistent command surface for app operations.

## Core Design Decision

The CLI is an **interface layer**, not an authority layer.

That means:

* business logic stays in shared backend services
* canonical state stays in the backend database and canonical data layer
* the CLI invokes backend-controlled operations
* the CLI may read local workspace files when running inside the sandbox
* the CLI must not directly mutate canonical DB state or canonical data files

## Why

* gives the product a real developer and power-user interface
* reduces the number of bespoke agent tools
* creates one operational language across app, automation, and agent use
* keeps business logic centralized
* aligns with the existing proposal and review workflow
* makes future expansion easier without fragmenting interfaces

## Architectural Position

### Backend is authoritative

Canonical state remains in the backend and canonical data layer, including:

* entries
* accounts
* groups
* entities
* tags
* proposals
* reviews
* threads
* messages
* attachment metadata
* runtime settings

### Workspace is execution-only

The workspace container is for:

* local files under `/workspace`
* read-only canonical files under `/data`
* scripts
* outputs
* scratch work

The workspace is not the source of truth for application state.

### CLI bridges both worlds

The CLI should provide:

* backend-backed app commands
* workspace-aware local commands where appropriate

This allows one coherent interface without blurring authority boundaries.

## Principles

* Shared service layer remains the source of truth for app behavior
* CLI commands should be stable, predictable, and scriptable
* Machine-readable output is a first-class requirement
* Agent-facing mutation must remain review-gated
* The CLI should be coherent, not exhaustive on day one
* The CLI must work well both for humans and for structured agent use
* The CLI must not require direct database access

## Runtime Modes

## 1. Host mode

The CLI runs outside the sandbox.

Typical users:

* developer
* operator
* local power user

Capabilities:

* call backend app operations
* inspect status
* run local workflows
* optionally interact with workspace and canonical files if explicitly supported

## 2. Sandbox mode

The CLI runs inside the per-user workspace container.

Typical user:

* agent

Capabilities:

* call backend app operations
* read `/data`
* read and write `/workspace`

Restrictions:

* no direct canonical DB writes
* no direct canonical file writes
* no bypass of proposal/review workflow

## Command Classes

The CLI should distinguish two broad classes of commands.

## A. App commands

These operate on canonical Bill Helper state through the backend.

Examples:

* entries
* accounts
* groups
* entities
* tags
* proposals
* reviews
* threads
* status
* attachments

These commands must go through backend service calls.

## B. Workspace commands

These operate on local execution context and files.

Examples:

* inspect files under `/workspace`
* inspect files under `/data`
* manage local outputs
* promote a workspace artifact through a backend-controlled save flow

These commands may read local filesystem state, but must not directly mutate canonical data storage.

## Mutation Model

This is the most important rule.

### Reads

Read commands may:

* query backend state
* read local workspace files
* read canonical files from `/data`

### Mutations

Mutating commands that affect app state must go through backend-controlled operations.

Examples:

* create entry proposal
* update pending proposal
* create group proposal
* attach a canonical file to an entity or entry
* save a durable artifact

The CLI must not directly:

* update authoritative ledger tables
* write to `bill_helper.db`
* write into canonical user data storage
* bypass review and approval

## Backend Communication Model

The CLI should communicate with the backend through a narrow, stable interface.

Recommended initial approach:

* HTTP API or internal app API surface
* authenticated with the current principal or a scoped runtime token
* same service-layer semantics regardless of whether the CLI runs inside or outside the sandbox

This ensures:

* one business logic path
* one policy enforcement point
* one review-gated mutation path

## Authentication and Identity

The CLI should execute as a specific principal.

Requirements:

* respect the same user and admin boundaries as the app
* in sandbox mode, use scoped credentials for that user and run context
* avoid exposing broad privileged backend secrets inside the workspace container

The CLI should not assume elevated access just because it runs inside a trusted container.

## Output Contract

Structured output is mandatory.

Every command should support a machine-readable mode, such as:

* `--json`

Recommended output characteristics:

* stable keys
* compact but sufficient structure
* predictable error shape
* minimal incidental formatting in machine mode

Human-friendly text output is still useful, but structured output is required for agent use.

## Suggested Top-Level Shape

The exact command set can evolve, but the top-level interface should feel coherent.

A reasonable first shape:

* `billengine status ...`
* `billengine entries ...`
* `billengine accounts ...`
* `billengine groups ...`
* `billengine entities ...`
* `billengine tags ...`
* `billengine proposals ...`
* `billengine reviews ...`
* `billengine threads ...`
* `billengine attachments ...`
* `billengine workspace ...`

## Recommended Command Semantics

### Status

System and user-facing runtime information.

Examples:

* current principal
* backend reachability
* workspace mount visibility
* active thread or run context if relevant

### Entries

Read entries and create/update/delete proposals related to entries.

### Accounts

Inspect accounts and propose account-related changes.

### Groups

Inspect groups and propose group or membership changes.

### Entities and tags

Inspect and propose catalog changes.

### Proposals and reviews

Inspect pending proposals, update pending proposals, approve or reject when allowed.

### Threads

Inspect thread state and optionally create or switch thread context if needed.

### Attachments

Inspect canonical file records, link files to entries through backend flows, and save promoted artifacts.

### Workspace

Inspect local workspace state and local file paths in a safe, explicit way.

## Workspace Awareness

When running inside the sandbox, the CLI should be aware of:

* `/workspace` as writable local execution storage
* `/data` as read-only canonical user files

It should be able to accept local file paths as inputs for backend-backed operations, for example:

* promoting a generated artifact from `/workspace/output/...`
* linking a canonical file from `/data/uploads/...`

But file-path-based operations must still result in backend-managed canonical records.

## What the CLI must not do

* reimplement business logic already in services
* open or edit the authoritative SQLite DB directly
* write directly into canonical data storage
* become a shell replacement
* expose arbitrary unrestricted command execution
* bypass proposal and review semantics

## Non-Goals

* Finalizing every command or flag up front
* Supporting every edge-case workflow in the first version
* Replacing the web UI
* Replacing the agent workspace terminal
* Granting unrestricted host or container access
* Making the CLI a second persistence layer

## Deliverables

* a coherent `billengine` CLI skeleton
* a clear split between app commands and workspace-aware commands
* shared service-layer integration for all app operations
* structured output mode suitable for agent consumption
* sandbox-compatible runtime behavior
* basic human-facing documentation
* basic agent-facing usage contract

## Implementation Guidance

## 1. Keep business logic in services

The CLI should call existing backend service functions or backend API surfaces. It should not duplicate domain rules.

## 2. Add a thin command layer

Implement the CLI as argument parsing plus request translation plus response rendering.

## 3. Make machine output first-class

Do not bolt on JSON later. Design for structured output from the beginning.

## 4. Explicitly separate read vs mutate operations

Read operations may be immediate. Mutations should map cleanly to proposal creation or other review-aware flows.

## 5. Keep workspace operations narrow

Do not let `workspace` commands drift into unrestricted shell behavior. The workspace terminal already handles general execution.

## Suggested Rollout

### Phase 1

* status
* entries list and proposal creation
* proposals list/update
* threads/status basics
* structured output

### Phase 2

* accounts
* groups
* entities
* tags
* attachments
* review actions where allowed

### Phase 3

* workspace-aware artifact promotion
* richer thread and review workflows
* more polished human ergonomics

## Success Criteria

* humans can perform common local workflows through the CLI
* the agent can use the CLI as a unified app interface
* all canonical mutations still respect proposal/review flow
* the CLI works both inside and outside the sandbox
* the CLI never needs direct database writes
* the interface is stable enough to grow without fragmentation

## Final Design Rule

`billengine` should be the canonical command interface for Bill Helper operations, but it must remain a thin client over backend authority, not a new home for business logic or canonical state.

