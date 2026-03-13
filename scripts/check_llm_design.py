#!/usr/bin/env python3
# CALLING SPEC:
# - Purpose: verify the non-iOS LLM-oriented hard rules for production modules across backend, frontend, telegram, scripts, and benchmark.
# - Inputs: scans repository files under the configured source roots; no CLI args are required.
# - Outputs: prints a pass/fail report and exits with status `0` on success or `1` on violations.
# - Side effects: reads source files only.

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE_ROOTS = (
    ROOT / "backend",
    ROOT / "frontend" / "src",
    ROOT / "telegram",
    ROOT / "scripts",
    ROOT / "benchmark",
)
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx"}
MAX_LOC = 800
CALLING_SPEC_TOKEN = "CALLING SPEC:"
SKIP_PARTS = {
    "__pycache__",
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    "coverage",
    "ios",
}
SKIP_FILE_MARKERS = (".test.", ".spec.")
PYTHON_EXTRA_FORBID_TOKEN = 'extra="forbid"'
PYTHON_EXTRA_FORBID_TOKEN_SINGLE = "extra='forbid'"


@dataclass(frozen=True, slots=True)
class Violation:
    path: Path
    message: str


def _iter_target_files() -> list[Path]:
    files: list[Path] = []
    for root in INCLUDE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in SOURCE_EXTENSIONS or not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if "tests" in path.parts or "test" in path.parts or path.name.startswith("test_"):
                continue
            if any(marker in path.name for marker in SKIP_FILE_MARKERS):
                continue
            files.append(path)
    return sorted(files)


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _check_calling_spec(path: Path, lines: list[str]) -> Violation | None:
    head = "\n".join(lines[:12])
    if CALLING_SPEC_TOKEN in head:
        return None
    return Violation(path, "missing top-of-file calling spec block")


def _check_line_count(path: Path, lines: list[str]) -> Violation | None:
    if len(lines) <= MAX_LOC:
        return None
    return Violation(path, f"exceeds {MAX_LOC} LOC ({len(lines)})")


def _handler_uses_context_reporting(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"debug", "info", "warning", "error", "exception", "critical"}:
            return True
        if isinstance(func, ast.Name) and func.id in {"recoverable_result", "print"}:
            return True
    return False


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    has_raise = any(isinstance(node, ast.Raise) for node in ast.walk(handler))
    swallows = any(isinstance(node, (ast.Return, ast.Break, ast.Continue)) for node in ast.walk(handler))
    return has_raise and not swallows


def _is_broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id in {"Exception", "BaseException"}:
        return True
    return False


def _check_python_broad_excepts(path: Path, text: str) -> list[Violation]:
    violations: list[Violation] = []
    module = ast.parse(text, filename=str(path))
    for node in ast.walk(module):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad_handler(node):
            continue
        if _handler_reraises(node):
            continue
        if _handler_uses_context_reporting(node):
            continue
        violations.append(
            Violation(path, f"broad exception handler without contextual reporting at line {node.lineno}")
        )
    return violations


def _is_basemodel_base(base: ast.expr) -> bool:
    if isinstance(base, ast.Name):
        return base.id == "BaseModel"
    if isinstance(base, ast.Attribute):
        return base.attr == "BaseModel"
    return False


def _module_defines_direct_basemodel_subclass(path: Path, text: str) -> bool:
    module = ast.parse(text, filename=str(path))
    for node in module.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if any(_is_basemodel_base(base) for base in node.bases):
            return True
    return False


def _check_python_extra_forbid(path: Path, text: str) -> Violation | None:
    if "BaseModel" not in text:
        return None
    if not _module_defines_direct_basemodel_subclass(path, text):
        return None
    if PYTHON_EXTRA_FORBID_TOKEN in text or PYTHON_EXTRA_FORBID_TOKEN_SINGLE in text:
        return None
    return Violation(path, 'BaseModel module missing `extra="forbid"` contract')


def main() -> int:
    violations: list[Violation] = []
    for path in _iter_target_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for check in (_check_line_count(path, lines), _check_calling_spec(path, lines)):
            if check is not None:
                violations.append(check)
        if path.suffix == ".py":
            violations.extend(_check_python_broad_excepts(path, text))
            forbid_violation = _check_python_extra_forbid(path, text)
            if forbid_violation is not None:
                violations.append(forbid_violation)

    if violations:
        print("LLM design check FAILED:")
        for violation in violations:
            print(f"- {violation.path.relative_to(ROOT)}: {violation.message}")
        return 1

    print("LLM design check passed.")
    print(f"- Checked {len(_iter_target_files())} non-iOS production modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
