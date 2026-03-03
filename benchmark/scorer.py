"""Score benchmark results against ground truth.

Usage:
    uv run python -m benchmark.scorer --run RUN_ID
    uv run python -m benchmark.scorer --compare RUN_ID_1 RUN_ID_2 [--save-report NAME]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "benchmark" / "results" / "runs"
CASES_DIR = REPO_ROOT / "benchmark" / "fixtures" / "cases"
REPORTS_DIR = REPO_ROOT / "benchmark" / "reports"


def _normalize_text(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(s.lower().split()).strip()


def _normalize_tags(tags: list[str] | None) -> set[str]:
    if not tags:
        return set()
    return {_normalize_text(t) for t in tags if t and t.strip()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _text_similarity(a: str | None, b: str | None) -> float:
    na, nb = _normalize_text(a), _normalize_text(b)
    if na == nb:
        return 1.0
    if not na or not nb:
        return 0.0
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if shorter in longer:
        return len(shorter) / len(longer)
    common = sum(1 for ca, cb in zip(shorter, longer) if ca == cb)
    return common / max(len(shorter), len(longer))


@dataclass
class FieldScores:
    kind: float = 0.0
    amount_minor: float = 0.0
    date: float = 0.0
    name: float = 0.0
    from_entity: float = 0.0
    to_entity: float = 0.0
    tags: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "kind": self.kind,
            "amount_minor": self.amount_minor,
            "date": self.date,
            "name": self.name,
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "tags": self.tags,
        }

    def average(self) -> float:
        vals = list(self.as_dict().values())
        return sum(vals) / len(vals) if vals else 0.0


@dataclass
class EntryMatch:
    gt_index: int
    pred_index: int
    scores: FieldScores


@dataclass
class SetScore:
    """Precision / recall / category accuracy for a set of named items (tags or entities)."""
    gt_count: int = 0
    pred_count: int = 0
    matched_count: int = 0
    precision: float = 0.0
    recall: float = 0.0
    category_accuracy: float = 0.0
    matched_names: list[str] = field(default_factory=list)
    missing_names: list[str] = field(default_factory=list)
    extra_names: list[str] = field(default_factory=list)

    def f1(self) -> float:
        if (self.precision + self.recall) == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gt_count": self.gt_count,
            "pred_count": self.pred_count,
            "matched_count": self.matched_count,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1(), 4),
            "category_accuracy": round(self.category_accuracy, 4),
            "missing_names": self.missing_names,
            "extra_names": self.extra_names,
        }


@dataclass
class CaseScore:
    case_id: str
    gt_count: int
    pred_count: int
    matched_count: int
    precision: float
    recall: float
    field_scores: FieldScores
    tag_score: SetScore = field(default_factory=SetScore)
    entity_score: SetScore = field(default_factory=SetScore)
    matches: list[EntryMatch] = field(default_factory=list)
    unmatched_gt: list[int] = field(default_factory=list)
    unmatched_pred: list[int] = field(default_factory=list)

    def overall_score(self) -> float:
        if self.matched_count == 0 and self.tag_score.gt_count == 0 and self.entity_score.gt_count == 0:
            return 0.0
        entry_f1 = (2 * self.precision * self.recall / (self.precision + self.recall)
                    if (self.precision + self.recall) > 0 else 0.0)
        entry_score = 0.5 * entry_f1 + 0.5 * self.field_scores.average() if self.matched_count > 0 else 0.0
        tag_f1 = self.tag_score.f1()
        entity_f1 = self.entity_score.f1()
        # Weighted: entries 60%, entities 25%, tags 15%
        return 0.60 * entry_score + 0.25 * entity_f1 + 0.15 * tag_f1


def score_named_set(
    gt_items: list[dict[str, Any]],
    pred_items: list[dict[str, Any]],
    *,
    classify_field: str = "category",
) -> SetScore:
    """Score a set of named items (tags or entities) by name matching + classification accuracy.

    classify_field: the dict key used for the secondary classification check
    (e.g. "category" for entities, "type" for tags).
    """
    gt_by_name: dict[str, dict[str, Any]] = {}
    for item in gt_items:
        name = _normalize_text(item.get("name"))
        if name:
            gt_by_name[name] = item

    pred_by_name: dict[str, dict[str, Any]] = {}
    for item in pred_items:
        name = _normalize_text(item.get("name"))
        if name:
            pred_by_name[name] = item

    matched_names = sorted(set(gt_by_name) & set(pred_by_name))
    missing_names = sorted(set(gt_by_name) - set(pred_by_name))
    extra_names = sorted(set(pred_by_name) - set(gt_by_name))

    gt_count = len(gt_by_name)
    pred_count = len(pred_by_name)
    matched_count = len(matched_names)

    precision = matched_count / pred_count if pred_count > 0 else (1.0 if gt_count == 0 else 0.0)
    recall = matched_count / gt_count if gt_count > 0 else (1.0 if pred_count == 0 else 0.0)

    cat_correct = 0
    cat_total = 0
    for name in matched_names:
        gt_cat = _normalize_text(gt_by_name[name].get(classify_field))
        pred_cat = _normalize_text(pred_by_name[name].get(classify_field))
        if gt_cat:
            cat_total += 1
            if gt_cat == pred_cat:
                cat_correct += 1

    category_accuracy = cat_correct / cat_total if cat_total > 0 else 1.0

    return SetScore(
        gt_count=gt_count,
        pred_count=pred_count,
        matched_count=matched_count,
        precision=precision,
        recall=recall,
        category_accuracy=category_accuracy,
        matched_names=matched_names,
        missing_names=missing_names,
        extra_names=extra_names,
    )


def score_entry_pair(gt: dict[str, Any], pred: dict[str, Any]) -> FieldScores:
    return FieldScores(
        kind=1.0 if gt.get("kind") == pred.get("kind") else 0.0,
        amount_minor=1.0 if gt.get("amount_minor") == pred.get("amount_minor") else 0.0,
        date=1.0 if gt.get("date") == pred.get("date") else 0.0,
        name=_text_similarity(gt.get("name"), pred.get("name")),
        from_entity=_text_similarity(gt.get("from_entity"), pred.get("from_entity")),
        to_entity=_text_similarity(gt.get("to_entity"), pred.get("to_entity")),
        tags=_jaccard(_normalize_tags(gt.get("tags")), _normalize_tags(pred.get("tags"))),
    )


def match_entries(
    gt_entries: list[dict[str, Any]],
    pred_entries: list[dict[str, Any]],
) -> tuple[list[EntryMatch], list[int], list[int]]:
    """Greedy match predicted entries to ground truth by (date, amount_minor) key."""
    used_gt: set[int] = set()
    used_pred: set[int] = set()
    matches: list[EntryMatch] = []

    gt_by_key: dict[tuple, list[int]] = {}
    for i, entry in enumerate(gt_entries):
        key = (entry.get("date"), entry.get("amount_minor"))
        gt_by_key.setdefault(key, []).append(i)

    for pi, pred in enumerate(pred_entries):
        key = (pred.get("date"), pred.get("amount_minor"))
        candidates = gt_by_key.get(key, [])
        for gi in candidates:
            if gi not in used_gt:
                scores = score_entry_pair(gt_entries[gi], pred)
                matches.append(EntryMatch(gt_index=gi, pred_index=pi, scores=scores))
                used_gt.add(gi)
                used_pred.add(pi)
                break

    # Second pass: try to match remaining predictions to remaining ground truth
    # using a looser criterion (date-only match, then best available).
    remaining_gt = [i for i in range(len(gt_entries)) if i not in used_gt]
    remaining_pred = [i for i in range(len(pred_entries)) if i not in used_pred]

    if remaining_gt and remaining_pred:
        for pi in list(remaining_pred):
            best_gi = None
            best_score = -1.0
            for gi in remaining_gt:
                s = score_entry_pair(gt_entries[gi], pred_entries[pi])
                avg = s.average()
                if avg > best_score and avg > 0.3:
                    best_score = avg
                    best_gi = gi
            if best_gi is not None:
                scores = score_entry_pair(gt_entries[best_gi], pred_entries[pi])
                matches.append(EntryMatch(gt_index=best_gi, pred_index=pi, scores=scores))
                remaining_gt.remove(best_gi)
                remaining_pred.remove(pi)

    unmatched_gt = [i for i in range(len(gt_entries)) if i not in {m.gt_index for m in matches}]
    unmatched_pred = [i for i in range(len(pred_entries)) if i not in {m.pred_index for m in matches}]

    return matches, unmatched_gt, unmatched_pred


def score_case(case_id: str, run_id: str) -> CaseScore:
    gt_path = CASES_DIR / case_id / "ground_truth.json"
    results_path = RESULTS_DIR / run_id / "cases" / case_id / "results.json"

    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth not found: {gt_path}")
    if not results_path.exists():
        raise FileNotFoundError(f"Results not found: {results_path}")

    gt_data = json.loads(gt_path.read_text())
    results_data = json.loads(results_path.read_text())

    # Tags & entities (set-based)
    tag_score = score_named_set(
        gt_data.get("tags", []),
        results_data.get("tags", []),
        classify_field="type",
    )
    entity_score = score_named_set(
        gt_data.get("entities", []),
        results_data.get("entities", []),
        classify_field="category",
    )

    # Entries (ordered matching)
    gt_entries = gt_data.get("entries", [])
    pred_entries = results_data.get("entries", [])

    matches, unmatched_gt, unmatched_pred = match_entries(gt_entries, pred_entries)

    gt_count = len(gt_entries)
    pred_count = len(pred_entries)
    matched = len(matches)

    precision = matched / pred_count if pred_count > 0 else (1.0 if gt_count == 0 else 0.0)
    recall = matched / gt_count if gt_count > 0 else (1.0 if pred_count == 0 else 0.0)

    if matches:
        avg_scores = FieldScores(
            kind=sum(m.scores.kind for m in matches) / matched,
            amount_minor=sum(m.scores.amount_minor for m in matches) / matched,
            date=sum(m.scores.date for m in matches) / matched,
            name=sum(m.scores.name for m in matches) / matched,
            from_entity=sum(m.scores.from_entity for m in matches) / matched,
            to_entity=sum(m.scores.to_entity for m in matches) / matched,
            tags=sum(m.scores.tags for m in matches) / matched,
        )
    else:
        avg_scores = FieldScores()

    return CaseScore(
        case_id=case_id,
        gt_count=gt_count,
        pred_count=pred_count,
        matched_count=matched,
        precision=precision,
        recall=recall,
        field_scores=avg_scores,
        tag_score=tag_score,
        entity_score=entity_score,
        matches=matches,
        unmatched_gt=unmatched_gt,
        unmatched_pred=unmatched_pred,
    )


def score_run(run_id: str) -> dict[str, Any]:
    run_dir = RESULTS_DIR / run_id
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        print(f"Error: run meta not found at {meta_path}", file=sys.stderr)
        sys.exit(1)

    meta = json.loads(meta_path.read_text())
    case_ids = meta.get("cases", [])

    case_scores: list[CaseScore] = []
    for cid in case_ids:
        try:
            cs = score_case(cid, run_id)
            case_scores.append(cs)

            score_out = {
                "case_id": cs.case_id,
                "tags": cs.tag_score.as_dict(),
                "entities": cs.entity_score.as_dict(),
                "entries": {
                    "gt_count": cs.gt_count,
                    "pred_count": cs.pred_count,
                    "matched_count": cs.matched_count,
                    "precision": round(cs.precision, 4),
                    "recall": round(cs.recall, 4),
                    "field_scores": {k: round(v, 4) for k, v in cs.field_scores.as_dict().items()},
                    "unmatched_gt_indices": cs.unmatched_gt,
                    "unmatched_pred_indices": cs.unmatched_pred,
                },
                "overall_score": round(cs.overall_score(), 4),
            }
            score_path = RESULTS_DIR / run_id / "cases" / cid / "score.json"
            score_path.write_text(json.dumps(score_out, indent=2) + "\n")
        except FileNotFoundError as exc:
            print(f"  Skipping {cid}: {exc}")

    _print_run_summary(meta, case_scores)

    return _build_run_report(meta, case_scores)


def _print_run_summary(meta: dict[str, Any], case_scores: list[CaseScore]) -> None:
    print(f"\n{'='*80}")
    print(f"Run: {meta.get('run_id')}")
    print(f"Model: {meta.get('model')}")
    print(f"{'='*80}\n")

    # Tags & entities
    print("Tags & Entities:")
    te_header = f"  {'Case':<30} {'Tag F1':>7} {'Tag Cat':>8} {'Ent F1':>7} {'Ent Cat':>8}"
    print(te_header)
    print("  " + "-" * (len(te_header) - 2))
    for cs in case_scores:
        ts, es = cs.tag_score, cs.entity_score
        print(
            f"  {cs.case_id:<30} {ts.f1():>7.2f} {ts.category_accuracy:>8.2f}"
            f" {es.f1():>7.2f} {es.category_accuracy:>8.2f}"
        )
        if ts.missing_names:
            print(f"    missing tags: {', '.join(ts.missing_names)}")
        if ts.extra_names:
            print(f"    extra tags:   {', '.join(ts.extra_names)}")
        if es.missing_names:
            print(f"    missing entities: {', '.join(es.missing_names)}")
        if es.extra_names:
            print(f"    extra entities:   {', '.join(es.extra_names)}")
    print()

    # Entries
    print("Entries:")
    header = f"  {'Case':<30} {'GT':>4} {'Pred':>5} {'Match':>5} {'Prec':>6} {'Rec':>6} {'Score':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for cs in case_scores:
        print(
            f"  {cs.case_id:<30} {cs.gt_count:>4} {cs.pred_count:>5} "
            f"{cs.matched_count:>5} {cs.precision:>6.2f} {cs.recall:>6.2f} "
            f"{cs.overall_score():>6.2f}"
        )

    if case_scores:
        avg_prec = sum(cs.precision for cs in case_scores) / len(case_scores)
        avg_rec = sum(cs.recall for cs in case_scores) / len(case_scores)
        avg_score = sum(cs.overall_score() for cs in case_scores) / len(case_scores)
        print("  " + "-" * (len(header) - 2))
        print(f"  {'AVERAGE':<30} {'':>4} {'':>5} {'':>5} {avg_prec:>6.2f} {avg_rec:>6.2f} {avg_score:>6.2f}")

    if case_scores:
        print(f"\nField-level accuracy (averaged across matched entries):")
        fields = ["kind", "amount_minor", "date", "name", "from_entity", "to_entity", "tags"]
        field_header = f"  {'Case':<30} " + " ".join(f"{f:>12}" for f in fields)
        print(field_header)
        print("  " + "-" * (len(field_header) - 2))
        for cs in case_scores:
            vals = cs.field_scores.as_dict()
            print(f"  {cs.case_id:<30} " + " ".join(f"{vals[f]:>12.2f}" for f in fields))


def _build_run_report(meta: dict[str, Any], case_scores: list[CaseScore]) -> dict[str, Any]:
    cases = []
    for cs in case_scores:
        cases.append({
            "case_id": cs.case_id,
            "tags": cs.tag_score.as_dict(),
            "entities": cs.entity_score.as_dict(),
            "entries": {
                "gt_count": cs.gt_count,
                "pred_count": cs.pred_count,
                "matched_count": cs.matched_count,
                "precision": round(cs.precision, 4),
                "recall": round(cs.recall, 4),
                "field_scores": {k: round(v, 4) for k, v in cs.field_scores.as_dict().items()},
            },
            "overall_score": round(cs.overall_score(), 4),
        })

    avg_score = sum(cs.overall_score() for cs in case_scores) / len(case_scores) if case_scores else 0

    return {
        "run_id": meta.get("run_id"),
        "model": meta.get("model"),
        "cases_count": len(case_scores),
        "average_overall_score": round(avg_score, 4),
        "cases": cases,
    }


def compare_runs(run_ids: list[str], report_name: str | None = None) -> None:
    reports = []
    for rid in run_ids:
        report = score_run(rid)
        reports.append(report)

    print(f"\n{'='*80}")
    print("MODEL COMPARISON")
    print(f"{'='*80}\n")

    header = f"{'Model':<45} {'Cases':>5} {'Prec':>6} {'Rec':>6} {'Score':>6}"
    print(header)
    print("-" * len(header))

    for r in reports:
        model_display = r["model"]
        if len(model_display) > 44:
            model_display = "..." + model_display[-41:]
        print(
            f"{model_display:<45} {r['cases_count']:>5} "
            f"{r['average_precision']:>6.2f} {r['average_recall']:>6.2f} "
            f"{r['average_overall_score']:>6.2f}"
        )

    if report_name:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        comparison = {
            "report_name": report_name,
            "runs": reports,
        }
        out_path = REPORTS_DIR / f"{report_name}.json"
        out_path.write_text(json.dumps(comparison, indent=2) + "\n")
        print(f"\nReport saved to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score benchmark results.")
    sub = parser.add_subparsers(dest="command")

    score_p = sub.add_parser("run", help="Score a single run")
    score_p.add_argument("run_id", help="Run ID to score")

    compare_p = sub.add_parser("compare", help="Compare multiple runs")
    compare_p.add_argument("run_ids", nargs="+", help="Run IDs to compare")
    compare_p.add_argument("--save-report", default=None, help="Save comparison report with this name")

    args = parser.parse_args()
    if args.command == "run":
        score_run(args.run_id)
    elif args.command == "compare":
        compare_runs(args.run_ids, report_name=args.save_report)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
