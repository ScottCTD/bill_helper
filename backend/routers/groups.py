from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_or_create_current_principal
from backend.database import get_db
from backend.models_finance import EntryGroup
from backend.schemas_finance import (
    GroupCreate,
    GroupGraphRead,
    GroupMemberCreate,
    GroupSummaryRead,
    GroupUpdate,
)
from backend.services.access_scope import (
    get_entry_for_principal_or_404,
    get_group_for_principal_or_404,
    group_owner_filter,
)
from backend.services.groups import (
    add_group_member as add_group_member_service,
    build_group_graph,
    build_group_summary,
    create_group as create_group_service,
    delete_group as delete_group_service,
    group_tree_options,
    load_group_tree,
    remove_group_member as remove_group_member_service,
    rename_group,
)

router = APIRouter(prefix="/groups", tags=["groups"])


def _get_group_tree_or_404(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
) -> EntryGroup:
    return get_group_for_principal_or_404(
        db,
        group_id=group_id,
        principal=principal,
        stmt=select(EntryGroup).options(*group_tree_options()),
    )


@router.post("", response_model=GroupSummaryRead, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> GroupSummaryRead:
    try:
        group = create_group_service(
            db,
            name=payload.name,
            group_type=payload.group_type,
            owner_user_id=principal.user_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return build_group_summary(group)


@router.get("", response_model=list[GroupSummaryRead])
def list_group_summaries(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> list[GroupSummaryRead]:
    groups = list(
        db.scalars(
            select(EntryGroup)
            .where(group_owner_filter(principal))
            .options(*group_tree_options())
        )
    )
    summaries = [build_group_summary(group) for group in groups]
    return sorted(
        summaries,
        key=lambda summary: (
            summary.last_occurred_at is None,
            summary.last_occurred_at or summary.name,
            summary.name.lower(),
            summary.id,
        ),
        reverse=True,
    )


@router.get("/{group_id}", response_model=GroupGraphRead)
def get_group_graph(
    group_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> GroupGraphRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    return build_group_graph(group)


@router.patch("/{group_id}", response_model=GroupSummaryRead)
def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> GroupSummaryRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    if payload.name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No group fields were provided.")

    try:
        updated_group = rename_group(db, group=group, name=payload.name)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return build_group_summary(updated_group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> None:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    try:
        delete_group_service(db, group=group)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()


@router.post("/{group_id}/members", response_model=GroupGraphRead, status_code=status.HTTP_201_CREATED)
def add_group_member(
    group_id: str,
    payload: GroupMemberCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> GroupGraphRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)

    entry = None
    child_group = None
    if payload.entry_id is not None:
        entry = get_entry_for_principal_or_404(db, entry_id=payload.entry_id, principal=principal)
    if payload.child_group_id is not None:
        child_group = _get_group_tree_or_404(db, group_id=payload.child_group_id, principal=principal)

    try:
        add_group_member_service(
            db,
            group=group,
            entry=entry,
            child_group=child_group,
            member_role=payload.member_role,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group membership already exists.") from exc

    db.commit()
    updated_group = load_group_tree(db, group_id)
    if updated_group is None:  # pragma: no cover - post-commit invariant
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return build_group_graph(updated_group)


@router.delete("/{group_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_member(
    group_id: str,
    membership_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_or_create_current_principal),
) -> None:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    try:
        remove_group_member_service(db, group=group, membership_id=membership_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
