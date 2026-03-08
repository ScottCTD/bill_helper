from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas_finance import RuntimeSettingsUpdate, TaxonomyTermCreate


def test_runtime_settings_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettingsUpdate(current_user_name="alice")


def test_runtime_settings_update_normalizes_currency_and_agent_model() -> None:
    payload = RuntimeSettingsUpdate(
        default_currency_code="cad",
        dashboard_currency_code="usd",
        agent_model="  openai/gpt-4.1-mini  ",
        agent_bulk_max_concurrent_threads=6,
    )
    assert payload.default_currency_code == "CAD"
    assert payload.dashboard_currency_code == "USD"
    assert payload.agent_model == "openai/gpt-4.1-mini"
    assert payload.agent_bulk_max_concurrent_threads == 6


def test_runtime_settings_update_normalizes_user_memory_items() -> None:
    payload = RuntimeSettingsUpdate(
        user_memory=[" Prefers terse answers. ", "- Works in CAD.", "works in cad."],
    )
    assert payload.user_memory == ["Prefers terse answers.", "Works in CAD."]


def test_runtime_settings_update_rejects_string_user_memory() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettingsUpdate(user_memory="Prefers terse answers.")


def test_taxonomy_term_create_forbids_parent_term_field() -> None:
    with pytest.raises(ValidationError):
        TaxonomyTermCreate(name="food", parent_term_id="root")
