from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
BENCHMARK_DIR = REPO_ROOT / "benchmark"
SCRIPTS_DIR = REPO_ROOT / "scripts"

AGENT_API_EXPORT_NAMES = {
    "AgentRuntimeUnavailable",
    "approve_change_item",
    "ensure_agent_available",
    "interrupt_agent_run",
    "reject_change_item",
    "run_existing_agent_run",
    "run_existing_agent_run_stream",
    "run_agent_turn",
    "start_agent_run",
}

BANNED_DOMAIN_FACADES = {
    "backend.models",
    "backend.schemas",
    "backend.enums",
}
REMOVED_FACADE_PATHS = {
    BACKEND_DIR / "models.py",
    BACKEND_DIR / "schemas.py",
    BACKEND_DIR / "enums.py",
}


def _assert_marker_module(path: Path) -> None:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    non_docstring_nodes = [
        node
        for node in module.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert not non_docstring_nodes, f"{path} should remain marker/docstring-only"


def test_service_package_init_modules_are_marker_only() -> None:
    _assert_marker_module(BACKEND_DIR / "services" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "__init__.py")


def test_backend_modules_do_not_import_agent_api_from_backend_services() -> None:
    violations: list[str] = []
    for path in BACKEND_DIR.rglob("*.py"):
        if "tests" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "backend.services":
                continue
            for alias in node.names:
                if alias.name in AGENT_API_EXPORT_NAMES or alias.name == "*":
                    relpath = path.relative_to(REPO_ROOT)
                    violations.append(f"{relpath}:{node.lineno} imports `{alias.name}` from backend.services")
    assert not violations, "Use explicit backend.services.agent.* module imports:\n" + "\n".join(violations)


def test_repo_modules_do_not_import_domain_facade_god_modules() -> None:
    violations: list[str] = []
    for root in (BACKEND_DIR, BENCHMARK_DIR, SCRIPTS_DIR):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom):
                    if node.module not in BANNED_DOMAIN_FACADES:
                        continue
                    relpath = path.relative_to(REPO_ROOT)
                    violations.append(
                        f"{relpath}:{node.lineno} imports from '{node.module}' "
                        "(use *_finance/*_agent domain modules)"
                    )
                    continue
                if not isinstance(node, ast.Import):
                    continue
                for alias in node.names:
                    if alias.name not in BANNED_DOMAIN_FACADES:
                        continue
                    relpath = path.relative_to(REPO_ROOT)
                    violations.append(
                        f"{relpath}:{node.lineno} imports '{alias.name}' "
                        "(use *_finance/*_agent domain modules)"
                    )
    assert not violations, "Import explicit domain modules instead of facades:\n" + "\n".join(violations)


def test_legacy_domain_facades_are_removed() -> None:
    remaining = [path.relative_to(REPO_ROOT) for path in REMOVED_FACADE_PATHS if path.exists()]
    assert not remaining, "Legacy facade modules should stay deleted:\n" + "\n".join(str(path) for path in remaining)
