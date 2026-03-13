# Agent Cost Dashboard

## Overview

Add a section to the dashboard to display analytics of agent usage (tokens and costs), providing visibility into AI spending patterns and helping users optimize their usage.

## Key Metrics (Highlight Cards)

### Primary Metrics

- **Total Cost**: Overall spending across all agent sessions (sum of `total_cost_usd`)
- **Total Tokens**: Combined input + output tokens consumed
- **Total Runs**: Number of completed agent runs
- **Avg Cost per Run**: Mean cost per agent run

### Secondary Metrics

- **Avg Tokens per Run**: Mean token consumption
- **Cache Hit Rate**: Percentage of tokens served from cache (`cache_read_tokens / input_tokens`)
- **Most Used Model**: Model with highest run count
- **Failure Rate**: Percentage of runs with status "failed"

## Visualization Components

### 1. Cost Over Time (AreaChart - Recharts)

- Daily/weekly/monthly cost trends
- Configurable time range (7d, 30d, 90d, all time)
- Stacked area for model breakdown
- Reference: `frontend/src/features/dashboard/DashboardPanels.tsx` line 160 (DailySpendingPanel)

### 2. Token Distribution (PieChart - Recharts)

- Input vs Output token ratio
- Breakdown by model
- Percentage labels
- Reference: `frontend/src/features/dashboard/DashboardPanels.tsx` line 236 (BreakdownsPanel)

### 3. Model-Specific Table


| Model  | Runs | Input Tokens | Output Tokens | Cache Reads | Total Cost | Avg Cost/Run |
| ------ | ---- | ------------ | ------------- | ----------- | ---------- | ------------ |
| gpt-4o | 42   | 125,000      | 45,000        | 12,000      | $3.50      | $0.08        |


### 4. Cost by Surface (BarChart - Recharts)

- App vs Telegram usage comparison
- Grouped by model or time period

### 5. Top Expensive Runs (Table)

- Date, Thread Title, Model, Cost, Tokens, Status
- Click to navigate to thread

## Data Requirements

### Source Table: `agent_runs`

**Available Fields** (from `backend/models_agent.py`):

```python
id: str                          # UUID
thread_id: str                   # FK to agent_threads
model_name: str                  # e.g., "gpt-4o", "claude-3-5-sonnet"
surface: str                     # "app" or "telegram"
status: AgentRunStatus           # "running" | "completed" | "failed"
input_tokens: int | None
output_tokens: int | None
cache_read_tokens: int | None
cache_write_tokens: int | None
context_tokens: int | None
created_at: datetime
completed_at: datetime | None
```

**Computed Fields** (via `backend/services/agent/pricing.py`):

```python
input_cost_usd: float | None
output_cost_usd: float | None
total_cost_usd: float | None
```

### Aggregation Levels

- Per run (raw data, already available via `/api/v1/agent/runs/{run_id}`)
- Daily summary
- Weekly summary
- Monthly summary

## UI/UX Considerations

### Layout

Follow existing dashboard pattern from `frontend/src/pages/DashboardPage.tsx`:

- Metrics cards at top (4-column grid, responsive)
- Charts in main content area (2-column layout on xl screens)
- Full-width table at bottom
- Use existing UI components from `frontend/src/components/ui/`

### Styling

- Use Tailwind CSS with existing utility classes
- CSS variables from `frontend/src/styles/tokens.css`:
  - Chart colors: `--chart-segment-1` through `--chart-segment-6`
  - Status colors: `--success`, `--warning`, `--destructive`
- Dark mode support via existing theme system

### Interactivity

- Time range selector (global filter, like month/year selector in finance dashboard)
- Model filter (multi-select dropdown)
- Surface filter (app/telegram)
- Click-through from charts to filtered run list

## Implementation Phases

### Phase 1: Backend Foundation

- Create `AgentDashboardRead` schema in `backend/schemas_agent.py`
- Create `backend/services/agent_dashboard.py` with aggregation logic
- Add dashboard endpoints to `backend/routers/agent.py`
- Add database index on `created_at` if not present

### Phase 2: Core Frontend

- Add types to `frontend/src/lib/api/agent.ts`
- Create `AgentCostDashboard.tsx` component
- Implement metric cards with loading states
- Add time range selector

### Phase 3: Charts

- Cost over time area chart
- Token distribution pie chart
- Model comparison table
- Surface breakdown bar chart

### Phase 4: Polish

- Model/surface filters
- Top runs table with navigation
- Export functionality (CSV)
- Error handling and empty states
- Mobile responsiveness testing

## Reference Files

- Finance dashboard: `backend/services/finance_dashboard.py`
- Dashboard panels: `frontend/src/features/dashboard/DashboardPanels.tsx`
- Chart examples: `frontend/src/features/dashboard/helpers.tsx`
- Agent models: `backend/models_agent.py`
- Pricing service: `backend/services/agent/pricing.py`
- Agent serializers: `backend/services/agent/serializers.py`

