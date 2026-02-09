from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.config import get_settings
from backend.database import get_db
from backend.enums import EntryKind
from backend.models import Account, Entity, Entry, EntryLink, Tag, User
from backend.schemas import (
    EntryCreate,
    EntryDetailRead,
    EntryListResponse,
    EntryRead,
    EntryUpdate,
    LinkCreate,
    LinkRead,
)
from backend.services.entries import normalize_tag_name, set_entry_tags, soft_delete_entry
from backend.services.entities import get_or_create_entity, normalize_entity_name
from backend.services.groups import assign_initial_group, recompute_entry_groups
from backend.services.serializers import entry_to_detail_schema, entry_to_schema, link_to_schema
from backend.services.users import ensure_current_user, get_or_create_user, normalize_user_name

router = APIRouter(prefix="/entries", tags=["entries"])


def _entry_query():
    return select(Entry).where(Entry.is_deleted.is_(False))


def _get_entry_or_404(db: Session, entry_id: str) -> Entry:
    entry = db.scalar(
        _entry_query()
        .where(Entry.id == entry_id)
        .options(
            selectinload(Entry.tags),
            selectinload(Entry.outgoing_links),
            selectinload(Entry.incoming_links),
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry


def _ensure_account_exists(db: Session, account_id: str | None) -> None:
    if account_id is None:
        return
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


def _resolve_entity_value(
    db: Session,
    *,
    entity_id: str | None,
    entity_name: str | None,
    field_name: str,
) -> tuple[str | None, str | None]:
    normalized_name = normalize_entity_name(entity_name) if entity_name is not None else None
    if normalized_name == "":
        normalized_name = None

    if entity_id:
        entity = db.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{field_name} entity not found")
        if normalized_name is not None and entity.name.lower() != normalized_name.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} entity id and name do not match",
            )
        return entity.id, entity.name

    if normalized_name is not None:
        entity = get_or_create_entity(db, normalized_name)
        return entity.id, entity.name

    return None, None


def _resolve_user_value(
    db: Session,
    *,
    user_id: str | None,
    user_name: str | None,
    field_name: str,
) -> tuple[str | None, str | None]:
    normalized_name = normalize_user_name(user_name) if user_name is not None else None
    if normalized_name == "":
        normalized_name = None

    if user_id:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{field_name} user not found")
        if normalized_name is not None and user.name.lower() != normalized_name.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} user id and name do not match",
            )
        return user.id, user.name

    if normalized_name is not None:
        user = get_or_create_user(db, normalized_name)
        return user.id, user.name

    return None, None


@router.post("", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)) -> EntryRead:
    _ensure_account_exists(db, payload.account_id)
    from_entity_id, from_entity_name = _resolve_entity_value(
        db,
        entity_id=payload.from_entity_id,
        entity_name=payload.from_entity,
        field_name="from",
    )
    to_entity_id, to_entity_name = _resolve_entity_value(
        db,
        entity_id=payload.to_entity_id,
        entity_name=payload.to_entity,
        field_name="to",
    )

    owner_user_id = payload.owner_user_id
    owner_name = payload.owner
    if owner_name is not None and normalize_user_name(owner_name) == "":
        owner_name = None
    if owner_user_id is None and owner_name is None:
        settings = get_settings()
        owner_user = ensure_current_user(db, settings.current_user_name)
        owner_user_id = owner_user.id
        owner_name = owner_user.name
    else:
        owner_user_id, owner_name = _resolve_user_value(
            db,
            user_id=owner_user_id,
            user_name=owner_name,
            field_name="owner",
        )

    entry = Entry(
        account_id=payload.account_id,
        kind=payload.kind,
        occurred_at=payload.occurred_at,
        name=payload.name,
        amount_minor=payload.amount_minor,
        currency_code=payload.currency_code.upper(),
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        owner_user_id=owner_user_id,
        from_entity=from_entity_name,
        to_entity=to_entity_name,
        owner=owner_name,
        markdown_body=payload.markdown_body,
        group_id="",
    )
    db.add(entry)
    assign_initial_group(db, entry)
    set_entry_tags(db, entry, payload.tags)

    db.commit()
    db.refresh(entry)
    db.refresh(entry, attribute_names=["tags"])
    return entry_to_schema(entry)


