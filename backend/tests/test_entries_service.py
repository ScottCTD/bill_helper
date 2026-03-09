from __future__ import annotations

from datetime import date

import pytest

from backend.auth import RequestPrincipal
from backend.database import get_session_maker
from backend.enums_finance import EntryKind, GroupType
from backend.models_finance import Account, Entity, EntryGroup, User
from backend.services.crud_policy import PolicyViolation
from backend.services.entries import (
    EntityRef,
    UserRefPatch,
    UserRef,
    EntryCreateCommand,
    EntryUpdateCommand,
    create_entry_from_command,
    update_entry_from_command,
)


def _create_user(db, name: str) -> User:
    user = User(name=name)
    db.add(user)
    db.flush()
    return user


def _create_account(db, *, name: str, owner_user_id: str) -> Account:
    entity = Entity(name=name)
    db.add(entity)
    db.flush()

    account = Account(
        id=entity.id,
        owner_user_id=owner_user_id,
        currency_code="USD",
        is_active=True,
    )
    db.add(account)
    db.flush()
    return account


def _create_group(db, *, name: str, owner_user_id: str) -> EntryGroup:
    group = EntryGroup(
        owner_user_id=owner_user_id,
        name=name,
        group_type=GroupType.BUNDLE,
    )
    db.add(group)
    db.flush()
    return group


def test_create_entry_from_command_assigns_tags_and_direct_group() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        admin = _create_user(db, "admin")
        account = _create_account(db, name="Checking", owner_user_id=admin.id)
        group = _create_group(db, name="Bills", owner_user_id=admin.id)
        principal = RequestPrincipal(user_id=admin.id, user_name=admin.name)

        entry = create_entry_from_command(
            db,
            command=EntryCreateCommand(
                account_id=account.id,
                kind=EntryKind.EXPENSE,
                occurred_at=date(2026, 1, 1),
                name="Hydro Bill",
                amount_minor=1234,
                currency_code="usd",
                from_ref=EntityRef(name="Checking"),
                owner_ref=UserRef(user_id=admin.id),
                tags=["Food"],
                direct_group_id=group.id,
            ),
            principal=principal,
        )
        db.commit()

        assert entry.id is not None
        assert entry.owner_user_id == admin.id
        assert entry.from_entity_id == account.id
        assert entry.from_entity == "Checking"
        assert [tag.name for tag in entry.tags] == ["food"]
        assert entry.group_membership is not None
        assert entry.group_membership.entry_id == entry.id
        assert entry.group_membership.group_id == group.id
    finally:
        db.close()


def test_update_entry_from_command_uses_policy_violation_for_cross_principal_owner_name() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        admin = _create_user(db, "admin")
        alice = _create_user(db, "alice")
        account = _create_account(db, name="Alice Checking", owner_user_id=alice.id)
        principal = RequestPrincipal(user_id=alice.id, user_name=alice.name)

        entry = create_entry_from_command(
            db,
            command=EntryCreateCommand(
                account_id=account.id,
                kind=EntryKind.EXPENSE,
                occurred_at=date(2026, 1, 2),
                name="Coffee",
                amount_minor=600,
                currency_code="USD",
                tags=["food"],
            ),
            principal=principal,
        )
        db.commit()

        with pytest.raises(PolicyViolation) as exc_info:
            update_entry_from_command(
                db,
                entry_id=entry.id,
                command=EntryUpdateCommand(owner_ref=UserRefPatch(name=admin.name)),
                principal=principal,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Cannot assign resources to a different user."
    finally:
        db.close()
