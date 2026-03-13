# Telegram Transport UX Improvements

> **Status:** Completed on 2026-03-11
> **Scope:** `telegram/`, chart generation module, no backend changes needed for P0–P1
> **Result:** Telegram now streams replies from SSE, surfaces inline review actions, renders dashboard charts, registers command metadata, and can bind new threads to Telegram forum topics when enabled.

## Context

The current Telegram transport is a working MVP: allowlist-gated private chat bot that forwards messages to the backend agent, polls for completion, and delivers plain-text replies. It leaves significant Telegram platform capabilities unused.

**Current pain points:**

1. **No streaming** — user stares at a silent chat for up to 2 minutes while the agent works. The backend already exposes `POST /agent/threads/{id}/messages/stream` (SSE with `text_delta`, `reasoning_delta`, `run_event`), but the Telegram transport uses `GET /agent/runs/{id}` polling instead.
2. **No thread visualization** — all messages live in a flat private chat. Users must remember which thread is active and use `/threads` + `/use` to switch.
3. **No approval workflow** — the agent is review-gated (change items sit in `PENDING_REVIEW`), but the Telegram bot has no way to present or act on them. Users must switch to the web UI.
4. **No dashboard access** — the backend serves rich dashboard data (`/dashboard?month=YYYY-MM`) but the Telegram bot can't show any of it.
5. **Missing polish** — no `typing` indicator during processing, only `["message"]` updates registered, no command auto-complete menu.

**Reference docs:** `docs/agent_billing_assistant.md` (agent behavior, tools, system prompt), `backend/docs/agent_subsystem.md` (SSE events, runtime loop, review workflow).

---

## 1. Message Streaming via Progressive `editMessageText`

### What Telegram supports

Telegram has no native server-push streaming, but the standard pattern is:

1. **Send** an initial placeholder message (`"⏳ Working on it…"`)
2. **Edit** that message repeatedly via `editMessageText` as content arrives
3. Telegram clients re-render the message in-place — the user sees text appearing progressively

Constraints:
- `editMessageText` has rate limits (~30 calls/minute per chat for bots, though undocumented)
- Max message length 4096 chars (same as `sendMessage`)
- If the edited text is identical to the current text, the API returns `Bad Request: message is not modified` — must guard against this

### What the backend provides

`POST /agent/threads/{thread_id}/messages/stream` returns SSE events:

| Event type | Payload | Meaning |
|---|---|---|
| `text_delta` | `{ run_id, delta }` | Incremental assistant text token |
| `reasoning_delta` | `{ run_id, delta }` | Incremental model reasoning token |
| `run_event` | `{ run_id, event: { event_type, message, ... }, tool_call? }` | Lifecycle events — see below |

**`run_event` event types** (`AgentRunEventType` enum):
- `run_started`, `run_completed`, `run_failed` — lifecycle
- `reasoning_update` — **from the `send_intermediate_update` agent tool** (user-visible progress note, up to 400 chars, supports inline markdown)
- `tool_call_queued`, `tool_call_started`, `tool_call_completed`, `tool_call_failed`, `tool_call_cancelled` — tool lifecycle

**Key insight:** The agent has a `send_intermediate_update` tool that it calls to share user-facing progress notes (e.g. "I'll search your recent transactions…"). These arrive as `run_event` with `event_type: "reasoning_update"` and `source: "tool_call"`. This is the primary mechanism for showing the user what the agent is doing between tool calls.

### Decisions