@router.get("", response_model=EntryListResponse)
def list_entries(
    db: Session = Depends(get_db),
    start_date: date | None = None,
    end_date: date | None = None,
    kind: EntryKind | None = None,
    tag: str | None = None,
    currency: str | None = None,
    source: str | None = None,
    account_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EntryListResponse:
    conditions = [Entry.is_deleted.is_(False)]

    if start_date is not None:
        conditions.append(Entry.occurred_at >= start_date)
    if end_date is not None:
        conditions.append(Entry.occurred_at <= end_date)
    if kind is not None:
        conditions.append(Entry.kind == kind)
    if currency is not None:
        conditions.append(Entry.currency_code == currency.upper())
    if account_id is not None:
        conditions.append(Entry.account_id == account_id)
    if source is not None:
        pattern = f"%{source}%"
        conditions.append(
            or_(
                Entry.name.ilike(pattern),
                Entry.from_entity.ilike(pattern),
                Entry.to_entity.ilike(pattern),
            )
        )

    stmt = (
        select(Entry)
        .where(*conditions)
        .options(selectinload(Entry.tags))
        .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
    )
    count_stmt = select(func.count(func.distinct(Entry.id))).where(*conditions)

    if tag:
        normalized = normalize_tag_name(tag)
        stmt = stmt.join(Entry.tags).where(Tag.name == normalized)
        count_stmt = count_stmt.select_from(Entry).join(Entry.tags).where(Tag.name == normalized, *conditions)

    total = int(db.scalar(count_stmt) or 0)
    entries = list(db.scalars(stmt.limit(limit).offset(offset)))

    return EntryListResponse(
        items=[entry_to_schema(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{entry_id}", response_model=EntryDetailRead)
def get_entry(entry_id: str, db: Session = Depends(get_db)) -> EntryDetailRead:
    entry = _get_entry_or_404(db, entry_id)

    links = sorted(
        [*entry.outgoing_links, *entry.incoming_links],
        key=lambda link: link.created_at,
    )
    return entry_to_detail_schema(entry, links)


@router.patch("/{entry_id}", response_model=EntryRead)
def update_entry(entry_id: str, payload: EntryUpdate, db: Session = Depends(get_db)) -> EntryRead:
    entry = _get_entry_or_404(db, entry_id)
    update_data = payload.model_dump(exclude_unset=True)

    tags = update_data.pop("tags", None)
    if "account_id" in update_data:
        _ensure_account_exists(db, update_data["account_id"])

    if "currency_code" in update_data and update_data["currency_code"] is not None:
        update_data["currency_code"] = update_data["currency_code"].upper()

    for field_name in ("from", "to"):
        id_field = f"{field_name}_entity_id"
        name_field = field_name
        if id_field in update_data or name_field in update_data:
            resolved_id, resolved_name = _resolve_entity_value(
                db,
                entity_id=update_data.pop(id_field, None),
                entity_name=update_data.pop(name_field, None),
                field_name=field_name,
            )
            update_data[id_field] = resolved_id
            update_data[name_field] = resolved_name

    if "owner_user_id" in update_data or "owner" in update_data:
        resolved_id, resolved_name = _resolve_user_value(
            db,
            user_id=update_data.pop("owner_user_id", None),
            user_name=update_data.pop("owner", None),
            field_name="owner",
        )
        update_data["owner_user_id"] = resolved_id
        update_data["owner"] = resolved_name

    for field, value in update_data.items():
        setattr(entry, field, value)

    if tags is not None:
        set_entry_tags(db, entry, tags)

    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.refresh(entry, attribute_names=["tags"])
    return entry_to_schema(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, db: Session = Depends(get_db)) -> None:
    entry = _get_entry_or_404(db, entry_id)
    soft_delete_entry(db, entry)
    recompute_entry_groups(db)
    db.commit()


@router.post("/{entry_id}/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED)
def create_link(entry_id: str, payload: LinkCreate, db: Session = Depends(get_db)) -> LinkRead:
    if entry_id == payload.target_entry_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot link entry to itself")

    source_entry = db.scalar(_entry_query().where(Entry.id == entry_id))
    if source_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source entry not found")

    target_entry = db.scalar(_entry_query().where(Entry.id == payload.target_entry_id))
    if target_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target entry not found")

    link = EntryLink(
        source_entry_id=entry_id,
        target_entry_id=payload.target_entry_id,
        link_type=payload.link_type,
        note=payload.note,
    )
    db.add(link)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Link already exists") from exc

    recompute_entry_groups(db)
    db.commit()
    db.refresh(link)
    return link_to_schema(link)
