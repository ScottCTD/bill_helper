# Agent Workspace V1 - Per-User Sandbox Container and File/Data Mounts

## Status

- Proposed

## Priority

- High

## Scope

- Workspace scaffolding only
- Per-user sandbox container
- Host-side canonical file storage layout
- Per-user writable workspace volume
- Container image and mount design
- No CLI work in this task
- No email ingestion work in this task
- No agent-side context database in this task
- No conversation-history exposure to the agent in this task

## Summary

Introduce a per-user sandbox container that gives the agent a real execution environment with:

- a writable Docker volume mounted at `/workspace`
- a read-only host-backed data mount at `/data`
- Python 3.13
- common Python libraries
- common shell utilities

This task establishes the filesystem and container foundation only.

The backend remains the canonical authority for application state and metadata. Durable user-facing files are stored outside the execution container in host-managed local storage and mounted read-only into the sandbox. The sandbox has its own separate writable workspace volume for scratch files, scripts, temporary outputs, and non-canonical durable workspace files.

Conversation history is intentionally **not exposed to the agent** in this phase.

## Goals

- Provide a reusable per-user sandbox container for agent execution
- Separate canonical durable file storage from the execution container
- Give the agent a clean writable workspace via a Docker volume
- Mount canonical per-user files into the sandbox read-only
- Keep the initial design simple and local-file based
- Use a small, minimal image with Python 3.13 and a good terminal experience

## Non-Goals

- No CLI integration
- No email ingestion
- No conversation-history file exports to the agent
- No agent-side SQLite context layer
- No direct agent access to the canonical application database file
- No attempt to make the sandbox container the source of truth for app data

## Core Design Decision

The workspace design uses **two separate storage surfaces** inside the sandbox:

### `/workspace`

A writable Docker volume dedicated to agent execution.

This is where the agent writes:

- scratch files
- scripts
- temporary outputs
- workspace-only durable helper files

### `/data`

A read-only bind mount backed by host-side local storage.

This is where the agent reads canonical durable user files that the backend has registered and promoted.

This split is intentional:

- `/data` is canonical and backend-managed
- `/workspace` is writable and execution-oriented

The agent must never directly mutate canonical storage.

## Authority Boundary

### Canonical outside the sandbox

The backend and host-side data layer remain authoritative for:

- application database state
- file metadata and file relationships
- ownership and permissions
- which files are durable and frontend-visible
- file promotion and deletion semantics

### Writable inside the sandbox

The sandbox is authoritative only for its own local working files under `/workspace`.

Files created there are not canonical unless the backend later promotes them into canonical storage.

## Conversation History

Conversation history is **not exposed to the agent** in this phase.

That means:

- no conversation file mirrors under `/data`
- no mounted thread histories in the sandbox
- no workspace copies of historical conversations by default

Canonical conversation history remains in the backend database only.

This is an intentional simplification for V1.

## Host-Side Data Layout

The current top-level application data directory remains the base:

```text
~/.local/share/bill-helper/
├── agent_uploads
├── bill_helper.db
└── telegram
```

For this task, extend it to include a dedicated canonical per-user file area:

```text
~/.local/share/bill-helper/
├── bill_helper.db
├── agent_uploads
├── telegram
└── user_files/
    └── {user_id}/
        ├── uploads/
        └── artifacts/
```

### Rules

- Keep `bill_helper.db` at the top level
- Add `user_files/{user_id}/uploads/` for canonical user-uploaded files
- Add `user_files/{user_id}/artifacts/` for canonical durable generated artifacts
- Keep both `uploads/` and `artifacts/` flat for now
- Keep original file names. We might consider for normalize file names later.
- Do not add deeper nesting in this phase
- File relationships are tracked in the canonical database via stored file paths and metadata

## Host-Side Canonical File Semantics

### `user_files/{user_id}/uploads/`

Contains canonical uploaded files that the user or app has explicitly stored.

Examples:

- manual file uploads
- thread-attached uploaded files
- durable imported source documents

### `user_files/{user_id}/artifacts/`

