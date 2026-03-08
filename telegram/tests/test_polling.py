from __future__ import annotations

from telegram.commands import PTB_ALLOWED_UPDATES
from telegram.polling import run_polling


class FakeApplication:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run_polling(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_run_polling_uses_ptb_allowed_message_updates():
    application = FakeApplication()

    run_polling(application=application, drop_pending_updates=True)

    assert application.calls == [{"allowed_updates": PTB_ALLOWED_UPDATES, "drop_pending_updates": True}]