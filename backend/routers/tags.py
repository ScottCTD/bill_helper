from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth import RequestPrincipal, require_admin_principal
from backend.database import get_db
from backend.models_finance import Entry, EntryTag, Tag
from backend.schemas_finance import TagCreate, TagRead, TagUpdate
from backend.services.crud_policy import (
    PolicyViolation,
    translate_policy_violation,
)
from backend.services.tags import (
    TAG_TYPE_SUBJECT_TYPE,
    TAG_TYPE_TAXONOMY_KEY,
    count_entries_for_tag,
    create_tag_from_payload,
    update_tag_from_payload,
)
from backend.services.taxonomy import get_single_term_name, get_single_term_name_map

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("", response_model=list[TagRead])
def list_tags(db: Session = Depends(get_db)) -> list[TagRead]:
    entry_count_subquery = (
        select(func.count(EntryTag.entry_id))
        .select_from(EntryTag)
        .join(Entry, Entry.id == EntryTag.entry_id)
        .where(
            EntryTag.tag_id == Tag.id,
            Entry.is_deleted.is_(False),
        )
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Tag,
            entry_count_subquery.label("entry_count"),
        ).order_by(Tag.name.asc())
    ).all()
    type_by_tag_id = get_single_term_name_map(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_ids=[tag.id for tag, _ in rows],
    )
    return [
        TagRead(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            description=tag.description,
            type=type_by_tag_id.get(str(tag.id)),
            entry_count=int(entry_count or 0),
        )
        for tag, entry_count in rows
    ]


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
    return TagRead(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        description=tag.description,
        type=get_single_term_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
        ),
        entry_count=0,
    )


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _: RequestPrincipal = Depends(require_admin_principal),
) -> TagRead:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    try:
        update_tag_from_payload(db, tag=tag, payload=payload)
    except PolicyViolation as exc:
        raise translate_policy_violation(exc) from exc

    db.commit()
    db.refresh(tag)
    entry_count = count_entries_for_tag(db, tag_id=tag.id)
    return TagRead(
        id=tag.id,
        name=tag.name,
        color=tag.color,
        description=tag.description,
        type=get_single_term_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
        ),
        entry_count=entry_count,
    )
