# CALLING SPEC:
# - Purpose: provide request/response contracts for `workspace` routes.
# - Inputs: callers that import `backend/schemas_workspace.py` and pass module-defined arguments or framework events.
# - Outputs: schema models for workspace lifecycle and IDE launch reads.
# - Side effects: module-local behavior only.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WorkspaceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceSnapshotRead(WorkspaceSchema):
    workspace_enabled: bool
    starts_on_login: bool = False
    status: str
    container_name: str
    volume_name: str
    ide_ready: bool
    ide_launch_path: str
    degraded_reason: str | None = None


class WorkspaceIdeSessionRead(WorkspaceSchema):
    launch_url: str
    snapshot: WorkspaceSnapshotRead
