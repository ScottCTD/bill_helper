"""Create, list, and restore DB snapshots for benchmarking.

Usage:
    uv run python -m benchmark.snapshot create [--name NAME]
    uv run python -m benchmark.snapshot list
    uv run python -m benchmark.snapshot restore NAME
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS_DIR = REPO_ROOT / "benchmark" / "fixtures" / "snapshots"
PRODUCTION_DB_PATH = REPO_ROOT / ".data" / "bill_helper.db"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_snapshot(name: str, *, source_db: Path | None = None) -> Path:
    source = source_db or PRODUCTION_DB_PATH
    if not source.exists():
        print(f"Error: source database not found at {source}", file=sys.stderr)
        sys.exit(1)

    snapshot_dir = SNAPSHOTS_DIR / name
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    dest = snapshot_dir / "db.sqlite3"
    shutil.copy2(source, dest)

    metadata = {
        "name": name,
        "created_at": _utc_now_iso(),
        "source_path": str(source),
        "size_bytes": dest.stat().st_size,
    }
    (snapshot_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"Snapshot '{name}' created at {snapshot_dir}")
    print(f"  DB size: {metadata['size_bytes']:,} bytes")
    return snapshot_dir


def list_snapshots() -> list[dict]:
    if not SNAPSHOTS_DIR.exists():
        print("No snapshots directory found.")
        return []

    snapshots = []
    for child in sorted(SNAPSHOTS_DIR.iterdir()):
        meta_path = child / "metadata.json"
        db_path = child / "db.sqlite3"
        if not child.is_dir():
            continue
        entry: dict = {"name": child.name, "has_db": db_path.exists()}
        if meta_path.exists():
            entry.update(json.loads(meta_path.read_text()))
        snapshots.append(entry)

    if not snapshots:
        print("No snapshots found.")
    else:
        print(f"{'Name':<20} {'Created':<28} {'Size':>12}  {'DB?'}")
        print("-" * 68)
        for s in snapshots:
            size = f"{s.get('size_bytes', 0):,}" if s.get("size_bytes") else "?"
            print(f"{s['name']:<20} {s.get('created_at', '?'):<28} {size:>12}  {'yes' if s['has_db'] else 'NO'}")
    return snapshots


def get_snapshot_db_path(name: str) -> Path:
    db_path = SNAPSHOTS_DIR / name / "db.sqlite3"
    if not db_path.exists():
        print(f"Error: snapshot '{name}' DB not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    return db_path


def restore_snapshot(name: str) -> None:
    """Copy snapshot DB over the production DB path. DESTRUCTIVE to production DB."""
    db_path = get_snapshot_db_path(name)
    PRODUCTION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, PRODUCTION_DB_PATH)
    print(f"Restored snapshot '{name}' to {PRODUCTION_DB_PATH}")
    print("WARNING: production DB has been overwritten. Restart the app to use it.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage benchmark DB snapshots.")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create", help="Create a new snapshot from the production DB")
    create_p.add_argument("--name", default="default", help="Snapshot name (default: 'default')")
    create_p.add_argument("--source", default=None, help="Path to source DB (default: production DB)")

    sub.add_parser("list", help="List existing snapshots")

    restore_p = sub.add_parser("restore", help="Restore a snapshot to the production DB path (DESTRUCTIVE)")
    restore_p.add_argument("name", help="Snapshot name to restore")

    args = parser.parse_args()
    if args.command == "create":
        source = Path(args.source) if args.source else None
        create_snapshot(args.name, source_db=source)
    elif args.command == "list":
        list_snapshots()
    elif args.command == "restore":
        restore_snapshot(args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
