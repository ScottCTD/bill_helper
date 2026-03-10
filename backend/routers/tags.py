from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal, require_admin_principal
from backend.database import get_db
from backend.schemas_finance import TagCreate, TagRead, TagUpdate
from backend.services.finance_contracts import TagCreateCommand, TagPatch
from backend.services.tags import (
    build_tag_read,
    create_tag as create_tag_service,
    delete_tag as delete_tag_service,
    list_tag_reads,
    load_tag,
    update_tag as update_tag_service,
)

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("", response_model=list[TagRead])
def list_tags(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> list[TagRead]:
    return list_tag_reads(db, principal=principal)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> TagRead:
    tag = create_tag_service(
        db,
        command=TagCreateCommand.model_validate(payload.model_dump()),
    )

    db.commit()
    db.refresh(tag)
    return build_tag_read(db, tag=tag, principal=principal, entry_count=0)


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(require_admin_principal),
) -> TagRead:
    tag = load_tag(db, tag_id=tag_id)
    update_tag_service(
        db,
        tag=tag,
        patch=TagPatch.model_validate(payload.model_dump(exclude_unset=True)),
    )

    db.commit()
    db.refresh(tag)
    return build_tag_read(db, tag=tag, principal=principal)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> None:
    delete_tag_service(db, tag=load_tag(db, tag_id=tag_id))
    db.commit()