| Question | Decision |
|---|---|
| What to stream to the user? | `text_delta` content (the actual reply being written) + `reasoning_update` events from `send_intermediate_update` (agent progress notes) |
| Show reasoning tokens? | **No** — `reasoning_delta` events are the model's internal chain-of-thought, too noisy for Telegram |
| Show tool call lifecycle events? | **No** — don't show `tool_call_started`/`tool_call_completed`/etc. The agent's own `send_intermediate_update` calls provide better, curated progress messages |
| Edit interval | **Smallest safe interval without overwhelming Telegram** — start at ~1.5s, back off on rate-limit errors. Make it configurable via `TELEGRAM_STREAM_EDIT_INTERVAL_SECONDS` |
| Handling > 4096 chars | When the accumulated text approaches 4096 chars, finalize the current message and start a new one. Continue editing the new message. This gives natural chunking. |
| Typing indicator during streaming | **Yes** — run a background `asyncio.Task` that sends `sendChatAction("typing")` every 4s, cancel it when streaming finishes. Useful during the initial connection phase before text starts flowing. |
| Fallback when stream fails | Keep polling (`GET /agent/runs/{id}`) as fallback if the SSE connection fails or drops |

### Implementation sketch

**New module:** `telegram/stream_handler.py`

```
TelegramStreamConsumer:
    __init__(chat_id, reply_to_message_id, bot)
    
    async consume(sse_stream):
        placeholder = await bot.send_message(chat_id, "⏳ Working on it…")
        typing_task = start_typing_indicator(chat_id)
        accumulated_text = ""
        status_line = ""       # from send_intermediate_update
        last_edit_time = 0
        current_message = placeholder
        
        for event in sse_stream:
            if event.type == "text_delta":
                accumulated_text += event.delta
                if now - last_edit_time > EDIT_INTERVAL_SECONDS:
                    display = build_display(status_line, accumulated_text)
                    if len(display) > NEAR_LIMIT:
                        # Finalize current message, start new one
                        await finalize_message(current_message, accumulated_text)
                        current_message = await bot.send_message(chat_id, "…")
                        accumulated_text = overflow_text
                    else:
                        await safe_edit(current_message, display)
                    last_edit_time = now
            
            elif event.type == "run_event":
                evt = event["event"]
                if evt["event_type"] == "reasoning_update":
                    # Agent's send_intermediate_update message
                    status_line = evt["message"]
                    display = build_display(status_line, accumulated_text)
                    await safe_edit(current_message, display)
                    last_edit_time = now
                # Ignore tool_call_* and other run_event types
        
        typing_task.cancel()
        # Final delivery of complete text
        await finalize_message(current_message, accumulated_text)
```

`safe_edit` — wraps `editMessageText` to catch `message is not modified` and rate-limit errors.

`build_display` — prepends status line (italicized) above accumulated text, HTML-escaped.

**Changes to `bill_helper_api.py`:**
- Add `async def stream_thread_message(thread_id, content, files) -> AsyncIterator[SSEEvent]` using `httpx` streaming response + SSE line parser (or `httpx-sse` library)

**Changes to `message_handler.py`:**
- Replace `send_thread_message()` + `poll_run_until_terminal()` with `stream_thread_message()` + `TelegramStreamConsumer`
- Keep polling as fallback if stream connection fails

---

## 2. Forum Topics for Thread Organization

### What Telegram supports (Bot API 9.3+)

Telegram now supports **forum topics in private chats** with bots:

- `createForumTopic(chat_id, name)` — creates a named topic in the private chat
- `message_thread_id` parameter on `sendMessage`, `sendPhoto`, `editMessageText`, `sendChatAction`, etc. — targets a specific topic
- `editForumTopic(chat_id, message_thread_id, name)` — rename an existing topic
- `User.has_topics_enabled` — checks if forum mode is enabled for the bot
- Topics appear as separate conversation threads in the Telegram client UI
- Each topic has a name, optional icon color, and a `message_thread_id`

This maps onto Bill Helper's backend thread model: **one Telegram forum topic ↔ one backend agent thread**.

### Decisions

