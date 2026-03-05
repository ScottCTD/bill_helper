# Agent Import Benchmark

Benchmark framework for evaluating LLMs on their ability to parse bank statements into structured tool calls (`propose_create_tag`, `propose_create_entity`, `propose_create_entry`).

## Overview

The benchmark measures how accurately a model can extract financial data from unstructured input (PDFs, images, text) by comparing the model's tool calls against human-verified ground truth. With an empty DB snapshot, the agent must propose tags and entities before referencing them in entries.

## Quick Start

### 1. Create a DB snapshot

```bash
# Default snapshot with accounts, default tags, entity categories, and user memory
uv run python -m benchmark.create_empty_snapshot

# Or create a snapshot from an existing DB
uv run python -m benchmark.snapshot create --name custom
```

### 2. Set up a benchmark case

Create a case directory under `benchmark/fixtures/cases/`:

```
benchmark/fixtures/cases/my_case/
  input.json
  attachments/
    statement.pdf
  ground_truth.json    # generated in step 3, then manually edited
```

`input.json`:
```json
{
  "text": "Please import these transactions from my credit card statement.",
  "attachment_paths": ["attachments/statement.pdf"],
  "snapshot": "default"
}
```

`ground_truth.json`:
```json
{
  "tags": [],
  "entities": [
    {"name": "Loblaws", "category": "merchant"},
    {"name": "Starbucks", "category": "merchant"}
  ],
  "entries": [
    {
      "kind": "EXPENSE",
      "date": "2026-01-05",
      "name": "Loblaws",
      "amount_minor": 4523,
      "currency_code": "CAD",
      "from_entity": "Scotiabank Credit",
      "to_entity": "Loblaws",
      "tags": ["grocery"]
    }
  ]
}
```

The `tags` array lists only tags the agent must **create** (via `propose_create_tag`). With the default snapshot, tags are pre-seeded so this is typically empty. The `entities` array lists entities the agent must create. Entry-level `tags` reference existing tag names.

### 3. Generate draft ground truth

```bash
uv run python -m benchmark.generate_ground_truth \
  --case my_case \
  --model "openrouter/anthropic/claude-sonnet-4"
```

Review and edit the generated `ground_truth.json` (or `ground_truth_draft.json` if one already existed).

### 4. Run the benchmark

```bash
# Single model, all cases
uv run python -m benchmark.runner --model "openrouter/anthropic/claude-sonnet-4" --all-cases

# Specific cases with parallel workers
uv run python -m benchmark.runner \
  --model "openrouter/google/gemini-2.5-pro" \
  --cases case_001 case_002 \
  --workers 4
```

### 5. Score results

```bash
# Score a single run
uv run python -m benchmark.scorer run 20260302T143000_anthropic--claude-sonnet-4

# Compare multiple runs
uv run python -m benchmark.scorer compare RUN_ID_1 RUN_ID_2 --save-report my_comparison
```

## Directory Structure

```
benchmark/
  fixtures/                    # gitignored -- private data
    snapshots/{name}/
      db.sqlite3               # SQLite DB copy
      metadata.json
    cases/{case_id}/
      input.json               # case input definition
      attachments/             # PDFs, images
      ground_truth.json        # human-verified expected tags, entities, entries
  results/                     # gitignored -- run outputs
    runs/{run_id}/
      run_meta.json            # run config and summary
      cases/{case_id}/
        results.json           # extracted propose_create_* tool calls
        trace.json             # full interaction trace
        score.json             # scoring output
  reports/                     # tracked in git -- public metrics only
    {name}.json                # aggregate comparison reports
  runner.py                    # run cases against a model
  scorer.py                    # score results and compare models
  generate_ground_truth.py     # generate draft ground truth
  snapshot.py                  # manage DB snapshots
  create_empty_snapshot.py     # create default snapshot with seeded data
  schemas.py                   # Pydantic schemas for case/result data
```

## Scoring

The scorer evaluates three dimensions:

### Tags & Entities (set-based)

Tags and entities are scored by name-based set matching: precision, recall, F1, plus category accuracy for matched items.

### Entries (ordered matching)

Entries are matched between predictions and ground truth using `(date, amount_minor)` as a composite key, with a fallback fuzzy matcher.

| Field | Method |
|-------|--------|
| `kind` | Exact match (0 or 1) |
| `amount_minor` | Exact match (0 or 1) |
| `date` | Exact match (0 or 1) |
| `name` | Normalized text similarity |
| `from_entity` | Normalized text similarity |
| `to_entity` | Normalized text similarity |
| `tags` | Jaccard similarity |

### Overall Score

Weighted composite: entries (60%), entities (25%), tags (15%). Entry score combines F1 with average field accuracy.

## Production Parity

The runner reuses production agent code through a stable benchmark-facing service contract:
- Benchmark contract: `backend/services/agent/benchmark_interface.py` (`run_benchmark_case`)
- Same tool schemas and execution (`backend/services/agent/tools.py`)
- Same message construction (`backend/services/agent/message_history.py`)
- Same system prompt (`backend/services/agent/prompts.py`)
- Model client via LiteLLM (`backend/services/agent/model_client.py`)
- Same run-step state machine via adapterized orchestrator (`backend/services/agent/run_orchestrator.py`)
- Same tool-call/usage helper semantics (`backend/services/agent/protocol_helpers.py`)

The only change is the model name, injected via `RuntimeSettings` override in the isolated temp DB.

## DB Isolation

- **Production DB is never touched during benchmark runs.** Each case copies its snapshot to a unique temp file.
- Runs are isolated from each other (separate temp DB per case).
- `snapshot.py restore` is the only command that writes to the production DB path, and it requires an explicit manual invocation.

## CLI Error Contract

- Benchmark scripts are module-native (`uv run python -m benchmark.<script>`) and do not mutate `sys.path` for local imports.
- Reusable helpers are side-effect-light functions that return typed results (`create_default_snapshot`, `generate_ground_truth`) so callers can reuse logic without process-control coupling.
- JSON benchmark artifacts (`metadata.json`, `results.json`, `trace.json`, `run_meta.json`, `score.json`, report outputs) are written atomically via temp-file + replace semantics to avoid partial files on interruption/crash.
- Worker functions (`run_benchmark`, `score_run`, `generate_ground_truth`, snapshot helpers) are exception-based.
- CLI wrappers convert failures to process exit codes only in `main()` (`raise SystemExit(main())`), keeping script failure behavior consistent across benchmark tools.
