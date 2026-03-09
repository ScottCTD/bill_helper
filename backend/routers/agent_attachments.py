from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models_agent import AgentMessageAttachment
from backend.routers.agent_support import AGENT_ROUTER_KWARGS

router = APIRouter(**AGENT_ROUTER_KWARGS)


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: str, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(AgentMessageAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    path = Path(attachment.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is missing")
    return FileResponse(path, media_type=attachment.mime_type, filename=path.name)