| Question | Decision |
|---|---|
| Opt-in or default? | **User toggle** — `/topics on\|off` command. Forum topics change the chat UX significantly; let the user control it. |
| Topic naming | **Use backend thread name.** The agent calls `rename_thread` (a session tool) after its first tool call to set a descriptive 1–5 word topic. Create the Telegram topic with a placeholder name (e.g. "New thread — Mar 11"), then update via `editForumTopic` when the backend thread name changes. |
| Delayed rename handling | **Placeholder + `editForumTopic`.** After a run completes, check if the backend thread title changed. If so, call `editForumTopic` to sync the Telegram topic name. Alternatively, detect `rename_thread` tool calls in the SSE stream (they appear as `tool_call_completed` events) and rename immediately. |
| General topic behavior | **Default active thread.** The "General" topic acts as the current flat-chat experience — messages there go to whichever backend thread is "active" (same as today, just inside the General topic). `/new` creates a new dedicated topic for a fresh thread. |
| Existing chat migration | **No migration needed.** Existing chats stay flat until the user runs `/topics on`. Telegram history in the flat chat remains visible in General. |
| Fallback | If forum mode isn't enabled (`has_topics_enabled` is false), fall back to current flat behavior. `/topics on` should instruct the user to enable it if needed. |

### Implementation sketch

**Phase 1: Topic-aware message routing**

Extend `state.py` to store a `thread_id ↔ message_thread_id` mapping per chat:

```python
class ChatStateRecord(BaseModel):
    active_thread_id: str | None = None
    active_run_id: str | None = None
    topics_enabled: bool = False
    topic_thread_map: dict[int, str] = {}  # message_thread_id → backend thread_id
    updated_at: datetime
```

When a message arrives with `message.message_thread_id` and topics are enabled:
1. Look up the backend thread for that topic in `topic_thread_map`
2. Send to that thread (not the "active" thread)
3. Messages in General topic still use the active thread (current behavior)

**Phase 2: Auto-create topics for `/new`**

When `/new` is called with topics enabled:
1. Create backend thread
2. `createForumTopic(chat_id, name="New thread — {date}")`
3. Store mapping: `topic_thread_map[message_thread_id] = backend_thread_id`
4. Reply inside the new topic

**Phase 3: Rename sync**

After a run completes, fetch the backend thread. If the title differs from the Telegram topic name, call `editForumTopic` to update it.

### Prerequisites

- PTB v22+ which supports `createForumTopic` in private chats (Bot API 9.3)
- May need to enable forum topic mode for the bot via BotFather
- `allowed_updates` must include `message` with `message_thread_id` awareness (already works with current `message` handler, just needs routing logic)

---

## 3. Review Gate: Inline Keyboard Approval Workflow

### The problem

The agent is review-gated: when it proposes data changes (create entry, update account, etc.), it produces `AgentChangeItem` records with status `PENDING_REVIEW`. The user must approve or reject each before it's applied.

Currently, this workflow is **web-only**:
- Frontend shows a review modal with Approve/Reject/Approve All/Reject All buttons
- Backend endpoints: `POST /agent/change-items/{id}/approve`, `/reject`, `/reopen`

On Telegram, the user sees the agent's reply text but has **no way to act on pending change items** without switching to the browser.

### What Telegram supports

**Inline keyboards** with callback queries:
- Attach buttons to any message via `reply_markup=InlineKeyboardMarkup`
- User taps a button → bot receives a `CallbackQuery` with `callback_data`
- Bot calls `query.answer()` and can `query.edit_message_text()` or `query.edit_message_reply_markup()`
- Buttons can be updated/removed after action

### Decisions

| Question | Decision |
|---|---|
| Message layout | **One message per change item.** Each gets its own message with an inline keyboard. This keeps messages short and focused. Many messages are fine. |
| Message style | **Concise and exact.** Show change type emoji, entity/entry summary, and amount. One line of rationale. No verbose payloads. |
| Payload editing? | **No.** Simply reject and let the agent re-propose. Rejecting is effectively "edit" — the user can explain what's wrong in a follow-up message and the agent adjusts. |
| Rejection notes? | **No.** Reject is a one-tap action. User writes a follow-up message to explain. |
| Stale button handling | **Check current status before acting.** If item is already APPLIED/REJECTED (e.g. approved via web), show a toast via `query.answer("Already applied", show_alert=True)` and update the message to reflect current state. |
| Reopen? | **Not on Telegram.** Web-only for now. |
| Batch approve/reject all? | **Yes** — send a summary message at the end with "✅ Approve All / ❌ Reject All" buttons after the individual item messages. |

