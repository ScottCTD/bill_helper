from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Entry, EntryTag, Tag
from backend.schemas import TagCreate, TagRead, TagUpdate
from backend.services.entries import normalize_tag_name
from backend.services.tags import resolve_tag_color
from backend.services.taxonomy import assign_single_term_by_name, get_single_term_name, get_single_term_name_map

router = APIRouter(prefix="/tags", tags=["tags"])

TAG_TYPE_TAXONOMY_KEY = "tag_type"
TAG_TYPE_SUBJECT_TYPE = "tag"


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
def create_tag(payload: TagCreate, db: Session = Depends(get_db)) -> TagRead:
    normalized_name = normalize_tag_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name cannot be empty")

    existing = db.scalar(select(Tag).where(Tag.name == normalized_name))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

    tag = Tag(
        name=normalized_name,
        color=resolve_tag_color(payload.color),
        description=payload.description,
    )
    db.add(tag)
    db.flush()
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=payload.type,
    )
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
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)) -> TagRead:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data:
        normalized_name = normalize_tag_name(update_data["name"] or "")
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name cannot be empty")

        existing = db.scalar(select(Tag).where(Tag.name == normalized_name))
        if existing is not None and existing.id != tag.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

        tag.name = normalized_name
    if "color" in update_data:
        tag.color = update_data["color"]
    if "description" in update_data:
        tag.description = update_data["description"]
    if "type" in update_data:
        assign_single_term_by_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
            term_name=update_data["type"],
        )

    db.add(tag)
    db.commit()
    db.refresh(tag)
    entry_count = int(
        db.scalar(
            select(func.count(EntryTag.entry_id))
            .select_from(EntryTag)
            .join(Entry, Entry.id == EntryTag.entry_id)
            .where(
                EntryTag.tag_id == tag.id,
                Entry.is_deleted.is_(False),
            )
        )
        or 0
    )
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
