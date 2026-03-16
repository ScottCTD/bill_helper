# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `agent` routes.
# - Inputs: callers that import `backend/routers/agent.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `agent`.
# - Side effects: FastAPI routing and HTTP error translation.
from fastapi import APIRouter

from backend.routers.agent_attachments import router as attachments_router
from backend.routers.agent_dashboard import router as dashboard_router
from backend.routers.agent_proposals import router as proposals_router
from backend.routers.agent_reviews import router as reviews_router
from backend.routers.agent_runs import router as runs_router
from backend.routers.agent_threads import router as threads_router

router = APIRouter()
router.include_router(dashboard_router)
router.include_router(threads_router)
router.include_router(runs_router)
router.include_router(proposals_router)
router.include_router(reviews_router)
router.include_router(attachments_router)
