from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.database import get_session_maker
from backend.models_finance import User
from backend.services.taxonomy import (
    assign_single_term_by_name,
    create_term,
    ensure_taxonomy_by_key,
    get_single_term_name,
    get_single_term_name_map,
)


def _admin_user_id(db) -> str:
    owner_user_id = db.scalar(select(User.id).where(User.name == "admin"))
    assert isinstance(owner_user_id, str)
    return owner_user_id


def test_create_term_enforces_flat_uniqueness() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        owner_user_id = _admin_user_id(db)
        taxonomy = ensure_taxonomy_by_key(db, "tag_type", owner_user_id=owner_user_id)
        create_term(db, taxonomy=taxonomy, name="Food")
        db.commit()

        with pytest.raises(ValueError):
            create_term(db, taxonomy=taxonomy, name=" food ")
    finally:
        db.close()


def test_assign_single_term_name_map_round_trip() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        owner_user_id = _admin_user_id(db)
        assign_single_term_by_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=1,
            term_name="expense",
            owner_user_id=owner_user_id,
        )
        assign_single_term_by_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=2,
            term_name="income",
            owner_user_id=owner_user_id,
        )
        db.commit()

        assert get_single_term_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=1,
            owner_user_id=owner_user_id,
        ) == "expense"
        assert get_single_term_name_map(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_ids=[1, 2],
            owner_user_id=owner_user_id,
        ) == {"1": "expense", "2": "income"}
    finally:
        db.close()
