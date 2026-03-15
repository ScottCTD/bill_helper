from __future__ import annotations

import ast
from functools import lru_cache
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
REMOVED_AGENT_PROPOSE_HANDLER_MODULE = BACKEND_DIR / "services" / "agent" / "tool_handlers_propose.py"
AGENT_PROPOSALS_PACKAGE = BACKEND_DIR / "services" / "agent" / "proposals"
REMOVED_AGENT_CHANGE_APPLY_MODULE = BACKEND_DIR / "services" / "agent" / "change_apply.py"
AGENT_APPLY_PACKAGE = BACKEND_DIR / "services" / "agent" / "apply"
REMOVED_AGENT_REVIEW_MODULE = BACKEND_DIR / "services" / "agent" / "review.py"
AGENT_REVIEWS_PACKAGE = BACKEND_DIR / "services" / "agent" / "reviews"
REMOVED_AGENT_READ_HANDLER_MODULE = BACKEND_DIR / "services" / "agent" / "tool_handlers_read.py"
AGENT_READ_TOOLS_PACKAGE = BACKEND_DIR / "services" / "agent" / "read_tools"
REMOVED_AGENT_MEMORY_HANDLER_MODULE = BACKEND_DIR / "services" / "agent" / "tool_handlers_memory.py"
REMOVED_AGENT_THREAD_HANDLER_MODULE = BACKEND_DIR / "services" / "agent" / "tool_handlers_threads.py"
REMOVED_AGENT_PROGRESS_HANDLER_MODULE = BACKEND_DIR / "services" / "agent" / "read_tools" / "progress.py"
AGENT_SESSION_TOOLS_PACKAGE = BACKEND_DIR / "services" / "agent" / "session_tools"
AGENT_MODEL_CLIENT_PATH = BACKEND_DIR / "services" / "agent" / "model_client.py"
AGENT_MODEL_CLIENT_SUPPORT_PACKAGE = BACKEND_DIR / "services" / "agent" / "model_client_support"
AGENT_ATTACHMENT_CONTENT_ASSEMBLY_PATH = BACKEND_DIR / "services" / "agent" / "attachment_content_assembly.py"
AGENT_ATTACHMENT_CONTENT_PDF_PATH = BACKEND_DIR / "services" / "agent" / "attachment_content_pdf.py"
AGENT_MESSAGE_HISTORY_CONTENT_PATH = BACKEND_DIR / "services" / "agent" / "message_history_content.py"
AGENT_MESSAGE_HISTORY_PREFIXES_PATH = BACKEND_DIR / "services" / "agent" / "message_history_prefixes.py"
AGENT_TOOL_RUNTIME_PATH = BACKEND_DIR / "services" / "agent" / "tool_runtime.py"
AGENT_TOOL_RUNTIME_SUPPORT_PACKAGE = BACKEND_DIR / "services" / "agent" / "tool_runtime_support"
AGENT_RUNTIME_SUPPORT_PACKAGE = BACKEND_DIR / "services" / "agent" / "runtime_support"
REMOVED_AGENT_CHANGE_CONTRACTS_MODULE = BACKEND_DIR / "services" / "agent" / "change_contracts.py"
AGENT_CHANGE_CONTRACTS_PACKAGE = BACKEND_DIR / "services" / "agent" / "change_contracts"
AGENT_ROUTER_PATH = BACKEND_DIR / "routers" / "agent.py"
REMOVED_AGENT_ROUTER_SUPPORT_MODULE = BACKEND_DIR / "routers" / "agent_support.py"
AGENT_ROUTER_SPLIT_MODULES = (
    BACKEND_DIR / "routers" / "agent_threads.py",
    BACKEND_DIR / "routers" / "agent_runs.py",
    BACKEND_DIR / "routers" / "agent_reviews.py",
    BACKEND_DIR / "routers" / "agent_attachments.py",
)


@lru_cache(maxsize=None)
def _parsed_module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@lru_cache(maxsize=None)
def _source_python_paths(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            paths.append(path)
    return tuple(paths)


def _assert_marker_module(path: Path) -> None:
    module = _parsed_module(path)
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
    module = _parsed_module(path)
    return {
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef)
    }


