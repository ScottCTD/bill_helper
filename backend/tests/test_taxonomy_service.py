from __future__ import annotations

import pytest

from backend.database import get_session_maker
from backend.services.taxonomy import (
    assign_single_term_by_name,
    create_term,
    ensure_taxonomy_by_key,
    get_single_term_name,
    get_single_term_name_map,
)


def test_create_term_enforces_flat_uniqueness() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        taxonomy = ensure_taxonomy_by_key(db, "tag_type")
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
        assign_single_term_by_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=1,
            term_name="expense",
        )
        assign_single_term_by_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=2,
            term_name="income",
        )
        db.commit()

        assert get_single_term_name(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_id=1,
        ) == "expense"
        assert get_single_term_name_map(
            db,
            taxonomy_key="tag_type",
            subject_type="tag",
            subject_ids=[1, 2],
        ) == {"1": "expense", "2": "income"}
    finally:
        db.close()
