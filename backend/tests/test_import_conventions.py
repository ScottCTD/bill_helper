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
SETTINGS_MODEL_PATH = BACKEND_DIR / "models_settings.py"
SETTINGS_SCHEMA_PATH = BACKEND_DIR / "schemas_settings.py"
REMOVED_AGENT_TOOL_ARGS_MODULE = BACKEND_DIR / "services" / "agent" / "tool_args.py"
AGENT_TOOL_ARGS_PACKAGE = BACKEND_DIR / "services" / "agent" / "tool_args"


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


def _defined_class_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef)
    }


def test_service_package_init_modules_are_marker_only() -> None:
    _assert_marker_module(BACKEND_DIR / "services" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "validation" / "__init__.py")


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


def test_agent_tool_args_are_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_TOOL_ARGS_MODULE.exists(), "tool_args should stay split into a package"
    assert AGENT_TOOL_ARGS_PACKAGE.is_dir(), "tool_args package should exist"


def test_schema_modules_do_not_import_service_modules() -> None:
    violations: list[str] = []
    for path in (
        BACKEND_DIR / "schemas_agent.py",
        BACKEND_DIR / "schemas_finance.py",
        SETTINGS_SCHEMA_PATH,
    ):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom):
                if not (node.module or "").startswith("backend.services"):
                    continue
                relpath = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{relpath}:{node.lineno} imports from '{node.module}' "
                    "(extract shared validators into backend.validation)"
                )
                continue
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if not alias.name.startswith("backend.services"):
                    continue
                relpath = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{relpath}:{node.lineno} imports '{alias.name}' "
                    "(extract shared validators into backend.validation)"
                )
    assert not violations, "Schema modules must not depend on service modules:\n" + "\n".join(violations)


def test_runtime_settings_contracts_are_split_from_finance_modules() -> None:
    assert SETTINGS_MODEL_PATH.exists(), "Runtime settings ORM model should live in backend/models_settings.py"
    assert SETTINGS_SCHEMA_PATH.exists(), "Runtime settings schemas should live in backend/schemas_settings.py"

    finance_model_classes = _defined_class_names(BACKEND_DIR / "models_finance.py")
    assert "RuntimeSettings" not in finance_model_classes, (
        "Runtime settings ORM should stay outside backend/models_finance.py"
    )

    finance_schema_classes = _defined_class_names(BACKEND_DIR / "schemas_finance.py")
    leaked_classes = {
        "RuntimeSettingsOverridesRead",
        "RuntimeSettingsRead",
        "RuntimeSettingsUpdate",
    } & finance_schema_classes
    assert not leaked_classes, (
        "Runtime settings schemas should stay outside backend/schemas_finance.py:\n"
        + "\n".join(sorted(leaked_classes))
    )


def test_runtime_settings_service_does_not_import_api_schemas() -> None:
    service_path = BACKEND_DIR / "services" / "runtime_settings.py"
    module = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
    violations: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == "backend.schemas_settings":
            violations.append(f"{service_path.relative_to(REPO_ROOT)}:{node.lineno} imports from backend.schemas_settings")
            continue
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name != "backend.schemas_settings":
                continue
            violations.append(
                f"{service_path.relative_to(REPO_ROOT)}:{node.lineno} imports backend.schemas_settings"
            )
    assert not violations, (
        "runtime_settings service should expose service-local contracts and leave HTTP schemas in the router:\n"
        + "\n".join(violations)
    )


def test_finance_write_services_do_not_import_http_write_schemas() -> None:
    write_schema_names = {
        "AccountCreate",
        "AccountUpdate",
        "EntityCreate",
        "EntityUpdate",
        "TagCreate",
        "TagUpdate",
    }
    service_paths = [
        BACKEND_DIR / "services" / "accounts.py",
        BACKEND_DIR / "services" / "entities.py",
        BACKEND_DIR / "services" / "tags.py",
        BACKEND_DIR / "services" / "agent" / "change_apply.py",
    ]
    violations: list[str] = []
    for service_path in service_paths:
        module = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module == "backend.schemas_finance":
                imported_names = {alias.name for alias in node.names}
                leaked_names = sorted(imported_names & write_schema_names)
                if leaked_names:
                    violations.append(
                        f"{service_path.relative_to(REPO_ROOT)}:{node.lineno} imports HTTP write schemas "
                        + ", ".join(leaked_names)
                    )
    assert not violations, (
        "Finance write services should use backend.services.finance_contracts instead of HTTP write schemas:\n"
        + "\n".join(violations)
    )
