from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.auth import RequestPrincipal, get_current_principal
from backend.database import get_db
from backend.enums_finance import EntryKind
from backend.models_finance import Entity, Entry, EntryGroup, Tag
from backend.schemas_finance import (
    EntryCreate,
    EntryDetailRead,
    EntryListResponse,
    EntryRead,
    EntryUpdate,
)
from backend.services.access_scope import (
    ensure_principal_can_assign_user,
    entry_owner_filter,
    get_account_for_principal_or_404,
    get_entry_for_principal_or_404,
    get_group_for_principal_or_404,
    get_user_for_principal_or_404,
)
from backend.services.entries import normalize_tag_name, set_entry_tags, soft_delete_entry
from backend.services.entities import ensure_entity_by_name, normalize_entity_name
from backend.services.groups import entry_group_options, group_tree_options, set_entry_direct_group
from backend.services.serializers import entry_to_detail_schema, entry_to_schema
from backend.services.users import ensure_user_by_name, normalize_user_name

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryListQueryParams(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    kind: EntryKind | None = None
    tag: str | None = None
    currency: str | None = None
    source: str | None = None
    account_id: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


def _entry_query(principal: RequestPrincipal):
    return select(Entry).where(
        Entry.is_deleted.is_(False),
        entry_owner_filter(principal),
    )


def _get_entry_or_404(
    db: Session,
    entry_id: str,
    principal: RequestPrincipal,
) -> Entry:
    return get_entry_for_principal_or_404(
        db,
        entry_id=entry_id,
        principal=principal,
        stmt=select(Entry).options(
            selectinload(Entry.tags),
            *entry_group_options(),
        ),
    )


def _get_group_tree_or_404(
    db: Session,
    group_id: str,
    principal: RequestPrincipal,
) -> EntryGroup:
    return get_group_for_principal_or_404(
        db,
        group_id=group_id,
        principal=principal,
        stmt=select(EntryGroup).options(*group_tree_options()),
    )


def _ensure_account_exists(
    db: Session,
    account_id: str | None,
    principal: RequestPrincipal,
) -> None:
    if account_id is None:
        return
    get_account_for_principal_or_404(db, account_id=account_id, principal=principal)


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
        entity = ensure_entity_by_name(db, normalized_name)
        return entity.id, entity.name

    return None, None


def _resolve_user_value(
    db: Session,
    *,
    user_id: str | None,
    user_name: str | None,
    field_name: str,
    principal: RequestPrincipal,
) -> tuple[str | None, str | None]:
    normalized_name = normalize_user_name(user_name) if user_name is not None else None
    if normalized_name == "":
        normalized_name = None

    if user_id:
        user = get_user_for_principal_or_404(db, user_id=user_id, principal=principal)
        if normalized_name is not None and user.name.lower() != normalized_name.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} user id and name do not match",
            )
        return user.id, user.name

    if normalized_name is not None:
        user = ensure_user_by_name(db, normalized_name)
        ensure_principal_can_assign_user(principal, user_id=user.id)
        return user.id, user.name

    return None, None