def test_service_package_init_modules_are_marker_only() -> None:
    _assert_marker_module(BACKEND_DIR / "services" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "apply" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "proposals" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "read_tools" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "reviews" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "runtime_support" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "session_tools" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "model_client_support" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "services" / "agent" / "tool_runtime_support" / "__init__.py")
    _assert_marker_module(BACKEND_DIR / "validation" / "__init__.py")


def test_backend_modules_do_not_import_agent_api_from_backend_services() -> None:
    violations: list[str] = []
    for path in _source_python_paths((BACKEND_DIR,)):
        module = _parsed_module(path)
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
    for path in _source_python_paths((BACKEND_DIR, BENCHMARK_DIR, SCRIPTS_DIR)):
        module = _parsed_module(path)
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


def test_production_modules_do_not_import_tool_args_barrel() -> None:
    violations: list[str] = []
    tool_args_package_init = AGENT_TOOL_ARGS_PACKAGE / "__init__.py"

    for path in _source_python_paths((BACKEND_DIR,)):
        if path == tool_args_package_init:
            continue
        module = _parsed_module(path)
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom):
                if node.module != "backend.services.agent.tool_args":
                    continue
                relpath = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{relpath}:{node.lineno} imports from 'backend.services.agent.tool_args' "
                    "(import the owning tool_args submodule directly)"
                )
                continue
            if not isinstance(node, ast.Import):
                continue
            for alias in node.names:
                if alias.name != "backend.services.agent.tool_args":
                    continue
                relpath = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{relpath}:{node.lineno} imports 'backend.services.agent.tool_args' "
                    "(import the owning tool_args submodule directly)"
                )
    assert not violations, "Production modules must not depend on the tool_args barrel:\n" + "\n".join(violations)


def test_agent_proposals_are_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_PROPOSE_HANDLER_MODULE.exists(), "proposal handlers should stay split into the proposals package"
    assert AGENT_PROPOSALS_PACKAGE.is_dir(), "proposals package should exist"
    for name in (
        "catalog.py",
        "entries.py",
        "groups.py",
        "normalization.py",
        "normalization_catalog.py",
        "normalization_common.py",
        "normalization_entries.py",
        "normalization_groups.py",
        "pending.py",
    ):
        assert (AGENT_PROPOSALS_PACKAGE / name).exists(), f"missing proposal module: {name}"
    group_memberships_package = AGENT_PROPOSALS_PACKAGE / "group_memberships"
    assert group_memberships_package.is_dir(), "group membership proposal helpers should stay grouped in a subpackage"
    for name in ("__init__.py", "common.py", "validation.py", "handlers.py"):
        assert (group_memberships_package / name).exists(), f"missing group membership proposal module: {name}"


def test_agent_apply_handlers_are_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_CHANGE_APPLY_MODULE.exists(), "apply handlers should stay split into the apply package"
    assert AGENT_APPLY_PACKAGE.is_dir(), "apply package should exist"
    for name in ("catalog.py", "common.py", "dispatch.py", "entries.py", "groups.py"):
        assert (AGENT_APPLY_PACKAGE / name).exists(), f"missing apply module: {name}"


def test_agent_review_workflow_is_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_REVIEW_MODULE.exists(), "review workflow should stay split into the reviews package"
    assert AGENT_REVIEWS_PACKAGE.is_dir(), "reviews package should exist"
    for name in ("common.py", "dependencies.py", "overrides.py", "workflow.py"):
        assert (AGENT_REVIEWS_PACKAGE / name).exists(), f"missing review module: {name}"


def test_agent_read_tools_are_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_READ_HANDLER_MODULE.exists(), "read tools should stay split into the read_tools package"
    assert AGENT_READ_TOOLS_PACKAGE.is_dir(), "read_tools package should exist"
    for name in ("catalog.py", "common.py", "entries.py", "groups.py", "proposals.py"):
        assert (AGENT_READ_TOOLS_PACKAGE / name).exists(), f"missing read tool module: {name}"


def test_agent_session_tools_are_grouped_in_a_package() -> None:
    assert not REMOVED_AGENT_MEMORY_HANDLER_MODULE.exists(), "memory tool handler should stay in the session_tools package"
    assert not REMOVED_AGENT_THREAD_HANDLER_MODULE.exists(), "thread tool handler should stay in the session_tools package"
    assert not REMOVED_AGENT_PROGRESS_HANDLER_MODULE.exists(), "progress tool should stay in the session_tools package"
    assert AGENT_SESSION_TOOLS_PACKAGE.is_dir(), "session_tools package should exist"
    for name in ("memory.py", "progress.py", "threads.py"):
        assert (AGENT_SESSION_TOOLS_PACKAGE / name).exists(), f"missing session tool module: {name}"


