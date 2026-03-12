from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.database import get_db
from backend.services.access_scope import load_attachment_for_principal

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


@router.get("/attachments/{attachment_id}")
def get_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> FileResponse:
    attachment = load_attachment_for_principal(db, attachment_id=attachment_id, principal=principal)
    path = Path(attachment.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is missing")
    return FileResponse(path, media_type=attachment.mime_type, filename=path.name)
