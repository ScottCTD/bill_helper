# Agent Workspace: Docker-Based Sandboxed Environment

## Philosophy: Everything Is a File

The agent operates in a per-user Docker container that serves as its workspace. All state the agent works with — conversation history, uploaded documents, generated scripts, analysis outputs — lives as files on disk inside the workspace. The agent reads and writes files, runs code, and inspects results through a real filesystem and terminal, not through abstract API calls.

This makes the agent's work transparent, auditable, and resumable. The user can browse the workspace like a folder. The agent can reference past conversations and outputs across sessions because they're just files.

## Architecture

### Container Types

| Type | Purpose | Lifecycle | Count |
|------|---------|-----------|-------|
| **App containers** | FastAPI backend, frontend, Postgres | Always running (Compose) | Fixed (3-4) |
| **Sandbox containers** | Per-user workspace with filesystem + Python + tools | On-demand, idle-timeout | 0 to N |

App containers are managed by Docker Compose. Sandbox containers are spawned dynamically by the backend via `docker-py`.

### Sandbox Container Spec

Each sandbox container provides:

- A persistent workspace directory mounted from host (`/workspaces/{user_id}/` → `/workspace` inside container)
- Python interpreter (with common data/finance libraries pre-installed)
- Basic shell utilities (cat, grep, head, tail, wc, jq, etc.)
- No network access (`network_mode: none`) for security
- Resource limits: ~256MB RAM, 0.5 CPU
- Idle timeout: killed after ~15 min inactivity, workspace volume persists

### Workspace Directory Structure

```
/workspace/
├── conversations/          # conversation history as files
│   ├── {thread_id}/
│   │   ├── metadata.json   # thread title, created_at, updated_at
│   │   └── messages.jsonl   # each line is a message (role, content, tool_calls, timestamp)
│   └── ...
├── uploads/                # user-uploaded files (images, CSVs, bank statements)
│   └── ...
├── scripts/                # agent-written scripts
│   └── ...
├── output/                 # agent-generated outputs (reports, charts, exports)
│   └── ...
└── scratch/                # temporary working area, agent can use freely
    └── ...
```

All conversation history is written to `conversations/` as the thread progresses. The agent can read any past conversation to recall context across sessions.

## New Agent Tools

### 1. `terminal` — Run Shell Commands

Execute arbitrary shell commands inside the sandbox container.

- **Input**: `command` (string), optional `timeout` (int, seconds, default 30)
- **Output**: `stdout`, `stderr`, `exit_code`
- The agent is free to install packages (`pip install`, `apt-get`), run scripts, pipe commands — anything a terminal can do.
- Long-running commands are killed after the timeout.

Example uses:
- `python analyze.py` — run a script the agent wrote
- `pip install pandas && python -c "import pandas; print(pandas.__version__)"` — install and verify
- `ls -la /workspace/uploads/` — inspect uploaded files
- `head -50 /workspace/uploads/statement.csv` — preview data

### 2. `file_write` — Write/Create Files

Write content to a file in the workspace.

- **Input**: `path` (string, relative to `/workspace`), `content` (string)
- **Output**: confirmation with bytes written
- Creates parent directories as needed.
- Overwrites existing file if present.

### 3. `file_read` — Read Files

Read content from a file in the workspace.

- **Input**: `path` (string, relative to `/workspace`), optional `offset` (int), optional `limit` (int, lines)
- **Output**: file content (string), total line count
- Supports pagination for large files.

### 4. `file_edit` — Surgical File Edits

Replace a specific string occurrence in a file (find-and-replace).

- **Input**: `path`, `old_str`, `new_str`
- **Output**: confirmation or error if `old_str` not found / not unique
- For precise modifications without rewriting entire files.

### 5. `list_files` — List Directory Contents

List files and directories in the workspace.

- **Input**: `path` (string, relative to `/workspace`, default `/workspace`), optional `recursive` (bool)
- **Output**: list of file/directory entries with names, sizes, modified times

## Conversation History as Files

When a new agent thread is created, the backend:

1. Ensures the sandbox container is running (or starts it).
2. Creates `/workspace/conversations/{thread_id}/metadata.json`.
3. As messages are exchanged, appends each message as a JSONL line to `messages.jsonl`.

The agent's system prompt tells it that past conversations live in `/workspace/conversations/`. It can use `terminal` or `file_read` to look up past threads — e.g., "What did we discuss about the VISA statement?" triggers the agent to grep through conversation files.

This means:
- Conversation memory is unlimited (not constrained by context window).
- The agent can self-serve context from prior sessions.
- The user can inspect/delete conversation files directly if needed.

## Security Constraints

- `network_mode: none` — sandbox has no internet access.
- Resource limits enforced (memory, CPU).
- Workspace is scoped to one user — no cross-user access.
- The sandbox cannot reach the host database or backend API directly.
- The backend communicates with the sandbox only via `docker exec` (command execution) and volume mounts (file I/O).

## Implementation Approach

1. **Sandbox image**: Create a `Dockerfile.sandbox` with Python 3.12, common libraries (pandas, openpyxl, matplotlib, etc.), and basic shell tools.
2. **Sandbox manager**: Backend service that starts/stops/reuses containers per user via `docker-py`. Tracks container state in the database.
3. **Tool handlers**: Implement the 5 new tools as `AgentToolDefinition` entries. Each handler calls `docker exec` on the user's sandbox container.
4. **Conversation sync**: After each agent message exchange, the backend appends to the conversation JSONL file in the workspace volume.
5. **Docker Compose update**: Add app-level services (backend, frontend, db) to `docker-compose.yml`. Sandbox containers remain dynamically managed.

## Dependencies

- `docker` Python package (docker-py) for container management
- Docker Engine on the host
- A `Dockerfile.sandbox` for the sandbox image
