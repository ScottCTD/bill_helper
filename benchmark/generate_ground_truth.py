"""Generate a draft ground_truth.json by running a capable model on a case.

Usage:
    uv run python -m benchmark.generate_ground_truth --case case_001 --model "openrouter/anthropic/claude-sonnet-4"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from benchmark.io_utils import atomic_write_json
from benchmark.runner import CASES_DIR, run_benchmark, RESULTS_DIR
from benchmark.schemas import (
    GroundTruth,
    GroundTruthEntity,
    GroundTruthEntry,
    GroundTruthTag,
)


@dataclass(slots=True)
class GroundTruthGenerationResult:
    case_id: str
    model_name: str
    output_path: Path
    run_id: str
    tag_count: int
    entity_count: int
    entry_count: int
    wrote_draft_path: bool


def generate_ground_truth(case_id: str, model_name: str) -> GroundTruthGenerationResult:
    case_dir = CASES_DIR / case_id
    if not (case_dir / "input.json").exists():
        raise FileNotFoundError(f"case '{case_id}' not found")

    gt_path = case_dir / "ground_truth.json"
    wrote_draft_path = False
    if gt_path.exists():
        gt_path = case_dir / "ground_truth_draft.json"
        wrote_draft_path = True

    run_id = run_benchmark(model_name, [case_id], workers=1)

    results_path = RESULTS_DIR / run_id / "cases" / case_id / "results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"no results produced at {results_path}")

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
    atomic_write_json(gt_path, gt.model_dump())
    return GroundTruthGenerationResult(
        case_id=case_id,
        model_name=model_name,
        output_path=gt_path,
        run_id=run_id,
        tag_count=len(gt_tags),
        entity_count=len(gt_entities),
        entry_count=len(gt_entries),
        wrote_draft_path=wrote_draft_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate draft ground truth from a capable model run."
    )
    parser.add_argument("--case", required=True, help="Case ID to generate ground truth for")
    parser.add_argument("--model", required=True, help="LiteLLM model to use for generation")
    args = parser.parse_args()

    try:
        print(
            f"Running model '{args.model}' on case '{args.case}' to generate ground truth draft..."
        )
        print()
        result = generate_ground_truth(args.case, args.model)
        if result.wrote_draft_path:
            print(
                f"WARNING: {CASES_DIR / result.case_id / 'ground_truth.json'} already exists. "
                f"Output was written as {result.output_path.name}"
            )
        print(f"Draft ground truth written to: {result.output_path}")
        print(
            f"  {result.tag_count} tags, {result.entity_count} entities, "
            f"{result.entry_count} entries extracted"
        )
        print()
        print("Next steps:")
        print(f"  1. Review and edit {result.output_path}")
        print("  2. Rename to ground_truth.json if it was saved as a draft")
        print(
            f"  3. Check the trace at: "
            f"{RESULTS_DIR / result.run_id / 'cases' / result.case_id / 'trace.json'}"
        )
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
