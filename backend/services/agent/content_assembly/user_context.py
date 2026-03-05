from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.models_finance import Account, User
from backend.services.runtime_settings import resolve_runtime_settings

MAX_ACCOUNT_MARKDOWN_CONTEXT_CHARS = 1_500
MAX_ACCOUNT_MARKDOWN_CONTEXT_LINES = 40
MAX_ACCOUNT_IMAGE_DATA_URL_CHARS = 120
MARKDOWN_IMAGE_DATA_URL_PATTERN = re.compile(r"!\[([^\]]*)\]\((data:image[^)]+)\)", re.IGNORECASE)


def _truncate_markdown_image_data_urls(markdown: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        alt = match.group(1)
        url = match.group(2)
        if len(url) <= MAX_ACCOUNT_IMAGE_DATA_URL_CHARS:
            return match.group(0)
        preview = f"{url[:MAX_ACCOUNT_IMAGE_DATA_URL_CHARS]}...(truncated)"
        return f"![{alt}]({preview})"

    return MARKDOWN_IMAGE_DATA_URL_PATTERN.sub(_replace, markdown)


def normalize_account_markdown_for_context(markdown: str | None) -> str | None:
    if markdown is None:
        return None
    normalized = markdown.strip()
    if not normalized:
        return None

    normalized = _truncate_markdown_image_data_urls(normalized)
    lines = normalized.splitlines()
    if len(lines) > MAX_ACCOUNT_MARKDOWN_CONTEXT_LINES:
        normalized = "\n".join(lines[:MAX_ACCOUNT_MARKDOWN_CONTEXT_LINES]).rstrip()
        normalized = f"{normalized}\n...(truncated)"

    if len(normalized) > MAX_ACCOUNT_MARKDOWN_CONTEXT_CHARS:
        normalized = normalized[:MAX_ACCOUNT_MARKDOWN_CONTEXT_CHARS].rstrip()
        normalized = f"{normalized}\n...(truncated)"
    return normalized


def build_current_user_context(db: Session) -> str:
    settings = resolve_runtime_settings(db)
    current_user_name = (settings.current_user_name or "").strip() or "(unknown)"
    accounts = list(
        db.scalars(
            select(Account)
            .join(User, User.id == Account.owner_user_id)
            .where(func.lower(User.name) == current_user_name.lower())
            .options(selectinload(Account.entity))
            .order_by(Account.created_at.asc())
        )
    )

    lines = [
        f"user_name: {current_user_name}",
        f"accounts_count: {len(accounts)}",
        "accounts:",
    ]
    if not accounts:
        lines.append("- (none)")
        return "\n".join(lines)

    max_accounts = 40
    for index, account in enumerate(accounts[:max_accounts], start=1):
        status = "active" if account.is_active else "inactive"
        lines.append(
            f"{index}. name={account.name}; currency={account.currency_code}; status={status}; "
            f"entity={account.entity.name if account.entity is not None else '-'}"
        )
        notes_markdown = normalize_account_markdown_for_context(account.markdown_body)
        if notes_markdown:
            lines.append("  notes_markdown:")
            lines.extend(f"    {line}" for line in notes_markdown.splitlines())
        else:
            lines.append("  notes_markdown: (none)")
    if len(accounts) > max_accounts:
        lines.append(f"- ... (+{len(accounts) - max_accounts} more)")
    return "\n".join(lines)