@router.post("", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: EntryCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> EntryRead:
    target_group = None
    if payload.direct_group_id is not None:
        target_group = _get_group_tree_or_404(db, payload.direct_group_id, principal)

    _ensure_account_exists(db, payload.account_id, principal)
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
        owner_user_id = principal.user_id
        owner_name = principal.user_name
    else:
        owner_user_id, owner_name = _resolve_user_value(
            db,
            user_id=owner_user_id,
            user_name=owner_name,
            field_name="owner",
            principal=principal,
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
    )
    db.add(entry)
    db.flush()
    set_entry_tags(db, entry, payload.tags)

    try:
        set_entry_direct_group(
            db,
            entry=entry,
            group=target_group,
            member_role=payload.direct_group_member_role,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return entry_to_schema(_get_entry_or_404(db, entry.id, principal))


@router.get("", response_model=EntryListResponse)
def list_entries(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
    filters: EntryListQueryParams = Depends(),
) -> EntryListResponse:
    conditions = [Entry.is_deleted.is_(False), entry_owner_filter(principal)]

    if filters.start_date is not None:
        conditions.append(Entry.occurred_at >= filters.start_date)
    if filters.end_date is not None:
        conditions.append(Entry.occurred_at <= filters.end_date)
    if filters.kind is not None:
        conditions.append(Entry.kind == filters.kind)
    if filters.currency is not None:
        conditions.append(Entry.currency_code == filters.currency.upper())
    if filters.account_id is not None:
        conditions.append(Entry.account_id == filters.account_id)
    if filters.source is not None:
        pattern = f"%{filters.source}%"
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
        .options(selectinload(Entry.tags), *entry_group_options())
        .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
    )
    count_stmt = select(func.count(func.distinct(Entry.id))).where(*conditions)

    if filters.tag:
        normalized = normalize_tag_name(filters.tag)
        stmt = stmt.join(Entry.tags).where(Tag.name == normalized)
        count_stmt = count_stmt.select_from(Entry).join(Entry.tags).where(Tag.name == normalized, *conditions)

    total = int(db.scalar(count_stmt) or 0)
    entries = list(db.scalars(stmt.limit(filters.limit).offset(filters.offset)))

    return EntryListResponse(
        items=[entry_to_schema(entry) for entry in entries],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/{entry_id}", response_model=EntryDetailRead)
def get_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> EntryDetailRead:
    entry = _get_entry_or_404(db, entry_id, principal)
    return entry_to_detail_schema(entry)


@router.patch("/{entry_id}", response_model=EntryRead)
def update_entry(
    entry_id: str,
    payload: EntryUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> EntryRead:
    entry = _get_entry_or_404(db, entry_id, principal)
    update_data = payload.model_dump(exclude_unset=True)

    tags = update_data.pop("tags", None)
    group_value = update_data.pop("direct_group_id", Ellipsis)
    role_value = update_data.pop("direct_group_member_role", Ellipsis)
    if "account_id" in update_data:
        _ensure_account_exists(db, update_data["account_id"], principal)

    if "currency_code" in update_data and update_data["currency_code"] is not None:
        update_data["currency_code"] = update_data["currency_code"].upper()

    for entity_field, field_name in (("from_entity", "from"), ("to_entity", "to")):
        id_field = f"{entity_field}_id"
        if id_field in update_data or entity_field in update_data:
            resolved_id, resolved_name = _resolve_entity_value(
                db,
                entity_id=update_data.pop(id_field, None),
                entity_name=update_data.pop(entity_field, None),
                field_name=field_name,
            )
            update_data[id_field] = resolved_id
            update_data[entity_field] = resolved_name

    if "owner_user_id" in update_data or "owner" in update_data:
        resolved_id, resolved_name = _resolve_user_value(
            db,
            user_id=update_data.pop("owner_user_id", None),
            user_name=update_data.pop("owner", None),
            field_name="owner",
            principal=principal,
        )
        update_data["owner_user_id"] = resolved_id
        update_data["owner"] = resolved_name

    for field, value in update_data.items():
        setattr(entry, field, value)

    if tags is not None:
        set_entry_tags(db, entry, tags)

    group_update_requested = group_value is not Ellipsis or role_value is not Ellipsis
    if group_update_requested:
        existing_membership = entry.group_membership
        target_group_id = (
            existing_membership.group_id if group_value is Ellipsis and existing_membership is not None else None
        ) if group_value is Ellipsis else group_value
        target_role = (
            existing_membership.member_role if role_value is Ellipsis and existing_membership is not None else None
        ) if role_value is Ellipsis else role_value
        if target_group_id is None:
            target_role = None

        target_group = None
        if target_group_id is not None:
            target_group = _get_group_tree_or_404(db, target_group_id, principal)

        try:
            set_entry_direct_group(
                db,
                entry=entry,
                group=target_group,
                member_role=target_role,
            )
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.add(entry)
    db.commit()
    return entry_to_schema(_get_entry_or_404(db, entry.id, principal))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    entry = _get_entry_or_404(db, entry_id, principal)
    soft_delete_entry(db, entry)
    db.commit()
