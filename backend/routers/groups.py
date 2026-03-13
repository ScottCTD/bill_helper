# CALLING SPEC:
# - Purpose: translate HTTP requests and responses for `groups` routes.
# - Inputs: callers that import `backend/routers/groups.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for `groups`.
# - Side effects: FastAPI routing and HTTP error translation.
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.auth.dependencies import get_current_principal
from backend.contracts_groups import (
    ChildGroupMemberTarget,
    EntryGroupMemberTarget,
    GroupCreateCommand,
    GroupMemberCreateCommand,
    GroupPatch,
)
from backend.database import get_db
from backend.models_finance import EntryGroup
from backend.schemas_finance import (
    GroupCreate,
    GroupGraphRead,
    GroupMemberCreate,
    GroupSummaryRead,
    GroupUpdate,
)
from backend.services.crud_policy import PolicyViolation
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
    update_group as update_group_service,
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
    principal: RequestPrincipal = Depends(get_current_principal),
) -> GroupSummaryRead:
    group = create_group_service(
        db,
        command=GroupCreateCommand.model_validate(payload.model_dump()),
        owner_user_id=principal.user_id,
    )

    db.commit()
    return build_group_summary(group)


@router.get("", response_model=list[GroupSummaryRead])
def list_group_summaries(
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
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
    principal: RequestPrincipal = Depends(get_current_principal),
) -> GroupGraphRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    return build_group_graph(group)


@router.patch("/{group_id}", response_model=GroupSummaryRead)
def update_group(
    group_id: str,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> GroupSummaryRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    updated_group = update_group_service(
        db,
        group=group,
        patch=GroupPatch.model_validate(payload.model_dump(exclude_unset=True)),
    )

    db.commit()
    return build_group_summary(updated_group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    delete_group_service(db, group=group)
    db.commit()


@router.post("/{group_id}/members", response_model=GroupGraphRead, status_code=status.HTTP_201_CREATED)
def add_group_member(
    group_id: str,
    payload: GroupMemberCreate,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> GroupGraphRead:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    command = _group_member_command_for_principal(db, payload=payload, principal=principal)

    try:
        add_group_member_service(
            db,
            group=group,
            command=command,
        )
    except IntegrityError as exc:
        db.rollback()
        raise PolicyViolation.conflict("Group membership already exists.") from exc

    db.commit()
    updated_group = load_group_tree(db, group_id)
    if updated_group is None:  # pragma: no cover - post-commit invariant
        raise RuntimeError("Failed to load group after membership commit.")
    return build_group_graph(updated_group)


@router.delete("/{group_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group_member(
    group_id: str,
    membership_id: str,
    db: Session = Depends(get_db),
    principal: RequestPrincipal = Depends(get_current_principal),
) -> None:
    group = _get_group_tree_or_404(db, group_id=group_id, principal=principal)
    remove_group_member_service(db, group=group, membership_id=membership_id)
    db.commit()


def _group_member_command_for_principal(
    db: Session,
    *,
    payload: GroupMemberCreate,
    principal: RequestPrincipal,
) -> GroupMemberCreateCommand:
    if payload.target.target_type == "entry":
        entry = get_entry_for_principal_or_404(db, entry_id=payload.target.entry_id, principal=principal)
        return GroupMemberCreateCommand(
            target=EntryGroupMemberTarget(entry_id=entry.id),
            member_role=payload.member_role,
        )

    child_group = _get_group_tree_or_404(db, group_id=payload.target.group_id, principal=principal)
    return GroupMemberCreateCommand(
        target=ChildGroupMemberTarget(group_id=child_group.id),
        member_role=payload.member_role,
    )
