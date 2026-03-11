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


def test_topics_and_review_bindings_persist_across_reloads(tmp_path):
    store = ChatStateStore(tmp_path / "chat_state.json")

    store.set_topics_enabled(123, True)
    store.bind_topic_thread(123, message_thread_id=77, thread_id="thread-7")
    store.bind_review_item_message(123, run_id="run-1", item_id="item-1", message_id=1001)
    store.bind_review_summary_message(123, run_id="run-1", message_id=1002)

    reloaded = ChatStateStore(tmp_path / "chat_state.json")
    state = reloaded.get(123)

    assert state is not None
    assert state.topics_enabled is True
    assert reloaded.get_thread_for_topic(123, 77) == "thread-7"
    assert reloaded.get_topic_for_thread(123, "thread-7") == 77
    review_run = reloaded.get_review_run(123, "run-1")
    assert review_run is not None
    assert review_run.item_message_ids == {"item-1": 1001}
    assert review_run.summary_message_id == 1002
