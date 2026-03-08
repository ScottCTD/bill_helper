from __future__ import annotations

from telegram.state import ChatStateStore


def test_chat_state_persists_thread_and_run_across_reloads(tmp_path):
    store = ChatStateStore(tmp_path / "chat_state.json")

    store.set_active_thread(123, "thread-1")
    store.set_active_run(123, "run-1")

    reloaded = ChatStateStore(tmp_path / "chat_state.json")
    state = reloaded.get(123)

    assert state is not None
    assert state.active_thread_id == "thread-1"
    assert state.active_run_id == "run-1"


def test_switching_threads_clears_active_run_and_clear_chat_removes_state(tmp_path):
    store = ChatStateStore(tmp_path / "chat_state.json")

    store.set_active_thread(123, "thread-1")
    store.set_active_run(123, "run-1")
    updated = store.set_active_thread(123, "thread-2")

    assert updated.active_thread_id == "thread-2"
    assert updated.active_run_id is None

    store.clear_chat(123)

    assert store.get(123) is None