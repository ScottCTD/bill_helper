from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import require_admin_principal
from backend.database import get_db
from backend.schemas_finance import TagCreate, TagRead, TagUpdate
from backend.services.crud_policy import (
    PolicyViolation,
    translate_policy_violation,
)
from backend.services.tags import (
    build_tag_read,
    create_tag_from_payload,
    delete_tag as delete_tag_service,
    list_tag_reads,
    load_tag,
    update_tag_from_payload,
)

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("", response_model=list[TagRead])
def list_tags(db: Session = Depends(get_db)) -> list[TagRead]:
    return list_tag_reads(db)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> TagRead:
    try:
        tag = create_tag_from_payload(db, payload=payload)
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    db.commit()
    db.refresh(tag)
    return build_tag_read(db, tag=tag, entry_count=0)


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> TagRead:
    try:
        tag = load_tag(db, tag_id=tag_id)
        update_tag_from_payload(db, tag=tag, payload=payload)
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    db.commit()
    db.refresh(tag)
    return build_tag_read(db, tag=tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> None:
    try:
        delete_tag_service(db, tag=load_tag(db, tag_id=tag_id))
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc
    db.commit()
