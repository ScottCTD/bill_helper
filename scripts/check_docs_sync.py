from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_latest_migration_filename() -> str:
    version_dir = ROOT / "alembic" / "versions"
    indexed_files: list[tuple[int, str]] = []
    for path in version_dir.glob("*.py"):
        match = re.match(r"^(\d{4})_.+\.py$", path.name)
        if not match:
            continue
        indexed_files.append((int(match.group(1)), path.name))
    if not indexed_files:
        raise RuntimeError("No Alembic migration files found.")
    return max(indexed_files, key=lambda pair: pair[0])[1]


def assert_exists(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        if not path.exists():
            errors.append(f"Missing required documentation file: {path.relative_to(ROOT)}")


def assert_latest_migration_referenced(latest_migration: str, errors: list[str]) -> None:
    required_reference_docs = [
        DOCS_DIR / "backend.md",
        DOCS_DIR / "repository-structure.md",
    ]
    latest_revision_token = latest_migration.removesuffix(".py")
    for path in required_reference_docs:
        contents = read_text(path)
        if latest_migration not in contents and latest_revision_token not in contents:
            errors.append(
                (
                    f"{path.relative_to(ROOT)} does not reference latest migration "
                    f"`{latest_migration}` (or `{latest_revision_token}`)."
                )
            )


def assert_no_stale_terms(errors: list[str]) -> None:
    stale_terms = [
        "EntryStatus",
        "entries.status",
        "creates entry with `status=PENDING_REVIEW`",
        "approving entry proposals creates entry with `PENDING_REVIEW`",
    ]
    scan_paths = [
        ROOT / "README.md",
        ROOT / "backend" / "README.md",
        ROOT / "frontend" / "README.md",
    ]
    scan_paths.extend(
        path
        for path in DOCS_DIR.rglob("*.md")
        if "completed" not in path.parts
        and "adr" not in path.parts
    )
    for path in scan_paths:
        contents = read_text(path)
        for term in stale_terms:
            if term in contents:
                errors.append(
                    f"Stale term `{term}` found in {path.relative_to(ROOT)}."
                )


def assert_docs_index_links(errors: list[str]) -> None:
    index_path = DOCS_DIR / "README.md"
    index_contents = read_text(index_path)
    required_mentions = [
        "documentation-system.md",
        "feature-entry-lifecycle.md",
        "feature-dashboard-analytics.md",
        "adr/README.md",
    ]
    for mention in required_mentions:
        if mention not in index_contents:
            errors.append(
                f"{index_path.relative_to(ROOT)} should reference `{mention}`."
            )


def main() -> int:
    errors: list[str] = []

    required_paths = [
        ROOT / "backend" / "README.md",
        ROOT / "frontend" / "README.md",
        DOCS_DIR / "documentation-system.md",
        DOCS_DIR / "feature-entry-lifecycle.md",
        DOCS_DIR / "feature-dashboard-analytics.md",
        DOCS_DIR / "adr" / "README.md",
    ]
    assert_exists(required_paths, errors)

    latest_migration = get_latest_migration_filename()
    assert_latest_migration_referenced(latest_migration, errors)
    assert_no_stale_terms(errors)
    assert_docs_index_links(errors)

    if errors:
        print("Documentation consistency check FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Documentation consistency check passed.")
    print(f"- Latest migration referenced: {latest_migration}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
