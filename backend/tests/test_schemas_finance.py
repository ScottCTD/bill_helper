from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas_finance import TaxonomyTermCreate


def test_taxonomy_term_create_forbids_parent_term_field() -> None:
    with pytest.raises(ValidationError):
        TaxonomyTermCreate(name="food", parent_term_id="root")
