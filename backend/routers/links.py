from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, get_current_principal
from backend.database import get_db
from backend.models_finance import EntryLink
from backend.services.access_scope import get_entry_for_principal_or_404
from backend.services.groups import recompute_entry_groups

router = APIRouter(prefix="/links", tags=["links"])


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(
    link_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    link = db.get(EntryLink, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    get_entry_for_principal_or_404(db, entry_id=link.source_entry_id, principal=principal)
    get_entry_for_principal_or_404(db, entry_id=link.target_entry_id, principal=principal)
    db.delete(link)
    db.flush()
    recompute_entry_groups(db)
    db.commit()
