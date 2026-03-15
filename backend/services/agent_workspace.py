# CALLING SPEC:
# - Purpose: implement focused service logic for `agent_workspace`.
# - Inputs: callers that import `backend/services/agent_workspace.py` and pass module-defined arguments or framework events.
# - Outputs: dataclasses and helpers for sandbox spec creation plus Docker-backed workspace lifecycle operations.
# - Side effects: filesystem directory creation and Docker CLI operations when workspace provisioning is enabled.
from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import socket
import threading
import time

import httpx
from starlette import status

from backend.config import Settings, get_settings
from backend.services import docker_cli
from backend.services.crud_policy import PolicyViolation
from backend.services.user_files import ensure_user_file_roots, user_file_owner_root

WORKSPACE_CONTAINER_PREFIX = "bill-helper-sandbox-"
WORKSPACE_VOLUME_PREFIX = "bill-helper-workspace-"
WORKSPACE_CONTAINER_REVISION = "ide-v12"
WORKSPACE_IDE_PORT = 13337
WORKSPACE_IDE_READY_TIMEOUT_SECONDS = 12.0

logger = logging.getLogger(__name__)
_workspace_locks: dict[str, threading.RLock] = {}
_workspace_locks_guard = threading.Lock()


@dataclass(slots=True, frozen=True)
class UserWorkspaceSpec:
    user_id: str
    image: str
    docker_binary: str
    container_name: str
    volume_name: str
    data_bind_source: Path
    container_revision: str
    ide_port: int
    ide_launch_path: str
    workspace_mount_path: str = "/workspace"
    data_mount_path: str = "/data"


@dataclass(slots=True, frozen=True)
class UserWorkspaceRuntime:
    workspace_enabled: bool
    starts_on_login: bool
    status: str
    ide_ready: bool
    ide_launch_path: str
    ide_host_port: int | None = None
    degraded_reason: str | None = None


