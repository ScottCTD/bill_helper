# ADR 0007: Canonical User Files and Per-User Agent Workspace IDE

- Status: accepted
- Date: 2026-03-14
- Deciders: scottcui

## Context

Agent uploads were previously stored as thread-scoped files under `{data_dir}/agent_uploads/<message_id>/...`, and `agent_message_attachments` owned the attachment metadata directly. That model had three problems:

1. Durable user-visible files did not have one canonical registry or ownership seam.
2. Deleting a thread deleted uploaded payload files even though later features need stable per-user files beyond one conversation.
3. There was no deterministic per-user sandbox/workspace contract to prepare for future execution tooling.

The V1 workspace task also needed a concrete provisioning model that stays dependency-light and works with the existing local-first prototype.

## Decision

Adopt a canonical per-user file layer plus eager per-user workspace provisioning.

### Canonical user files

- Store durable user-visible uploads under `{data_dir}/user_files/{user_id}/uploads`.
- Add `user_files` as the source-of-truth registry for those files.
- Rewire `agent_message_attachments` to reference `user_files.id` instead of storing attachment file metadata directly.
- Keep the attachment API surface stable by deriving `mime_type`, `original_filename`, and absolute `file_path` from the linked canonical file row at serialization time.
- Delete thread-scoped database rows on thread deletion, but do not delete canonical uploaded payload files from disk.

### Workspace provisioning

- Provision one deterministic workspace definition per user:
  - container: `bill-helper-sandbox-{user_id}`
  - volume: `bill-helper-workspace-{user_id}`
  - read-only bind mount: `{data_dir}/user_files/{user_id}/uploads` -> `/workspace/uploads`
  - writable volume mount: `{workspace volume}` -> `/workspace`
- Create host directories, the named volume, and the named container definition eagerly during admin bootstrap and user creation.
- Run `code-server` as the container's main process, publish its IDE port to localhost only, and persist IDE settings/extensions inside the same named workspace volume.
- Structure the writable workspace volume so `/workspace` contains `scratch/` for user-created files, `uploads/` as the direct read-only bind mount, and persisted IDE state in a hidden internal directory.
- Force built-in VS Code AI features off in the persisted `code-server` user settings so the per-user workspace IDE does not expose agent mode or related chat UI.
- Keep the container stopped by default between uses, but authenticated browser sessions now best-effort auto-start it so the IDE is usually ready before the user opens `/workspace`.
- Reuse the existing bearer-backed app session model by minting one narrow `HttpOnly` cookie for `/api/v1/workspace/ide/` instead of creating a second IDE-specific auth system.

### Control plane and image policy

- Use a thin Docker CLI adapter instead of adding the Python Docker SDK.
- Require a prebuilt local image tag (`bill-helper-agent-workspace:latest` by default); the backend does not auto-build images.
- If the backend runs inside Docker, it still needs host-daemon access via `/var/run/docker.sock` or `DOCKER_HOST`.

## Consequences

### Positive

- Durable uploads now have one ownership model and one readable migration path for agent attachment bundles.
- Agent uploads survive thread deletion, so future file catalog and workspace flows can reuse the same canonical records.
- Per-user sandbox resources are deterministic, isolated by user, and now provide a first-class browser IDE without introducing a heavier SDK dependency.

### Negative

- User creation/bootstrap now depends on Docker image availability when workspace provisioning is enabled.
- The backend takes on explicit host-Docker operational requirements for workspace management.
- The workspace surface now depends on same-origin reverse proxying and websocket forwarding through the backend.

### Follow-up constraints

- Active agent runs still do not expose arbitrary code execution.
- No file catalog UI is introduced by this decision; the registry exists first so later UI and execution work can build on it.
- Built-in `code-server` app/port proxying stays disabled in v1; the IDE edits `/workspace/scratch` and reads `/workspace/uploads`.
