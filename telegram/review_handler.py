from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import escape

from backend.enums_agent import AgentChangeStatus
from backend.schemas_agent import AgentChangeItemRead, AgentRunRead
from telegram.bill_helper_api import BillHelperApiClient, BillHelperApiError
from telegram.ptb import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.state import ChatStateStore

_CHANGE_TYPE_META = {
    "create_entry": ("➕", "Create entry"),
    "update_entry": ("✏️", "Update entry"),
    "delete_entry": ("🗑️", "Delete entry"),
    "create_account": ("🏦", "Create account"),
    "update_account": ("🏦", "Update account"),
    "delete_account": ("🏦", "Delete account"),
    "create_snapshot": ("📸", "Create snapshot"),
    "delete_snapshot": ("📸", "Delete snapshot"),
    "create_group": ("🧩", "Create group"),
    "update_group": ("🧩", "Update group"),
    "delete_group": ("🧩", "Delete group"),
    "create_group_member": ("🔗", "Create group member"),
    "delete_group_member": ("🔗", "Delete group member"),
    "create_tag": ("🏷️", "Create tag"),
    "update_tag": ("🏷️", "Update tag"),
    "delete_tag": ("🏷️", "Delete tag"),
    "create_entity": ("👤", "Create entity"),
    "update_entity": ("👤", "Update entity"),
    "delete_entity": ("👤", "Delete entity"),
}

_STATUS_LABELS = {
    AgentChangeStatus.PENDING_REVIEW: "Pending review",
    AgentChangeStatus.APPROVED: "Approved",
    AgentChangeStatus.REJECTED: "Rejected",
    AgentChangeStatus.APPLIED: "Applied",
    AgentChangeStatus.APPLY_FAILED: "Apply failed",
}


@dataclass(slots=True)
class TelegramReviewHandler:
    api_client: BillHelperApiClient
    state_store: ChatStateStore

    async def render_change_items(
        self,
        *,
        bot: object,
        chat_id: int,
        run: AgentRunRead,
        message_thread_id: int | None = None,
    ) -> list[object]:
        pending_items = [item for item in run.change_items if item.status == AgentChangeStatus.PENDING_REVIEW]
        if not pending_items:
            self.state_store.clear_review_run(chat_id, run.id)
            return []

        sent_messages: list[object] = []
        for item in pending_items:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=format_change_item_html(item),
                parse_mode="HTML",
                reply_markup=self._item_keyboard(item.id),
                message_thread_id=message_thread_id,
            )
            sent_messages.append(sent)
            self.state_store.bind_review_item_message(
                chat_id,
                run_id=run.id,
                item_id=item.id,
                message_id=sent.message_id,
            )

        if len(pending_items) > 1:
            summary = await bot.send_message(
                chat_id=chat_id,
                text=f"📋 <b>{len(pending_items)} changes proposed</b>\nApprove or reject each item above, or review all at once.",
                parse_mode="HTML",
                reply_markup=self._batch_keyboard(run.id),
                message_thread_id=message_thread_id,
            )
            sent_messages.append(summary)
            self.state_store.bind_review_summary_message(chat_id, run_id=run.id, message_id=summary.message_id)
        return sent_messages

    async def handle_callback(self, update, context) -> None:
        del context
        query = update.callback_query
        if query is None or not query.data:
            return
        parts = query.data.split(":", 2)
        if len(parts) != 3 or parts[0] != "ci":
            return
        action = parts[1]
        target_id = parts[2]
        await query.answer()

        if query.message is None or query.message.chat is None:
            return
        chat_id = query.message.chat.id
        bot = query.get_bot()
        if action in {"approve", "reject"}:
            await self._handle_single_item_action(
                bot=bot,
                chat_id=chat_id,
                item_id=target_id,
                action=action,
            )
            return
        if action in {"approve_all", "reject_all"}:
            await self._handle_batch_action(
                bot=bot,
                chat_id=chat_id,
                run_id=target_id,
                action=action,
            )

    async def _handle_single_item_action(
        self,
        *,
        bot: object,
        chat_id: int,
        item_id: str,
        action: str,
    ) -> None:
        binding = self.state_store.get_review_run_for_item(chat_id, item_id)
        if binding is None:
            return
        run_id, review_run = binding
        try:
            item = await asyncio.to_thread(
                self.api_client.approve_change_item if action == "approve" else self.api_client.reject_change_item,
                item_id,
            )
        except BillHelperApiError as exc:
            if exc.status_code != 409:
                raise
            run = await asyncio.to_thread(self.api_client.get_run, run_id)
            item = _find_change_item(run, item_id)
            if item is None:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=review_run.item_message_ids[item_id],
                    reply_markup=None,
                )
                return
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=review_run.item_message_ids[item_id],
            text=format_change_item_html(item, include_status=True),
            parse_mode="HTML",
        )
        await self._refresh_summary(bot=bot, chat_id=chat_id, run_id=run_id)

    async def _handle_batch_action(
        self,
        *,
        bot: object,
        chat_id: int,
        run_id: str,
        action: str,
    ) -> None:
        review_run = self.state_store.get_review_run(chat_id, run_id)
        if review_run is None:
            return
        run = await asyncio.to_thread(self.api_client.get_run, run_id)
        pending_items = [item for item in run.change_items if item.status == AgentChangeStatus.PENDING_REVIEW]
        for item in pending_items:
            try:
                updated = await asyncio.to_thread(
                    self.api_client.approve_change_item if action == "approve_all" else self.api_client.reject_change_item,
                    item.id,
                )
            except BillHelperApiError as exc:
                if exc.status_code != 409:
                    raise
                refreshed_run = await asyncio.to_thread(self.api_client.get_run, run_id)
                updated = _find_change_item(refreshed_run, item.id) or item
            message_id = review_run.item_message_ids.get(item.id)
            if message_id is None:
                continue
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=format_change_item_html(updated, include_status=True),
                parse_mode="HTML",
            )
        await self._refresh_summary(bot=bot, chat_id=chat_id, run_id=run_id)

    async def _refresh_summary(self, *, bot: object, chat_id: int, run_id: str) -> None:
        review_run = self.state_store.get_review_run(chat_id, run_id)
        if review_run is None or review_run.summary_message_id is None:
            return
        run = await asyncio.to_thread(self.api_client.get_run, run_id)
        counts = {status: 0 for status in AgentChangeStatus}
        for item in run.change_items:
            counts[item.status] = counts.get(item.status, 0) + 1
        pending_count = counts.get(AgentChangeStatus.PENDING_REVIEW, 0)
        if pending_count > 0:
            text = (
                f"📋 <b>{pending_count} changes still pending</b>\n"
                "Approve or reject each item above, or review all remaining changes."
            )
            reply_markup = self._batch_keyboard(run_id)
        else:
            applied_count = counts.get(AgentChangeStatus.APPLIED, 0)
            rejected_count = counts.get(AgentChangeStatus.REJECTED, 0)
            text = (
                f"📋 <b>Review complete</b>\n"
                f"Applied: {applied_count} | Rejected: {rejected_count}"
            )
            reply_markup = None
            self.state_store.clear_review_run(chat_id, run_id)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=review_run.summary_message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    def _item_keyboard(self, item_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Approve", callback_data=f"ci:approve:{item_id}"),
                InlineKeyboardButton("Reject", callback_data=f"ci:reject:{item_id}"),
            ]]
        )

    def _batch_keyboard(self, run_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("Approve all", callback_data=f"ci:approve_all:{run_id}"),
                InlineKeyboardButton("Reject all", callback_data=f"ci:reject_all:{run_id}"),
            ]]
        )


