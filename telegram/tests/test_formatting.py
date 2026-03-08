from __future__ import annotations

from telegram.formatting import chunk_telegram_html, format_status_html, render_telegram_reply_chunks, simplify_markdown_for_telegram


def test_simplify_markdown_for_telegram_strips_heavy_markdown():
    text = "## Summary\n**Done**\n[Receipt](https://example.com/receipt)"
    assert simplify_markdown_for_telegram(text) == "Summary\nDone\nReceipt (https://example.com/receipt)"


def test_render_telegram_reply_chunks_escapes_html_sensitive_content():
    chunks = render_telegram_reply_chunks("A & B < C > D")
    assert chunks == ["A &amp; B &lt; C &gt; D"]


def test_chunk_telegram_html_prefers_safe_boundaries_and_preserves_entities():
    chunks = chunk_telegram_html("One &amp; two\n\nThree &amp; four", max_chars=18)
    assert chunks == ["One &amp; two", "Three &amp; four"]


def test_format_status_html_wraps_bold_title_and_escapes_body():
    rendered = format_status_html("Working <now>", "A & B")
    assert rendered == "<b>Working &lt;now&gt;</b>\nA &amp; B"