from __future__ import annotations


def normalize_entity_name(name: str) -> str:
    return " ".join(name.split()).strip()


def normalize_entity_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = " ".join(category.split()).strip().lower()
    return normalized or None


def normalize_tag_name(name: str) -> str:
    return name.strip().lower()


def normalize_currency_code(value: str) -> str:
    return " ".join(value.split()).strip().upper()


def normalize_currency_code_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_currency_code(value)
    return normalized or None