def format_change_item_html(item: AgentChangeItemRead, *, include_status: bool = False) -> str:
    emoji, label = _CHANGE_TYPE_META.get(item.change_type.value, ("🧾", item.change_type.value.replace("_", " ").title()))
    payload = item.payload_json if isinstance(item.payload_json, dict) else {}
    summary = _extract_summary(payload)
    amount = _extract_amount(payload)
    tags = _extract_tags(payload) if item.change_type.value == "create_entry" else []
    rationale = escape((item.rationale_text or "").strip() or "No rationale provided.", quote=False)
    lines = [f"{emoji} <b>{escape(label, quote=False)}</b>"]
    if summary:
        detail = f"<b>{escape(summary, quote=False)}</b>"
        if amount:
            detail = f"{detail} — {escape(amount, quote=False)}"
        lines.append(detail)
    elif amount:
        lines.append(escape(amount, quote=False))
    if tags:
        rendered_tags = ", ".join(escape(tag, quote=False) for tag in tags)
        lines.append(f"Tags: <b>{rendered_tags}</b>")
    lines.append(rationale)
    if include_status:
        lines.append(f"Status: <b>{escape(_STATUS_LABELS[item.status], quote=False)}</b>")
    return "\n".join(lines)


def _extract_summary(payload: dict[str, object]) -> str | None:
    for key in (
        "name",
        "title",
        "account_name",
        "entity_name",
        "group_name",
        "tag_name",
        "snapshot_at",
        "normalized_name",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in ("entry", "account", "entity", "group", "tag"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_summary = _extract_summary(nested)
            if nested_summary:
                return nested_summary
    return None


def _extract_amount(payload: dict[str, object]) -> str | None:
    amount = payload.get("amount_minor")
    currency = payload.get("currency_code")
    if isinstance(amount, int) and isinstance(currency, str) and currency.strip():
        return f"{currency.upper()} {amount / 100:,.2f}"
    for key in ("entry", "account", "snapshot"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_amount = _extract_amount(nested)
            if nested_amount:
                return nested_amount
    return None


def _extract_tags(payload: dict[str, object]) -> list[str]:
    raw_tags = payload.get("tags")
    if isinstance(raw_tags, list):
        normalized_tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if normalized_tags:
            return normalized_tags
    entry_payload = payload.get("entry")
    if isinstance(entry_payload, dict):
        return _extract_tags(entry_payload)
    return []


def _find_change_item(run: AgentRunRead, item_id: str) -> AgentChangeItemRead | None:
    return next((item for item in run.change_items if item.id == item_id), None)
