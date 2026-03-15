# CALLING SPEC:
# - Purpose: implement focused service logic for `workspace_browser`.
# - Inputs: callers that import `backend/services/workspace_browser.py` and pass module-defined arguments or framework events.
# - Outputs: workspace snapshot dataclasses for lifecycle and IDE launch state.
# - Side effects: filesystem reads for user file roots and Docker inspect calls when workspace provisioning is enabled.
from __future__ import annotations

from dataclasses import dataclass

from backend.config import Settings, get_settings
from backend.services.agent_workspace import (
    build_user_workspace_runtime,
    build_user_workspace_spec,
)
from backend.services.user_files import ensure_user_file_roots


@dataclass(slots=True)
class WorkspaceSnapshotView:
    workspace_enabled: bool
    starts_on_login: bool
    status: str
    container_name: str
    volume_name: str
    ide_ready: bool
    ide_launch_path: str
    degraded_reason: str | None


def build_user_workspace_snapshot(
    *,
    user_id: str,
    settings: Settings | None = None,
) -> WorkspaceSnapshotView:
    resolved_settings = settings or get_settings()
    ensure_user_file_roots(user_id=user_id, data_dir=resolved_settings.data_dir)
    spec = build_user_workspace_spec(user_id=user_id, settings=resolved_settings)
    runtime = build_user_workspace_runtime(user_id=user_id, settings=resolved_settings)
    return WorkspaceSnapshotView(
        workspace_enabled=runtime.workspace_enabled,
        starts_on_login=runtime.starts_on_login,
        status=runtime.status,
        container_name=spec.container_name,
        volume_name=spec.volume_name,
        ide_ready=runtime.ide_ready,
        ide_launch_path=runtime.ide_launch_path,
        degraded_reason=runtime.degraded_reason,
    )