def build_user_workspace_spec(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    resolved_settings = settings or get_settings()
    return UserWorkspaceSpec(
        user_id=user_id,
        image=resolved_settings.agent_workspace_image,
        docker_binary=resolved_settings.agent_workspace_docker_binary,
        container_name=f"{WORKSPACE_CONTAINER_PREFIX}{user_id}",
        volume_name=f"{WORKSPACE_VOLUME_PREFIX}{user_id}",
        data_bind_source=user_file_owner_root(
            user_id=user_id,
            data_dir=resolved_settings.data_dir,
        ).resolve(),
        container_revision=WORKSPACE_CONTAINER_REVISION,
        ide_port=WORKSPACE_IDE_PORT,
        ide_launch_path=f"{resolved_settings.api_prefix}/workspace/ide/",
    )


def _workspace_provisioning_enabled(settings: Settings | None = None) -> bool:
    resolved_settings = settings or get_settings()
    return resolved_settings.agent_workspace_enabled


def workspace_starts_on_login(settings: Settings | None = None) -> bool:
    return _workspace_provisioning_enabled(settings)


def _workspace_labels(*, spec: UserWorkspaceSpec) -> dict[str, str]:
    return {
        "bill-helper.role": "agent-workspace",
        "bill-helper.user-id": spec.user_id,
        "bill-helper.workspace-revision": spec.container_revision,
    }


def ensure_user_workspace_provisioned(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    with _workspace_lock(user_id):
        return _ensure_user_workspace_provisioned(user_id=user_id, settings=settings)


def _ensure_user_workspace_provisioned(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    resolved_settings = settings or get_settings()
    ensure_user_file_roots(user_id=user_id, data_dir=resolved_settings.data_dir)
    spec = build_user_workspace_spec(user_id=user_id, settings=resolved_settings)
    if not _workspace_provisioning_enabled(resolved_settings):
        return spec
    if not docker_cli.image_exists(
        docker_binary=spec.docker_binary,
        image=spec.image,
    ):
        raise PolicyViolation(
            detail=(
                "Agent workspace image is missing. "
                f"Expected Docker image `{spec.image}` to exist before user workspace provisioning."
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    try:
        docker_cli.ensure_volume(
            docker_binary=spec.docker_binary,
            volume_name=spec.volume_name,
        )
        if _workspace_container_needs_recreate(spec=spec):
            docker_cli.remove_container_if_exists(
                docker_binary=spec.docker_binary,
                container_name=spec.container_name,
            )
        if not docker_cli.container_exists(
            docker_binary=spec.docker_binary,
            container_name=spec.container_name,
        ):
            docker_cli.create_container(
                docker_binary=spec.docker_binary,
                container_name=spec.container_name,
                image=spec.image,
                workspace_volume_name=spec.volume_name,
                data_bind_source=str(spec.data_bind_source),
                published_tcp_ports=[spec.ide_port],
                labels=_workspace_labels(spec=spec),
            )
    except docker_cli.DockerCliError as error:
        raise PolicyViolation(
            detail=f"Failed to provision agent workspace: {error}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from error
    return spec


def start_user_workspace(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    with _workspace_lock(user_id):
        spec = ensure_user_workspace_provisioned(user_id=user_id, settings=settings)
        resolved_settings = settings or get_settings()
        if not _workspace_provisioning_enabled(resolved_settings):
            return spec
        try:
            docker_cli.start_container(
                docker_binary=spec.docker_binary,
                container_name=spec.container_name,
            )
            _wait_for_workspace_ide_ready(spec=spec)
        except docker_cli.DockerCliError as error:
            raise PolicyViolation(
                detail=f"Failed to start agent workspace: {error}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from error
        return spec


def stop_user_workspace(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    with _workspace_lock(user_id):
        spec = build_user_workspace_spec(user_id=user_id, settings=settings)
        resolved_settings = settings or get_settings()
        if not _workspace_provisioning_enabled(resolved_settings):
            return spec
        try:
            docker_cli.stop_container(
                docker_binary=spec.docker_binary,
                container_name=spec.container_name,
            )
        except docker_cli.DockerCliError as error:
            raise PolicyViolation(
                detail=f"Failed to stop agent workspace: {error}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from error
        return spec


def remove_user_workspace(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceSpec:
    with _workspace_lock(user_id):
        spec = build_user_workspace_spec(user_id=user_id, settings=settings)
        resolved_settings = settings or get_settings()
        if not _workspace_provisioning_enabled(resolved_settings):
            return spec
        try:
            docker_cli.remove_container_if_exists(
                docker_binary=spec.docker_binary,
                container_name=spec.container_name,
            )
            docker_cli.remove_volume_if_exists(
                docker_binary=spec.docker_binary,
                volume_name=spec.volume_name,
            )
        except docker_cli.DockerCliError as error:
            raise PolicyViolation(
                detail=f"Failed to remove agent workspace: {error}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from error
        return spec


def build_user_workspace_runtime(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> UserWorkspaceRuntime:
    resolved_settings = settings or get_settings()
    spec = build_user_workspace_spec(user_id=user_id, settings=resolved_settings)
    starts_on_login = workspace_starts_on_login(resolved_settings)
    if not _workspace_provisioning_enabled(resolved_settings):
        return UserWorkspaceRuntime(
            workspace_enabled=False,
            starts_on_login=False,
            status="disabled",
            ide_ready=False,
            ide_launch_path=spec.ide_launch_path,
            degraded_reason="Workspace provisioning is disabled in the backend configuration.",
        )
    if not docker_cli.image_exists(
        docker_binary=spec.docker_binary,
        image=spec.image,
    ):
        return UserWorkspaceRuntime(
            workspace_enabled=True,
            starts_on_login=starts_on_login,
            status="image_missing",
            ide_ready=False,
            ide_launch_path=spec.ide_launch_path,
            degraded_reason=(
                "Agent workspace image is missing. "
                f"Build Docker image `{spec.image}` before starting the workspace."
            ),
        )
    try:
        ensure_user_workspace_provisioned(user_id=user_id, settings=resolved_settings)
    except PolicyViolation as error:
        return UserWorkspaceRuntime(
            workspace_enabled=True,
            starts_on_login=starts_on_login,
            status="provisioning_error",
            ide_ready=False,
            ide_launch_path=spec.ide_launch_path,
            degraded_reason=error.detail,
        )
    return _runtime_from_spec(spec=spec, starts_on_login=starts_on_login)


def require_user_workspace_ide_host_port(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> int:
    runtime = build_user_workspace_runtime(user_id=user_id, settings=settings)
    if runtime.status != "running" or not runtime.ide_ready or runtime.ide_host_port is None:
        detail = runtime.degraded_reason or "Workspace IDE is not running."
        raise PolicyViolation(
            detail=detail,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return runtime.ide_host_port


def queue_best_effort_user_workspace_start(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> None:
    resolved_settings = settings or get_settings()
    if not workspace_starts_on_login(resolved_settings):
        return

    def _runner() -> None:
        try:
            start_user_workspace(user_id=user_id, settings=resolved_settings)
        except PolicyViolation as error:
            logger.warning(
                "Best-effort workspace start failed for user %s: %s",
                user_id,
                error.detail,
            )
        except Exception:
            logger.exception("Best-effort workspace start crashed for user %s", user_id)

    threading.Thread(
        target=_runner,
        name=f"workspace-start-{user_id}",
        daemon=True,
    ).start()


def queue_best_effort_user_workspace_stop(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> None:
    resolved_settings = settings or get_settings()

    def _runner() -> None:
        try:
            stop_user_workspace(user_id=user_id, settings=resolved_settings)
        except PolicyViolation as error:
            logger.warning(
                "Best-effort workspace stop failed for user %s: %s",
                user_id,
                error.detail,
            )
        except Exception:
            logger.exception("Best-effort workspace stop crashed for user %s", user_id)

    threading.Thread(
        target=_runner,
        name=f"workspace-stop-{user_id}",
        daemon=True,
    ).start()


def _workspace_container_needs_recreate(*, spec: UserWorkspaceSpec) -> bool:
    if not docker_cli.container_exists(
        docker_binary=spec.docker_binary,
        container_name=spec.container_name,
    ):
        return False
    inspected = docker_cli.inspect_container(
        docker_binary=spec.docker_binary,
        container_name=spec.container_name,
    )
    config = inspected.get("Config")
    if not isinstance(config, dict):
        return True
    labels = config.get("Labels")
    if not isinstance(labels, dict):
        return True
    if labels.get("bill-helper.workspace-revision") != spec.container_revision:
        return True
    if config.get("Image") != spec.image:
        return True
    mounts = inspected.get("Mounts")
    if not isinstance(mounts, list):
        return True
    has_workspace_volume = False
    has_data_bind = False
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        if mount.get("Type") == "volume" and mount.get("Destination") == spec.workspace_mount_path:
            has_workspace_volume = mount.get("Name") == spec.volume_name
        if mount.get("Type") == "bind" and mount.get("Destination") == spec.data_mount_path:
            has_data_bind = (
                mount.get("RW") is False
                and _mount_source_matches_expected(
                    mount_source=mount.get("Source"),
                    expected_source=spec.data_bind_source,
                )
            )
    if not has_workspace_volume or not has_data_bind:
        return True
    return docker_cli.container_host_port(inspected=inspected, container_port=spec.ide_port) is None


def _mount_source_matches_expected(*, mount_source: object, expected_source: Path) -> bool:
    if not isinstance(mount_source, str) or not mount_source:
        return False
    expected_text = expected_source.as_posix()
    return mount_source == expected_text or mount_source.endswith(expected_text)


def _runtime_from_spec(
    *,
    spec: UserWorkspaceSpec,
    starts_on_login: bool,
) -> UserWorkspaceRuntime:
    try:
        inspected = docker_cli.inspect_container(
            docker_binary=spec.docker_binary,
            container_name=spec.container_name,
        )
    except docker_cli.DockerCliError:
        return UserWorkspaceRuntime(
            workspace_enabled=True,
            starts_on_login=starts_on_login,
            status="missing",
            ide_ready=False,
            ide_launch_path=spec.ide_launch_path,
            degraded_reason="Workspace container is not provisioned.",
        )
    state = inspected.get("State")
    if not isinstance(state, dict):
        return UserWorkspaceRuntime(
            workspace_enabled=True,
            starts_on_login=starts_on_login,
            status="missing",
            ide_ready=False,
            ide_launch_path=spec.ide_launch_path,
            degraded_reason="Workspace container state is unavailable.",
        )
    status_value = state.get("Status")
    status_text = status_value if isinstance(status_value, str) and status_value else "missing"
    ide_host_port = docker_cli.container_host_port(
        inspected=inspected,
        container_port=spec.ide_port,
    )
    ide_ready = (
        status_text == "running"
        and ide_host_port is not None
        and _ide_http_endpoint_ready(host_port=ide_host_port)
    )
    degraded_reason: str | None = None
    if status_text == "running" and not ide_ready:
        degraded_reason = "Workspace container is running but the IDE endpoint is not reachable yet."
    elif status_text != "running":
        degraded_reason = "Start workspace to launch the IDE."
    return UserWorkspaceRuntime(
        workspace_enabled=True,
        starts_on_login=starts_on_login,
        status=status_text,
        ide_ready=ide_ready,
        ide_launch_path=spec.ide_launch_path,
        ide_host_port=ide_host_port,
        degraded_reason=degraded_reason,
    )


def _wait_for_workspace_ide_ready(*, spec: UserWorkspaceSpec) -> None:
    deadline = time.monotonic() + WORKSPACE_IDE_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        runtime = _runtime_from_spec(spec=spec, starts_on_login=workspace_starts_on_login())
        if runtime.status == "running" and runtime.ide_ready:
            return
        time.sleep(0.25)
    raise PolicyViolation(
        detail="Workspace IDE did not become reachable after startup.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _ide_http_endpoint_ready(*, host_port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", host_port), timeout=0.5):
            pass
    except OSError:
        return False
    try:
        response = httpx.get(
            f"http://127.0.0.1:{host_port}/",
            follow_redirects=False,
            timeout=1.0,
        )
        return response.status_code in {200, 302, 304}
    except httpx.HTTPError:
        return False


def _workspace_lock(user_id: str) -> threading.RLock:
    with _workspace_locks_guard:
        lock = _workspace_locks.get(user_id)
        if lock is None:
            lock = threading.RLock()
            _workspace_locks[user_id] = lock
        return lock
