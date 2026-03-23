from backend.services.agent.tool_call_display import build_tool_call_display


def test_rename_thread_display_uses_requested_title():
    display = build_tool_call_display("rename_thread", input_json={"title": "Budget Review"})

    assert display.label == 'Renamed thread to "Budget Review"'
    assert display.detail == "Budget Review"


def test_add_user_memory_display_uses_count():
    display = build_tool_call_display(
        "add_user_memory",
        input_json={"memory_items": ["Use YYYY-MM-DD dates", "Prefer CAD"]},
        output_json={"added_count": 2},
    )

    assert display.label == "Added 2 memory items"


def test_read_image_display_uses_image_count():
    display = build_tool_call_display(
        "read_image",
        input_json={"paths": ["/workspace/a.png", "/workspace/b.png"]},
        output_json={"image_count": 2},
    )

    assert display.label == "Loaded 2 images"


def test_terminal_display_summarizes_bh_command_without_flags():
    display = build_tool_call_display(
        "terminal",
        input_json={"command": "bh entries create --date 2026-03-20 --amount 12.34 --note lunch"},
    )

    assert display.label == "bh entries create"
    assert display.detail is None


def test_terminal_display_unwraps_shell_wrappers():
    display = build_tool_call_display(
        "terminal",
        input_json={"command": "zsh -lc 'bh proposals list --status pending --limit 10'"},
    )

    assert display.label == "bh proposals list"


def test_terminal_display_falls_back_for_unparseable_or_unknown_commands():
    malformed = build_tool_call_display("terminal", input_json={"command": "'"})
    unknown = build_tool_call_display("terminal", input_json={"command": "git status --short"})

    assert malformed.label == "Ran terminal command"
    assert unknown.label == "Ran terminal command"