def test_agent_model_client_uses_grouped_support_modules() -> None:
    assert AGENT_MODEL_CLIENT_SUPPORT_PACKAGE.is_dir(), "model_client support package should exist"
    for name in ("client.py", "environment.py", "streaming.py", "usage.py"):
        assert (AGENT_MODEL_CLIENT_SUPPORT_PACKAGE / name).exists(), f"missing model client support module: {name}"
    assert not _defined_class_names(AGENT_MODEL_CLIENT_PATH), "model_client.py should stay a thin public seam"


def test_agent_tool_runtime_uses_grouped_support_modules() -> None:
    assert AGENT_TOOL_RUNTIME_SUPPORT_PACKAGE.is_dir(), "tool_runtime support package should exist"
    for name in (
        "catalog.py",
        "catalog_proposals.py",
        "catalog_read.py",
        "catalog_session.py",
        "definitions.py",
        "execution.py",
        "schema.py",
    ):
        assert (AGENT_TOOL_RUNTIME_SUPPORT_PACKAGE / name).exists(), f"missing tool runtime support module: {name}"
    assert not _defined_class_names(AGENT_TOOL_RUNTIME_PATH), "tool_runtime.py should stay a thin public seam"


def test_agent_message_history_helpers_are_split_by_concern() -> None:
    assert AGENT_MESSAGE_HISTORY_CONTENT_PATH.exists(), "message history content helpers should exist"
    assert AGENT_MESSAGE_HISTORY_PREFIXES_PATH.exists(), "message history prefix helpers should exist"


def test_agent_attachment_content_helpers_are_split_by_concern() -> None:
    assert AGENT_ATTACHMENT_CONTENT_ASSEMBLY_PATH.exists(), "attachment assembly helpers should exist"
    assert AGENT_ATTACHMENT_CONTENT_PDF_PATH.exists(), "attachment PDF helpers should exist"


def test_agent_runtime_uses_grouped_support_modules() -> None:
    assert AGENT_RUNTIME_SUPPORT_PACKAGE.is_dir(), "runtime support package should exist"
    for name in ("lifecycle.py", "tool_turns.py"):
        assert (AGENT_RUNTIME_SUPPORT_PACKAGE / name).exists(), f"missing runtime support module: {name}"


def test_agent_change_contracts_are_grouped_by_domain() -> None:
    assert not REMOVED_AGENT_CHANGE_CONTRACTS_MODULE.exists(), "change_contracts should stay split into a package"
    assert AGENT_CHANGE_CONTRACTS_PACKAGE.is_dir(), "change_contracts package should exist"
    for name in ("__init__.py", "catalog.py", "common.py", "entries.py", "groups.py", "patches.py"):
        assert (AGENT_CHANGE_CONTRACTS_PACKAGE / name).exists(), f"missing change-contract module: {name}"


def test_agent_router_is_split_by_http_boundary() -> None:
    assert not REMOVED_AGENT_ROUTER_SUPPORT_MODULE.exists(), "agent router helpers should stay owned by the split endpoint modules"
    for path in AGENT_ROUTER_SPLIT_MODULES:
        assert path.exists(), f"missing split router module: {path.name}"

    module = ast.parse(AGENT_ROUTER_PATH.read_text(encoding="utf-8"), filename=str(AGENT_ROUTER_PATH))
    function_names = {node.name for node in module.body if isinstance(node, ast.FunctionDef)}
    assert not function_names, "backend/routers/agent.py should stay an include-only aggregator"


def test_schema_modules_do_not_import_service_modules() -> None:
    violations: list[str] = []
    for path in (
        BACKEND_DIR / "schemas_agent.py",
        BACKEND_DIR / "schemas_finance.py",
        SETTINGS_SCHEMA_PATH,
    ):
        module = _parsed_module(path)
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
    module = _parsed_module(service_path)
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
        BACKEND_DIR / "services" / "agent" / "apply" / "catalog.py",
    ]
    violations: list[str] = []
    for service_path in service_paths:
        module = _parsed_module(service_path)
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
