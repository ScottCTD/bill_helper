from fastapi import APIRouter

from backend.routers.agent_attachments import router as attachments_router
from backend.routers.agent_reviews import router as reviews_router
from backend.routers.agent_runs import router as runs_router
from backend.routers.agent_threads import router as threads_router

router = APIRouter()
router.include_router(threads_router)
router.include_router(runs_router)
router.include_router(reviews_router)
router.include_router(attachments_router)