### Implementation sketch

**One message per change item:**

```
➕ Create entry
<b>Groceries at Costco</b> — $127.43
Receipt shows Costco purchase on 2026-03-10

[✅ Approve] [❌ Reject]
```

After tapping ✅:
```
➕ Create entry
<b>Groceries at Costco</b> — $127.43
✅ Applied
```

**Batch summary message (sent last):**

```
📋 3 changes proposed — approve or reject each above, or:

[✅ Approve All] [❌ Reject All]
```

**Callback data encoding:** `ci:approve:{item_id}`, `ci:reject:{item_id}`, `ci:approve_all:{run_id}`, `ci:reject_all:{run_id}`

**New module:** `telegram/review_handler.py`

```python
class TelegramReviewHandler:
    async def render_change_items(self, chat_id, run: AgentRunRead, reply_to_message_id):
        """Send one message per pending change item, then a batch summary."""
        items = [ci for ci in run.change_items if ci.status == "PENDING_REVIEW"]
        if not items:
            return
        
        for item in items:
            text = format_single_change_item_html(item)
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data=f"ci:approve:{item.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"ci:reject:{item.id}"),
            ]])
            await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
        
        if len(items) > 1:
            summary_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve All", callback_data=f"ci:approve_all:{run.id}"),
                InlineKeyboardButton("❌ Reject All", callback_data=f"ci:reject_all:{run.id}"),
            ]])
            await bot.send_message(
                chat_id,
                f"📋 {len(items)} changes proposed — approve or reject each above, or:",
                reply_markup=summary_keyboard,
                parse_mode="HTML",
            )
    
    async def handle_callback(self, update: Update, context):
        query = update.callback_query
        action_parts = query.data.split(":")
        namespace, action, target_id = action_parts[0], action_parts[1], action_parts[2]
        
        if namespace != "ci":
            return
        
        if action == "approve":
            current = await api.get_change_item_status(target_id)
            if current.status != "PENDING_REVIEW":
                await query.answer(f"Already {current.status.lower()}", show_alert=True)
                await update_message_to_reflect_status(query, current)
                return
            result = await api.approve_change_item(target_id)
            await query.answer("✅ Applied!")
            await query.edit_message_text(
                format_applied_item_html(result),
                parse_mode="HTML",
            )
        
        elif action == "reject":
            # Similar, but call api.reject_change_item()
            ...
        
        elif action in ("approve_all", "reject_all"):
            # Fetch all pending items for run, batch approve/reject
            # Update each individual message's text + remove keyboards
            ...
```

**Required wiring changes:**