Contains canonical durable generated files that should remain available to the frontend and future sessions.

Examples:

- saved plots
- exported reports
- generated images the user should be able to revisit

### Flat structure rule

For now, keep both directories flat to reduce early complexity.

This means:

- no thread-based nesting
- no date-based nesting
- no category subdirectories

The backend should generate collision-safe stored filenames.

## Canonical Database Responsibilities

The database should remain the canonical registry for durable files.

For each durable file in `user_files/{user_id}/uploads/` or `user_files/{user_id}/artifacts/`, the backend should know:

- file id
- user id
- stored path
- original file name
- display name if needed
- MIME type
- size
- hash if available
- created time
- source type
- related thread / entry / artifact metadata as needed later

The file payload lives on local disk. The database stores metadata and references.

## Sandbox Container Mount Design

Each per-user sandbox container should mount exactly two main paths:

### 1. Writable workspace volume

Mount a dedicated Docker volume to:

```text
/workspace
```

Properties:

- writable
- per-user
- persistent across container restarts
- intended for agent-created working state

Recommended naming pattern:

```text
bill-helper-workspace-{user_id}
```

### 2. Read-only canonical data mount

Bind mount the user's canonical file directory to:

```text
/data
```

Source on host:

```text
~/.local/share/bill-helper/user_files/{user_id}/
```

Mount properties:

- read-only
- per-user scoped
- backend-managed
- visible to the agent for reading only

Inside the container, `/data` will therefore look like:

```text
/data
├── uploads/
└── artifacts/
```

## Why `/data` should be read-only

This is the key safety boundary.

The agent may inspect canonical files, but it must not directly modify or delete them. Any durable file creation, promotion, replacement, or deletion should happen through backend-controlled flows.

Example:

- the agent writes a plot to `/workspace/output/plot.png`
- if the plot should become durable and frontend-visible, the backend promotes it into canonical storage under `/data/artifacts/` on the host and records it in the database
- the agent never writes directly into `/data/artifacts/`

## `/data` Structure Inside the Sandbox

The sandbox sees only the user's own canonical files:

```text
/data
├── uploads/
└── artifacts/
```

### `/data/uploads`

Read-only canonical uploaded files.

### `/data/artifacts`

Read-only canonical durable generated artifacts.

### Not included in `/data` for this phase

Do not include:

- conversation history
- backend database file
- other users' files
- internal backend state
- email stores
- attachment registries beyond the canonical promoted files themselves

## `/workspace` Structure Inside the Sandbox

Keep `/workspace` simple and flat in V1.

Recommended initial structure:

```text
/workspace
├── *
```

## Why `/workspace` should stay simple

The first version should optimize for clarity, not elaborate organization.

A flat and predictable layout is better for:

- agent prompting
- backend implementation
- operational debugging
- future migration if structure changes later

## Container Image Requirements

Use a small and minimal Python image as the base, with Python 3.13.

Recommended direction:

- minimal Debian-based Python image
- avoid large full-fat data-science images
- install only commonly useful packages and shell tools

## Required Runtime

- Python 3.13
- Bash shell
- UTF-8 environment
- non-root runtime user if practical

## Recommended Preinstalled Python Packages

Install common packages that materially improve agent usefulness without making the image too heavy.

Minimum recommended set:

- `numpy`
- `matplotlib`
- `pandas`
- `openpyxl`
- `python-dateutil`
- `requests`
- `pydantic`

## Recommended CLI Utilities

Install a compact but useful set of terminal tools:

- `bash`
- `coreutils`
- `findutils`
- `grep`
- `sed`
- `gawk`
- `jq`
- `less`
- `tree`
- `file`
- `curl`
- `unzip`
- `zip`
- `procps`

The goal is a better terminal experience for the agent without turning the image into a full developer workstation.

## Backend Responsibilities

The backend must manage all sandbox lifecycle and mount behavior.

### Provisioning

For each user:

- ensure `~/.local/share/bill-helper/user_files/{user_id}/uploads/` exists
- ensure `~/.local/share/bill-helper/user_files/{user_id}/artifacts/` exists
- ensure a Docker volume exists for that user's workspace

