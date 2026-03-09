from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
TASKS_DIR = ROOT / "tasks"
COMPLETED_TASKS_DIR = DOCS_DIR / "completed_tasks"


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


def assert_task_layout(errors: list[str]) -> None:
    required_dirs = [
        TASKS_DIR,
        COMPLETED_TASKS_DIR,
    ]
    assert_exists(required_dirs, errors)

    legacy_dirs = [
        DOCS_DIR / "exec-plans",
        DOCS_DIR / "todo",
        DOCS_DIR / "completed",
    ]
    for path in legacy_dirs:
        if path.exists():
            errors.append(
                f"Legacy execution-plan path should not exist anymore: {path.relative_to(ROOT)}"
            )


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
        ROOT / "AGENTS.md",
        ROOT / "backend" / "README.md",
        ROOT / "frontend" / "README.md",
    ]
    scan_paths.extend(
        path
        for path in DOCS_DIR.rglob("*.md")
        if "completed_tasks" not in path.parts and "adr" not in path.parts
    )
    for path in scan_paths:
        contents = read_text(path)
        for term in stale_terms:
            if term in contents:
                errors.append(
                    f"Stale term `{term}` found in {path.relative_to(ROOT)}."
                )


def assert_no_legacy_plan_refs(errors: list[str]) -> None:
    legacy_terms = [
        "docs/exec-plans/",
        "docs/todo/",
        "docs/completed/",
        "`exec-plans/`",
        "`todo/`",
        "`completed/`",
    ]
    scan_paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "backend" / "README.md",
        ROOT / "frontend" / "README.md",
    ]
    scan_paths.extend(
        path
        for path in DOCS_DIR.rglob("*.md")
        if "completed_tasks" not in path.parts
    )
    scan_paths.extend(TASKS_DIR.glob("*.md"))
    for path in scan_paths:
        contents = read_text(path)
        for term in legacy_terms:
            if term in contents:
                errors.append(
                    f"Legacy plan reference `{term}` found in {path.relative_to(ROOT)}."
                )


def assert_docs_index_links(errors: list[str]) -> None:
    index_path = DOCS_DIR / "README.md"
    index_contents = read_text(index_path)
    required_mentions = [
        "../tasks/",
        "documentation-system.md",
        "backend/README.md",
        "frontend/README.md",
        "api/README.md",
        "completed_tasks/README.md",
        "feature-entry-lifecycle.md",
        "feature-dashboard-analytics.md",
        "adr/README.md",
    ]
    for mention in required_mentions:
        if mention not in index_contents:
            errors.append(
                f"{index_path.relative_to(ROOT)} should reference `{mention}`."
            )


def assert_pointer_docs_link_to_canonical_docs(errors: list[str]) -> None:
    pointer_expectations = {
        ROOT / "backend" / "README.md": "../docs/backend.md",
        ROOT / "frontend" / "README.md": "../docs/frontend.md",
    }
    for path, expected_link in pointer_expectations.items():
        contents = read_text(path)
        if expected_link not in contents:
            errors.append(
                f"{path.relative_to(ROOT)} should link to canonical doc `{expected_link}`."
            )


def assert_subsystem_indexes_link_to_topic_maps(errors: list[str]) -> None:
    index_expectations = {
        DOCS_DIR / "backend.md": "backend/README.md",
        DOCS_DIR / "frontend.md": "frontend/README.md",
        DOCS_DIR / "api.md": "api/README.md",
    }
    for path, expected_link in index_expectations.items():
        contents = read_text(path)
        if expected_link not in contents:
            errors.append(
                f"{path.relative_to(ROOT)} should link to subsystem topic map `{expected_link}`."
            )


def main() -> int:
    errors: list[str] = []

    required_paths = [
        ROOT / "backend" / "README.md",
        ROOT / "frontend" / "README.md",
        DOCS_DIR / "backend.md",
        DOCS_DIR / "frontend.md",
        DOCS_DIR / "api.md",
        DOCS_DIR / "documentation-system.md",
        DOCS_DIR / "backend" / "README.md",
        DOCS_DIR / "frontend" / "README.md",
        DOCS_DIR / "api" / "README.md",
        DOCS_DIR / "completed_tasks" / "README.md",
        DOCS_DIR / "feature-entry-lifecycle.md",
        DOCS_DIR / "feature-dashboard-analytics.md",
        DOCS_DIR / "adr" / "README.md",
    ]
    assert_exists(required_paths, errors)
    assert_task_layout(errors)

    latest_migration = get_latest_migration_filename()
    assert_latest_migration_referenced(latest_migration, errors)
    assert_no_stale_terms(errors)
    assert_no_legacy_plan_refs(errors)
    assert_docs_index_links(errors)
    assert_pointer_docs_link_to_canonical_docs(errors)
    assert_subsystem_indexes_link_to_topic_maps(errors)

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
