from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import EntryLink
from backend.services.groups import recompute_entry_groups

router = APIRouter(prefix="/links", tags=["links"])


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: str, db: Session = Depends(get_db)) -> None:
    link = db.get(EntryLink, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(link)
    db.flush()
    recompute_entry_groups(db)
    db.commit()