### Container creation

When starting a sandbox for a user:

- mount the user's Docker volume at `/workspace`
- bind mount the user's canonical file directory at `/data` as read-only

### File promotion

When a file created in `/workspace/output/` should become durable:

- copy or move it into host canonical storage
- register it in the canonical database
- make it visible in frontend through the normal backend file model

### File upload

When the user uploads a file:

- store it in canonical host storage under `user_files/{user_id}/uploads/`
- register its metadata in the database
- it becomes visible to the sandbox automatically through `/data/uploads/`

## Workspace Lifecycle

### Persistence

The `/workspace` Docker volume must persist across container restarts.

### Ephemeral runtime

The container itself may be stopped after inactivity and later restarted.

### Reusability

When restarted, the same user should regain:

- the same `/workspace` contents
- the same `/data` view

## Security Boundaries

### The sandbox must not see:

- `bill_helper.db`
- other users' canonical files
- internal backend credentials beyond what is strictly needed for the sandbox runtime
- any writable canonical data mount

### The sandbox may see:

- only that user's promoted canonical files under `/data`
- its own writable `/workspace`

### The sandbox must not be able to:

- write to `/data`
- mutate canonical files directly
- access other user containers or volumes

## Implementation Notes

### Canonical data mount implementation

Use a bind mount from the host filesystem:

- host: `~/.local/share/bill-helper/user_files/{user_id}/`
- container: `/data`
- mode: read-only

This is appropriate for the current local-file storage model.

### Workspace mount implementation

Use a dedicated Docker volume per user:

- volume name pattern: `bill-helper-workspace-{user_id}`
- container mount point: `/workspace`

This keeps workspace durability separate from canonical data storage.

### Separation of concerns

Do not mix canonical durable files into the workspace volume by default.
Do not put scratch or agent scripts into the canonical data directory.

## Minimal Example Layout

### Host

```text
~/.local/share/bill-helper/
├── bill_helper.db
├── agent_uploads
├── telegram
└── user_files/
    └── user_123/
        ├── uploads/
        │   ├── 20260313_abcd_statement.pdf
        │   └── 20260313_efgh_receipt.png
        └── artifacts/
            └── 20260313_plot_xyz.png
```

### Inside sandbox

```text
/data
├── uploads/
│   ├── 20260313_abcd_statement.pdf
│   └── 20260313_efgh_receipt.png
└── artifacts/
    └── 20260313_plot_xyz.png
```

```text
/workspace
├── *
```

## Acceptance Criteria

### Storage and mount structure

- a per-user canonical host directory exists at `~/.local/share/bill-helper/user_files/{user_id}/`
- it contains `uploads/` and `artifacts/`
- the sandbox mounts that directory to `/data` as read-only
- the sandbox mounts a per-user Docker volume to `/workspace` as writable

### Workspace behavior

- files in canonical storage are visible inside `/data`
- the agent can read files from `/data`
- the agent can create and modify files under `/workspace`
- files under `/workspace` persist across container restarts

### Safety

- the sandbox cannot write to `/data`
- the sandbox cannot access `bill_helper.db`
- the sandbox cannot access other users' files

### Scope control

- conversation history is not exposed to the agent
- no email-specific storage is introduced
- no CLI-specific integration is introduced
- no agent-side database is introduced

## Recommended Implementation Order

1. add host-side `user_files/{user_id}/uploads/` and `user_files/{user_id}/artifacts/`
2. add per-user Docker workspace volumes
3. create minimal sandbox image with Python 3.13 and common utilities
4. implement sandbox container startup with both mounts
5. verify read-only behavior for `/data`
6. verify persistent writable behavior for `/workspace`
7. add backend logic for promoting files from workspace to canonical storage later

## Final Design Rule

For this phase, the workspace system should follow one simple rule:

**Canonical durable user-visible files live outside the execution container and are mounted read-only at `/data`; agent working state lives in a separate writable Docker volume at `/workspace`.**