# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `agent_dashboard` routes.
# - Inputs: callers that import `backend/routers/agent_dashboard.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `agent_dashboard`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.schemas_agent import AgentDashboardRead
from backend.services.agent_dashboard import AgentDashboardRangeKey, build_agent_dashboard_read

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


@router.get("/dashboard", response_model=AgentDashboardRead)
def get_agent_dashboard(
    range: AgentDashboardRangeKey = Query(default="30d"),
    model: list[str] | None = Query(default=None),
    surface: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> AgentDashboardRead:
    return build_agent_dashboard_read(
        db,
        principal=principal,
        range_key=range,
        model_names=model,
        surfaces=surface,
    )
