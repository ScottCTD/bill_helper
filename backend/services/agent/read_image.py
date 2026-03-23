"""Read image files from the current user's workspace for multimodal follow-up.

CALLING SPEC:
    run_read_image(context, args) -> ToolExecutionResult

Inputs:
    - current tool context with run/principal scope
    - one or more absolute image paths inside the workspace container
Outputs:
    - structured success/error payload plus optional multimodal tool-result content
Side effects:
    - ensures the user's workspace container is running and reads image bytes inside that container
"""

from __future__ import annotations

from collections.abc import Sequence
import json
from typing import Any

from sqlalchemy import select

from backend.config import get_settings
from backend.models_agent import AgentRun
from backend.services import docker_cli
from backend.services.agent.attachment_content import model_supports_vision
from backend.services.agent.tool_args.read_image import ReadImageArgs
from backend.services.agent.tool_results import error_result, format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.agent_workspace import start_user_workspace
from backend.services.runtime_settings import resolve_runtime_settings

_READ_IMAGE_PATHS_ENV = "BH_READ_IMAGE_PATHS_JSON"
_SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def run_read_image(context: ToolContext, args: ReadImageArgs) -> ToolExecutionResult:
    principal_user_id = (context.principal_user_id or "").strip()
    if not principal_user_id:
        return error_result("read_image requires a principal user.")

    model_name = _model_name_for_run(context)
    if not model_supports_vision(model_name):
        return error_result(
            "read_image is unavailable because the current model does not support vision.",
            details="Rely on parsed.md text or switch to a vision-capable model.",
        )

    settings = resolve_runtime_settings(context.db)
    if len(args.paths) > settings.agent_max_images_per_message:
        return error_result(
            f"Too many image paths. Max allowed is {settings.agent_max_images_per_message}.",
        )

    try:
        records = _read_images_from_workspace_container(
            principal_user_id=principal_user_id,
            paths=args.paths,
        )
    except (docker_cli.DockerCliError, ValueError) as exc:
        return error_result("read_image failed", details=str(exc))

    summary = f"loaded {len(records)} image(s)"
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                f"summary: {summary}",
                f"paths: {', '.join(record['path'] for record in records)}",
            ]
        ),
        output_json={
            "summary": summary,
            "paths": [record["path"] for record in records],
            "image_count": len(records),
        },
        status=ToolExecutionStatus.OK,
        llm_content=_llm_content_for_images(records),
    )


def _model_name_for_run(context: ToolContext) -> str:
    model_name = context.db.scalar(select(AgentRun.model_name).where(AgentRun.id == context.run_id))
    return str(model_name or "")


def _read_images_from_workspace_container(
    *,
    principal_user_id: str,
    paths: Sequence[str],
) -> list[dict[str, str]]:
    settings = get_settings()
    spec = start_user_workspace(user_id=principal_user_id, settings=settings)
    command = [
        "bash",
        "-lc",
        _container_reader_script(),
    ]
    try:
        completed = docker_cli.exec_in_container(
            docker_binary=spec.docker_binary,
            container_name=spec.container_name,
            command=command,
            env={_READ_IMAGE_PATHS_ENV: json.dumps(list(paths), separators=(",", ":"))},
            timeout_seconds=120.0,
        )
    except docker_cli.DockerCliError as error:
        error_detail = _error_detail_from_container_output(error.stdout)
        if error_detail is not None:
            raise ValueError(error_detail) from error
        raise

    payload = _parse_container_payload(completed.stdout)
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("read_image returned no images.")

    normalized: list[dict[str, str]] = []
    for image in images:
        if not isinstance(image, dict):
            raise ValueError("read_image returned an invalid image payload.")
        path = image.get("path")
        mime_type = image.get("mime_type")
        data_url = image.get("data_url")
        if not isinstance(path, str) or not isinstance(mime_type, str) or not isinstance(data_url, str):
            raise ValueError("read_image returned an incomplete image payload.")
        normalized.append(
            {
                "path": path,
                "mime_type": mime_type,
                "data_url": data_url,
            }
        )
    return normalized


def _parse_container_payload(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("read_image returned malformed output.") from exc
    if not isinstance(payload, dict):
        raise ValueError("read_image returned a non-object payload.")
    error_detail = payload.get("error")
    if isinstance(error_detail, str) and error_detail.strip():
        raise ValueError(error_detail.strip())
    return payload


def _error_detail_from_container_output(stdout: str) -> str | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    error_detail = payload.get("error")
    if isinstance(error_detail, str) and error_detail.strip():
        return error_detail.strip()
    return None


def _llm_content_for_images(records: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    text = "Loaded image(s) for visual inspection:\n" + "\n".join(
        f"- {record['path']}" for record in records
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for record in records:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": record["data_url"]},
            }
        )
    return content


def _container_reader_script() -> str:
    return """python - <<'PY'
import base64
import json
import mimetypes
import os
from pathlib import Path

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
WORKSPACE_ROOT = Path("/workspace").resolve()


def fail(message: str) -> None:
    print(json.dumps({"error": message}, separators=(",", ":")))
    raise SystemExit(9)


raw = os.environ.get("BH_READ_IMAGE_PATHS_JSON", "")
try:
    paths = json.loads(raw)
except json.JSONDecodeError:
    fail("read_image received invalid path payload.")

if not isinstance(paths, list) or not paths:
    fail("read_image requires at least one image path.")

images = []
for raw_path in paths:
    if not isinstance(raw_path, str):
        fail("read_image paths must be strings.")
    if not raw_path.startswith("/"):
        fail(f"path must be absolute: {raw_path}")
    path = Path(raw_path)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        fail(f"image path not found: {raw_path}")
    except OSError as exc:
        fail(f"image path could not be read: {raw_path} ({exc})")
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        fail(f"path is outside /workspace: {raw_path}")
    if not resolved.is_file():
        fail(f"path is not a file: {raw_path}")
    suffix = resolved.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        fail(f"path is not a supported image file: {raw_path}")
    mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    data_url = (
        f"data:{mime_type};base64,"
        + base64.b64encode(resolved.read_bytes()).decode("ascii")
    )
    images.append(
        {
            "path": str(path),
            "mime_type": mime_type,
            "data_url": data_url,
        }
    )

print(json.dumps({"images": images}, separators=(",", ":")))
PY"""
