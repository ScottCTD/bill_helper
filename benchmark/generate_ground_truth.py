"""Generate a draft ground_truth.json by running a capable model on a case.

Usage:
    uv run python -m benchmark.generate_ground_truth --case case_001 --model "openrouter/anthropic/claude-sonnet-4"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmark.runner import CASES_DIR, run_benchmark, RESULTS_DIR
from benchmark.schemas import (
    GroundTruth,
    GroundTruthEntity,
    GroundTruthEntry,
    GroundTruthTag,
)


def generate_ground_truth(case_id: str, model_name: str) -> None:
    case_dir = CASES_DIR / case_id
    if not (case_dir / "input.json").exists():
        print(f"Error: case '{case_id}' not found", file=sys.stderr)
        sys.exit(1)

    gt_path = case_dir / "ground_truth.json"
    if gt_path.exists():
        print(f"WARNING: {gt_path} already exists. Output will be written as ground_truth_draft.json")
        gt_path = case_dir / "ground_truth_draft.json"

    print(f"Running model '{model_name}' on case '{case_id}' to generate ground truth draft...")
    print()

    run_id = run_benchmark(model_name, [case_id], workers=1)

    results_path = RESULTS_DIR / run_id / "cases" / case_id / "results.json"
    if not results_path.exists():
        print(f"Error: no results produced at {results_path}", file=sys.stderr)
        sys.exit(1)

    results = json.loads(results_path.read_text())

    gt_tags = [
        GroundTruthTag(name=t.get("name", ""), type=t.get("type"))
        for t in results.get("tags", [])
    ]
    gt_entities = [
        GroundTruthEntity(name=e.get("name", ""), category=e.get("category"))
        for e in results.get("entities", [])
    ]
    gt_entries = [
        GroundTruthEntry(
            kind=entry.get("kind", "EXPENSE"),
            date=entry.get("date", ""),
            name=entry.get("name", ""),
            amount_minor=entry.get("amount_minor", 0),
            currency_code=entry.get("currency_code"),
            from_entity=entry.get("from_entity", ""),
            to_entity=entry.get("to_entity", ""),
            tags=entry.get("tags", []),
        )
        for entry in results.get("entries", [])
    ]

    gt = GroundTruth(tags=gt_tags, entities=gt_entities, entries=gt_entries)
    gt_path.write_text(json.dumps(gt.model_dump(), indent=2) + "\n")

    print()
    print(f"Draft ground truth written to: {gt_path}")
    print(f"  {len(gt_tags)} tags, {len(gt_entities)} entities, {len(gt_entries)} entries extracted")
    print()
    print("Next steps:")
    print(f"  1. Review and edit {gt_path}")
    print(f"  2. Rename to ground_truth.json if it was saved as a draft")
    print(f"  3. Check the trace at: {RESULTS_DIR / run_id / 'cases' / case_id / 'trace.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate draft ground truth from a capable model run."
    )
    parser.add_argument("--case", required=True, help="Case ID to generate ground truth for")
    parser.add_argument("--model", required=True, help="LiteLLM model to use for generation")
    args = parser.parse_args()

    generate_ground_truth(args.case, args.model)


if __name__ == "__main__":
    main()