1. `polling.py` / `webhook.py`: Change `allowed_updates=["message"]` → `["message", "callback_query"]`
2. `commands.py`: Register `CallbackQueryHandler(review_handler.handle_callback)`
3. `bill_helper_api.py`: Add `approve_change_item()`, `reject_change_item()` methods (call `POST /agent/change-items/{id}/approve` and `/reject` with empty payloads since we don't do notes or overrides)
4. `message_handler.py` or `stream_handler.py`: After run completes, check for pending change items and call `render_change_items()`

---

## 4. Dashboard Charts Command (`/dashboard`)

### What we need

A `/dashboard` command that:
1. Calls `GET /dashboard?month=YYYY-MM` (defaults to current month)
2. Generates two chart images using matplotlib in the Telegram transport process
3. Sends both as Telegram photos via `sendPhoto`
4. Includes a KPI text summary

### Data available from backend

**"Income vs Expense Trend"** → `monthly_trend: list[DashboardMonthlyTrendPoint]`
```python
{ month: "2026-01", expense_total_minor: 234500, income_total_minor: 500000, filter_group_totals: {...} }
```

**"Expense by Filter Group"** → `filter_groups: list[DashboardFilterGroupSummary]`
```python
{ key: "groceries", label: "Groceries", color: "#4CAF50", total_minor: 45000, share: 0.23 }
```

**KPIs** → `kpis: DashboardKpisRead` with `total_income`, `total_expense`, `balance`, etc.

### Decisions

| Question | Decision |
|---|---|
| Where to generate? | **Option A: In the Telegram transport** — add `matplotlib` as a dependency, generate charts in `telegram/charts.py`. Simpler for a prototype, no backend changes. Move to a shared backend endpoint later if iOS or other surfaces need chart images. |
| Which charts? | **Income vs Expense Trend** (line chart) + **Expense by Filter Group** (horizontal bar or pie chart). Start with these two. |
| Chart style | **Match the web dashboard design language** but optimize for iPhone screens — larger fonts, bolder lines, good contrast. Use the `color` field from `filter_groups` for consistent colors across surfaces. |
| Month argument | `/dashboard` → current month. `/dashboard 2026-02` → specific month. |
| KPI summary | **Yes** — send a text message before the charts with key numbers: total income, total expense, balance. |
| New dependency | `matplotlib` added to `pyproject.toml` under `[project.optional-dependencies]` telegram group. |

### Implementation sketch

**New module:** `telegram/charts.py`

```python
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO

def render_income_expense_trend(monthly_trend, currency_code) -> BytesIO:
    """Line chart: months on x-axis, income (green) and expense (red) lines."""
    months = [p.month for p in monthly_trend]
    income = [p.income_total_minor / 100 for p in monthly_trend]
    expense = [p.expense_total_minor / 100 for p in monthly_trend]
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    ax.plot(months, income, color="#4CAF50", marker="o", linewidth=2.5, label="Income")
    ax.plot(months, expense, color="#F44336", marker="o", linewidth=2.5, label="Expense")
    ax.set_title("Income vs Expense Trend", fontsize=16, fontweight="bold")
    ax.legend(fontsize=13)
    ax.tick_params(labelsize=12)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf

def render_expense_by_filter_group(filter_groups, currency_code) -> BytesIO:
    """Horizontal bar chart of expense by filter group, using group colors."""
    labels = [g.label for g in filter_groups]
    values = [g.total_minor / 100 for g in filter_groups]
    colors = [g.color or "#90A4AE" for g in filter_groups]
    
    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.8)), dpi=150)
    ax.barh(labels, values, color=colors)
    ax.set_title("Expense by Filter Group", fontsize=16, fontweight="bold")
    # ... value labels on bars, styling
    fig.tight_layout()
    
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
```

**New command in `commands.py`:**
```python
async def handle_dashboard(update, context):
    month = parse_month_arg(context.args) or current_month()
    await update.message.reply_text(f"📊 Generating dashboard for {month}…")
    
    dashboard = await api.get_dashboard(month)
    
    # KPI summary text
    kpi_text = format_kpi_summary_html(dashboard.kpis, dashboard.currency_code, month)
    await update.message.reply_html(kpi_text)
    
    # Charts
    if dashboard.monthly_trend:
        trend_img = render_income_expense_trend(dashboard.monthly_trend, dashboard.currency_code)
        await update.message.reply_photo(photo=trend_img, caption="Income vs Expense Trend")
    
    if dashboard.filter_groups:
        groups_img = render_expense_by_filter_group(dashboard.filter_groups, dashboard.currency_code)
        await update.message.reply_photo(photo=groups_img, caption="Expense by Filter Group")
```

**Changes to `bill_helper_api.py`:**
- Add `async def get_dashboard(month: str) -> DashboardRead` calling `GET /dashboard?month={month}`

---

## 5. Additional UX Improvements

### 5a. `sendChatAction` typing indicator

Send `sendChatAction(action="typing")` immediately on message receipt. Continue every 4s in a background `asyncio.Task` until the agent run completes or streaming begins. Once streaming starts and text is flowing, the typing indicator is less needed but still useful during gaps between tool calls.

### 5b. Register bot commands with BotFather for auto-complete

Call `bot.set_my_commands()` on startup:
```python
await bot.set_my_commands([
    BotCommand("start", "Introduction and quick help"),
    BotCommand("help", "List commands and supported uploads"),
    BotCommand("new", "Create a new conversation thread"),
    BotCommand("threads", "List recent threads"),
    BotCommand("use", "Switch to a thread by number or ID"),
    BotCommand("model", "Show or change the AI model"),
    BotCommand("stop", "Stop the current agent run"),
    BotCommand("status", "Show current model, thread, and run state"),
    BotCommand("dashboard", "Show dashboard charts for current month"),
    BotCommand("topics", "Toggle forum topics on/off"),
])
```

### 5c. Richer error formatting

Use Telegram HTML formatting for structured error messages:
```html
<b>❌ Error</b>
<code>503 Service Unavailable</code>
The backend agent is currently busy. Try again in a moment.
```

### 5d. Media group support (multiple photos)

Coalesce photos from the same media group (`media_group_id`) and send all as attachments in a single backend call. Lower priority than streaming and approval.

### 5e. Expand allowed update types

Change from `allowed_updates=["message"]` to `["message", "callback_query"]`. Required by the review gate feature. Consider adding `"edited_message"` later if we want to support message correction re-sends.

### 5f. Cost info in replies

Append a small footer to agent replies:
```
💰 $0.012 | 1.2k→0.8k tokens | claude-sonnet-4
```
Could be togglable. The data is already in `AgentRunRead.total_cost_usd`, `input_tokens`, `output_tokens`, `model_name`.

### 5g. Message reactions for quick feedback

Use `setMessageReaction` for lightweight status:
- 👀 on message receipt
- ✅ on successful completion
- ❌ on failure

Complement to (not replacement for) the streaming placeholder message.

---

## Implementation Priority

| Priority | Feature | Effort | Impact | Section |
|---|---|---|---|---|
| **P0** | Streaming via `editMessageText` + `send_intermediate_update` | Medium | High — eliminates the "silent wait" problem | §1 |
| **P0** | Review gate inline keyboards | Medium | High — unblocks the core approval workflow on Telegram | §3 |
| **P1** | Dashboard charts command | Medium | High — key feature request | §4 |
| **P1** | `sendChatAction` typing indicator | Small | Medium — quick polish win | §5a |
| **P1** | Bot command registration | Small | Medium — better discoverability | §5b |
| **P1** | Expand `allowed_updates` to include `callback_query` | Small | Required by §3 | §5e |
| **P2** | Forum topics for threads | Large | High — but changes chat UX significantly | §2 |
| **P2** | Media group coalescing | Medium | Low–Medium | §5d |
| **P3** | Cost info in replies | Small | Low — nice-to-have | §5f |
| **P3** | Message reactions | Small | Low — nice-to-have | §5g |
| **P3** | Richer error formatting | Small | Low — polish | §5c |

---

## Dependencies and Prerequisites

- **PTB version:** Verify `python-telegram-bot` version supports `createForumTopic` in private chats (v22+ needed for Bot API 9.3 features). Check with Context7 at implementation time.
- **New Python dependency:** `matplotlib` for chart generation (add to pyproject.toml `[project.optional-dependencies]` under a `telegram` group)
- **SSE client:** `httpx-sse` or manual SSE line parser for consuming the backend stream in `bill_helper_api.py`
- **BotFather configuration:** May need to enable forum topic mode for the bot (P2)
- **Backend changes:** None required for P0/P1 items — all endpoints already exist (`/messages/stream`, `/change-items/{id}/approve`, `/change-items/{id}/reject`, `/dashboard`). P2 forum topics may need detection of `rename_thread` tool calls in the SSE stream for topic name sync.
