# Agent Workspace: Docker-Based Sandboxed Environment

## Philosophy: Everything Is a File

The agent operates in a per-user Docker container that serves as its workspace. All state the agent works with — conversation history, uploaded documents, generated scripts, analysis outputs — lives as files on disk inside the workspace. The agent reads and writes files, runs code, and inspects results through a real filesystem and terminal, not through abstract API calls.

This makes the agent's work transparent, auditable, and resumable. The user can browse the workspace like a folder. The agent can reference past conversations and outputs across sessions because they're just files.

## Architecture

### Container Types

| Type | Purpose | Lifecycle | Count |
|------|---------|-----------|-------|
| **App container** | The full application (FastAPI backend serving API + static frontend + Postgres) | Always running (Compose) | 1 |
| **Sandbox containers** | Per-user workspace with filesystem + Python + tools + internet | On-demand, idle-timeout | 0 to N |

The app container is managed by Docker Compose. Sandbox containers are spawned dynamically by the backend via `docker-py`.

### Sandbox Container Spec

Each sandbox container provides:

- A persistent workspace directory mounted from host (`/workspaces/{user_id}/` → `/workspace` inside container)
- Python interpreter (with common data/finance libraries pre-installed)
- Basic shell utilities (cat, grep, head, tail, wc, jq, etc.)
- Full internet access — the agent can install any packages it needs
- Resource limits: ~256MB RAM, 0.5 CPU
- Idle timeout: killed after ~15 min inactivity, workspace volume persists

### Workspace Directory Structure

```
/workspace/
├── conversations/          # conversation history as files
│   ├── {thread_id}/
│   │   ├── metadata.json   # thread title, created_at, updated_at
│   │   ├── messages.jsonl   # each line is a message (role, content, tool_calls, timestamp)
│   │   └── uploads/         # files uploaded within this thread
│   │       └── ...
│   └── ...
├── uploads/                # user-uploaded files not tied to a thread (general workspace files)
│   └── ...
├── scripts/                # agent-written scripts
│   └── ...
├── output/                 # agent-generated outputs (reports, charts, exports)
│   └── ...
└── scratch/                # temporary working area, agent can use freely
    └── ...
```

Each thread has its own `uploads/` subdirectory. When a user uploads a file in a conversation, the backend copies it into `/workspace/conversations/{thread_id}/uploads/`. The agent sees it as a local file and can reference it via the terminal. Files uploaded outside of a specific thread go to the top-level `uploads/` directory.

## New Agent Tool

### `terminal` — Run Shell Commands

A single general-purpose tool. The agent does everything through the terminal: read files, write files, edit files, run Python, install packages, list directories — just like a developer in a shell.

- **Input**: `command` (string), optional `timeout` (int, seconds, default 30)
- **Output**: `stdout`, `stderr`, `exit_code`
- Long-running commands are killed after the timeout.

Example uses:
- `python analyze.py` — run a script the agent wrote
- `pip install pandas && python -c "import pandas; print(pandas.__version__)"` — install and use
- `cat /workspace/conversations/abc123/uploads/statement.csv | head -50` — preview an uploaded file
- `echo '...' > /workspace/scripts/analyze.py` — write a file
- `sed -i 's/old/new/' /workspace/scripts/analyze.py` — edit a file
- `ls -la /workspace/uploads/` — list files
- `apt-get install -y jq && cat data.json | jq '.expenses[]'` — install tools as needed

The agent is free to install anything and do anything inside the container.

## Command Approval & YOLO Mode

By default, every `terminal` command the agent wants to run is shown to the user for approval before execution. This is the safe default — the user sees exactly what the agent intends to do and can approve or reject it.

**YOLO mode**: An opt-in setting (per user or per thread) that skips approval and lets the agent execute commands freely without confirmation. Useful for power users who trust the agent and want faster iteration.

- YOLO mode is off by default.
- The user can toggle it from the UI (thread-level or account-level setting).
- Even in YOLO mode, the full command history is logged and visible in the conversation.

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

- Resource limits enforced (memory, CPU).
- Workspace is scoped to one user — no cross-user access.
- The sandbox cannot reach the host database or backend API directly.
- The backend communicates with the sandbox only via `docker exec` (command execution) and volume mounts (file I/O).
- Command approval by default; YOLO mode opt-in.

## Implementation Approach

1. **Sandbox image**: Create a `Dockerfile.sandbox` with Python 3.12, common libraries (pandas, openpyxl, matplotlib, etc.), and basic shell tools.
2. **Sandbox manager**: Backend service that starts/stops/reuses containers per user via `docker-py`. Tracks container state in the database.
3. **Tool handler**: Implement the `terminal` tool as an `AgentToolDefinition`. The handler calls `docker exec` on the user's sandbox container. Commands require user approval unless YOLO mode is enabled.
4. **File upload flow**: When a user uploads a file in a thread, the backend writes it to the workspace volume at `/workspaces/{user_id}/conversations/{thread_id}/uploads/`.
5. **Conversation sync**: After each agent message exchange, the backend appends to the conversation JSONL file in the workspace volume.
6. **Docker Compose update**: Add the app service (backend + frontend + db) to `docker-compose.yml`. Sandbox containers remain dynamically managed.

## Dependencies

- `docker` Python package (docker-py) for container management
- Docker Engine on the host
- A `Dockerfile.sandbox` for the sandbox image
