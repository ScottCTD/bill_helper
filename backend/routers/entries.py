from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal
from backend.database import get_db
from backend.enums_finance import EntryKind
from backend.models_finance import Entry, Tag
from backend.schemas_finance import (
    EntryCreate,
    EntryDetailRead,
    EntryListResponse,
    EntryRead,
    EntryUpdate,
)
from backend.services.access_scope import (
    entry_owner_filter,
    get_entry_for_principal_or_404,
)
from backend.services.entries import (
    EntityRef,
    EntityRefPatch,
    EntryCreateCommand,
    EntryUpdateCommand,
    UserRef,
    UserRefPatch,
    create_entry_from_command,
    soft_delete_entry,
    update_entry_from_command,
)
from backend.services.filter_groups import (
    entry_matches_filter_group,
    get_filter_group_definition,
    list_account_entity_ids_for_principal,
)
from backend.services.groups import entry_group_options
from backend.services.serializers import entry_to_detail_schema, entry_to_schema
from backend.validation.finance_names import normalize_tag_name

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryListQueryParams(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    kind: EntryKind | None = None
    tag: str | None = None
    currency: str | None = None
    source: str | None = None
    account_id: str | None = None
    filter_group_id: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


def _entity_ref_or_none(
    *,
    entity_id: str | None,
    entity_name: str | None,
) -> EntityRef | None:
    if entity_id is None and entity_name is None:
        return None
    return EntityRef(entity_id=entity_id, name=entity_name)


def _entity_ref_patch_or_none(
    *,
    entity_id: str | None,
    entity_name: str | None,
    fields_set: set[str],
    id_field: str,
    name_field: str,
) -> EntityRefPatch | None:
    if id_field not in fields_set and name_field not in fields_set:
        return None
    return EntityRefPatch(entity_id=entity_id, name=entity_name)


def _user_ref_or_none(*, user_id: str | None, user_name: str | None) -> UserRef | None:
    if user_id is None and user_name is None:
        return None
    return UserRef(user_id=user_id, name=user_name)


def _user_ref_patch_or_none(
    *,
    user_id: str | None,
    user_name: str | None,
    fields_set: set[str],
) -> UserRefPatch | None:
    if "owner_user_id" not in fields_set and "owner" not in fields_set:
        return None
    return UserRefPatch(user_id=user_id, name=user_name)


def _entry_create_command_from_request(payload: EntryCreate) -> EntryCreateCommand:
    return EntryCreateCommand(
        account_id=payload.account_id,
        kind=payload.kind,
        occurred_at=payload.occurred_at,
        name=payload.name,
        amount_minor=payload.amount_minor,
        currency_code=payload.currency_code,
        from_ref=_entity_ref_or_none(
            entity_id=payload.from_entity_id,
            entity_name=payload.from_entity,
        ),
        to_ref=_entity_ref_or_none(
            entity_id=payload.to_entity_id,
            entity_name=payload.to_entity,
        ),
        owner_ref=_user_ref_or_none(
            user_id=payload.owner_user_id,
            user_name=payload.owner,
        ),
        markdown_body=payload.markdown_body,
        tags=payload.tags,
        direct_group_id=payload.direct_group_id,
        direct_group_member_role=payload.direct_group_member_role,
    )


def _entry_update_command_from_request(payload: EntryUpdate) -> EntryUpdateCommand:
    fields_set = set(payload.model_fields_set)
    command_payload = payload.model_dump(
        exclude_unset=True,
        exclude={
            "from_entity_id",
            "from_entity",
            "to_entity_id",
            "to_entity",
            "owner_user_id",
            "owner",
        },
    )
    from_ref = _entity_ref_patch_or_none(
        entity_id=payload.from_entity_id,
        entity_name=payload.from_entity,
        fields_set=fields_set,
        id_field="from_entity_id",
        name_field="from_entity",
    )
    if from_ref is not None:
        command_payload["from_ref"] = from_ref
    to_ref = _entity_ref_patch_or_none(
        entity_id=payload.to_entity_id,
        entity_name=payload.to_entity,
        fields_set=fields_set,
        id_field="to_entity_id",
        name_field="to_entity",
    )
    if to_ref is not None:
        command_payload["to_ref"] = to_ref
    owner_ref = _user_ref_patch_or_none(
        user_id=payload.owner_user_id,
        user_name=payload.owner,
        fields_set=fields_set,
    )
    if owner_ref is not None:
        command_payload["owner_ref"] = owner_ref
    return EntryUpdateCommand.model_validate(command_payload)


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


@router.post("", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: EntryCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> EntryRead:
    entry = create_entry_from_command(
        db,
        command=_entry_create_command_from_request(payload),
        principal=principal,
    )

    db.commit()
    return entry_to_schema(_get_entry_or_404(db, entry.id, principal))


@router.get("", response_model=EntryListResponse)
def list_entries(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
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

    if filters.filter_group_id is not None:
        filter_group = get_filter_group_definition(
            db,
            filter_group_id=filters.filter_group_id,
            principal=principal,
        )
        account_entity_ids = list_account_entity_ids_for_principal(
            db,
            principal=principal,
        )
        matching_entries = [
            entry
            for entry in db.scalars(stmt)
            if entry_matches_filter_group(
                entry,
                filter_group=filter_group,
                account_entity_ids=account_entity_ids,
            )
        ]
        total = len(matching_entries)
        entries = matching_entries[filters.offset : filters.offset + filters.limit]
    else:
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
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> EntryDetailRead:
    entry = _get_entry_or_404(db, entry_id, principal)
    return entry_to_detail_schema(entry)


@router.patch("/{entry_id}", response_model=EntryRead)
def update_entry(
    entry_id: str,
    payload: EntryUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> EntryRead:
    entry = update_entry_from_command(
        db,
        entry_id=entry_id,
        command=_entry_update_command_from_request(payload),
        principal=principal,
    )

    db.commit()
    return entry_to_schema(_get_entry_or_404(db, entry.id, principal))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> None:
    entry = _get_entry_or_404(db, entry_id, principal)
    soft_delete_entry(db, entry)
    db.commit()
