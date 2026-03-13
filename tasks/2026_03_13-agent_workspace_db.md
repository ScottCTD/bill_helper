# Agent Workspace DB Extension - Optional SQLite Context Layer

## Status
- Proposed
- Later phase, not part of Agent Workspace V1

## Priority
- Medium
- Only start after there is clear demand

## Depends on
- Agent Workspace V1

## Summary

Add an optional SQLite database inside each user's sandbox workspace to act as a structured
agent-side context layer.

This database is not meant to replace the filesystem and should not initially become the
authoritative source of product state. Its purpose is to make agent retrieval and reasoning
easier when file-based context becomes too awkward or too slow.

The database should help the agent answer questions like:

- what have we discussed about a topic before
- what files are related to a thread or workflow
- what user preferences or memories are relevant
- which artifacts were generated from which source files
- what entities are connected to what conversations or documents

In other words, this is a better local context engine for the agent, while the filesystem
remains the durable execution substrate.

## Why

The filesystem is excellent for:

- transparency
- raw file access
- scripts and outputs
- reproducibility
- user inspectability

But the filesystem is weak at:

- structured lookup
- relationship traversal
- metadata joins
- deduped indexing
- fast search across many threads and artifacts

Once the workspace grows, a structured local database becomes useful.

## Non-Goals

- Not part of the first workspace implementation
- Not a replacement for the app database
- Not a way to bypass review-gated domain writes
- Not a second ledger database
- Not a distributed sync system in the first version

## Key Positioning

### Filesystem remains primary for execution
The agent still reads and writes real files in `/workspace`.

### SQLite adds structured context
The database stores metadata, relationships, derived indexes, and agent-friendly lookup
structures.

### The app remains authoritative
The product backend remains the source of truth for canonical product data. The workspace DB
starts as a derived or mirrored context layer.

## Recommended Scope for the First DB Version

The first DB version should store only agent-context data, not canonical finance-domain state.

### Good candidates
- mirrored thread metadata
- mirrored message metadata
- file catalog and file hashes
- attachment catalog and relationships
- extracted text chunks and embeddings metadata if needed later
- user memories and preferences mirrored for agent use
- artifact provenance
- lightweight tags, links, and relationships

### Avoid initially
- authoritative entries table
- authoritative proposals table
- authoritative approval state
- any write path that can drift from backend truth

## DB File Location

```text
/workspace/system/context.db
````

Optional migrations can live in:

```text
/workspace/system/db_migrations/
```

## Design Principles

### 1. Derived before authoritative

Prefer data that can be rebuilt from app state and workspace files.

### 2. Rebuildable

If the DB is lost or corrupted, the system should be able to recreate it from mirrored files
and backend sync.

### 3. Agent-friendly schema

Optimize for common agent queries, not for strict normalization purity.

### 4. File linkage first

Every structured record should be able to point back to underlying files where possible.

## Proposed Initial Schema Areas

### Threads

Stores thread-level metadata.

Example fields:

* thread_id
* title
* created_at
* updated_at
* status

### Messages

Stores message-level metadata.

Example fields:

* message_id
* thread_id
* role
* timestamp
* content_text
* content_summary
* jsonl_offset or file pointer
* run_id

### Files

Catalog of files in the workspace.

Example fields:

* file_id
* path
* file_name
* sha256
* mime_type
* size_bytes
* created_at
* updated_at
* source_type
* source_thread_id

### Attachments

Catalog of attachment-like artifacts.

Example fields:

* attachment_id
* file_id
* attachment_kind
* display_name
* origin_type
* origin_ref

### Memories

Mirrored user memory items for agent retrieval.

Example fields:

* memory_id
* created_at
* text
* category
* source

### Preferences

Mirrored stable user preferences.

Example fields:

* preference_key
* preference_value
* source
* updated_at

### Relationships

Generic edges between entities.

Example fields:

* relation_id
* from_type
* from_id
* relation_type
* to_type
* to_id
* metadata_json

### Artifacts

Generated outputs and their provenance.

Example fields:

* artifact_id
* file_id
* artifact_type
* generated_by
* source_thread_id
* source_message_id
* parent_artifact_id

## Example Use Cases

### Use case 1: Retrieve prior discussions

The agent can query for threads and messages related to a topic much faster than grepping
every JSONL file.

### Use case 2: Find related artifacts

The agent can discover all outputs produced from a given upload or conversation.

### Use case 3: Stable user preference lookup

The agent can retrieve preferences or memories without scanning many files.

### Use case 4: Attachment relationship resolution

The agent can identify all records or conversations linked to a document.

## Sync Strategy

The initial DB should be populated by backend-driven sync and workspace indexing.

### Data sources

* app thread/message events
* mirrored workspace files
* upload events
* attachment metadata
* agent memory updates if mirrored into workspace

### Sync style

* append or upsert on new events
* periodic reindex is acceptable
* full rebuild should be possible

### Important rule

If app state and workspace DB disagree, app state wins.

## Query Surfaces

There are two future options:

### Option A: Agent uses terminal plus sqlite CLI or Python

The agent queries `context.db` through normal terminal commands or Python scripts.

This is the simplest first step because it needs no new agent API.

### Option B: Add dedicated DB query tools later

The backend can expose narrow tools for common queries if terminal-only access proves clumsy.

Recommendation: start with Option A.

## Relationship to Filesystem

The DB should complement the filesystem, not replace it.

### Filesystem stays best for

* raw documents
* scripts
* outputs
* user browsing
* inspectability
* reproducibility

### DB becomes best for

* search
* joins
* metadata lookup
* relationships
* indexing
* provenance

## Security and Safety

* the DB lives inside the user's isolated workspace
* no cross-user access
* no secrets beyond what the user already granted to the workspace
* DB corruption should not break canonical app state
* rebuildability is required

## Implementation Approach

### Phase 1: optional index only

* create `/workspace/system/context.db`
* define schema for threads, messages, files, attachments, memories, preferences, relationships
* write sync/indexer logic
* allow agent to inspect it through terminal

### Phase 2: richer derived context

* add text extraction indexes
* add lightweight semantic retrieval metadata if needed
* add artifact provenance and relationship graph support

### Phase 3: evaluate broader role

Only after real use proves it valuable, consider whether some additional app context should
also be mirrored in more structured form.

Do not jump to making the workspace DB authoritative unless there is a very strong reason and
a clear sync model.

## Acceptance Criteria

* a SQLite DB exists in the workspace and is created automatically when enabled
* thread and message metadata can be mirrored into it
* workspace files can be indexed into it
* memories and preferences can be mirrored into it
* the agent can query it from the terminal
* the system can rebuild it if deleted

## Recommendation

Keep this as a deliberate extension, not part of the first workspace milestone.

Build the workspace first. Only add `context.db` when one of these becomes painful:

* searching prior conversations through files
* tracking relationships across many artifacts
* retrieving user memories and preferences efficiently
* indexing larger document collections for agent use