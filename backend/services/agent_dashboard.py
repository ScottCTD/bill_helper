# CALLING SPEC:
# - Purpose: build principal-scoped agent usage analytics for the dashboard route.
# - Inputs: SQLAlchemy session, authenticated principal, time-range key, and optional model/surface filters.
# - Outputs: `AgentDashboardRead` payloads with metrics, chart series, breakdown tables, and top-run rows.
# - Side effects: reads database state only.
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentRunStatus
from backend.models_agent import AgentRun, AgentThread
from backend.schemas_agent import (
    AgentDashboardCostPointRead,
    AgentDashboardMetricsRead,
    AgentDashboardModelBreakdownRead,
    AgentDashboardRead,
    AgentDashboardSurfaceBreakdownRead,
    AgentDashboardTokenSliceRead,
    AgentDashboardTopRunRead,
)
from backend.services.access_scope import agent_thread_owner_filter
from backend.services.agent.pricing import calculate_usage_costs

AgentDashboardRangeKey = Literal["7d", "30d", "90d", "all"]
AgentDashboardGranularity = Literal["day", "week", "month"]

AGENT_DASHBOARD_DAY_COUNTS: dict[AgentDashboardRangeKey, int | None] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}
AGENT_DASHBOARD_GRANULARITY: dict[AgentDashboardRangeKey, AgentDashboardGranularity] = {
    "7d": "day",
    "30d": "day",
    "90d": "week",
    "all": "month",
}
AGENT_DASHBOARD_SURFACES = ("app", "telegram")
AGENT_DASHBOARD_TOP_RUN_LIMIT = 10


@dataclass(frozen=True, slots=True)
class AgentDashboardWindow:
    range_key: AgentDashboardRangeKey
    granularity: AgentDashboardGranularity
    start_at: datetime | None
    end_at: datetime | None


@dataclass(frozen=True, slots=True)
class AgentDashboardRunRow:
    run_id: str
    thread_id: str
    thread_title: str | None
    model_name: str
    surface: str
    status: AgentRunStatus
    created_at: datetime
    completed_at: datetime | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    total_tokens: int
    total_cost_usd: float


def build_agent_dashboard_read(
    db: Session,
    *,
    principal: RequestPrincipal,
    range_key: AgentDashboardRangeKey = "30d",
    model_names: list[str] | None = None,
    surfaces: list[str] | None = None,
    today: date | None = None,
) -> AgentDashboardRead:
    window = resolve_agent_dashboard_window(range_key, today=today)
    selected_models = _normalize_string_filters(model_names)
    selected_surfaces = _normalize_surface_filters(surfaces)
    all_rows = _list_dashboard_rows(db, principal=principal, window=window)
    available_models = sorted({row.model_name for row in all_rows})
    filtered_rows = [
        row
        for row in all_rows
        if (not selected_models or row.model_name in selected_models)
        and (not selected_surfaces or row.surface in selected_surfaces)
    ]

    return AgentDashboardRead(
        range_key=window.range_key,
        granularity=window.granularity,
        available_models=available_models,
        available_surfaces=list(AGENT_DASHBOARD_SURFACES),
        selected_models=selected_models,
        selected_surfaces=selected_surfaces,
        metrics=_build_metrics(filtered_rows),
        cost_series=_build_cost_series(filtered_rows, granularity=window.granularity),
        token_distribution=_build_token_distribution(filtered_rows),
        model_breakdown=_build_model_breakdown(filtered_rows),
        surface_breakdown=_build_surface_breakdown(filtered_rows),
        top_runs=_build_top_runs(filtered_rows),
    )


def resolve_agent_dashboard_window(
    range_key: AgentDashboardRangeKey,
    *,
    today: date | None = None,
) -> AgentDashboardWindow:
    current_day = today or datetime.now(timezone.utc).date()
    day_count = AGENT_DASHBOARD_DAY_COUNTS[range_key]
    if day_count is None:
        return AgentDashboardWindow(
            range_key=range_key,
            granularity=AGENT_DASHBOARD_GRANULARITY[range_key],
            start_at=None,
            end_at=None,
        )

    start_day = current_day - timedelta(days=day_count - 1)
    end_day = current_day + timedelta(days=1)
    return AgentDashboardWindow(
        range_key=range_key,
        granularity=AGENT_DASHBOARD_GRANULARITY[range_key],
        start_at=datetime.combine(start_day, time.min, tzinfo=timezone.utc),
        end_at=datetime.combine(end_day, time.min, tzinfo=timezone.utc),
    )


def _normalize_string_filters(values: list[str] | None) -> list[str]:
    normalized = sorted({value.strip() for value in values or [] if value and value.strip()})
    return normalized


def _normalize_surface_filters(values: list[str] | None) -> list[str]:
    normalized = [value for value in _normalize_string_filters(values) if value in AGENT_DASHBOARD_SURFACES]
    return normalized


def _list_dashboard_rows(
    db: Session,
    *,
    principal: RequestPrincipal,
    window: AgentDashboardWindow,
) -> list[AgentDashboardRunRow]:
    stmt = (
        select(AgentRun, AgentThread.title)
        .join(AgentThread, AgentThread.id == AgentRun.thread_id)
        .where(
            agent_thread_owner_filter(principal),
            AgentRun.status.in_((AgentRunStatus.COMPLETED, AgentRunStatus.FAILED)),
        )
        .order_by(AgentRun.created_at.asc(), AgentRun.id.asc())
    )
    if window.start_at is not None:
        stmt = stmt.where(AgentRun.created_at >= window.start_at)
    if window.end_at is not None:
        stmt = stmt.where(AgentRun.created_at < window.end_at)

    rows: list[AgentDashboardRunRow] = []
    for run, thread_title in db.execute(stmt).all():
        input_tokens = max(int(run.input_tokens or 0), 0)
        output_tokens = max(int(run.output_tokens or 0), 0)
        cache_read_tokens = max(int(run.cache_read_tokens or 0), 0)
        costs = calculate_usage_costs(
            model_name=run.model_name,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cache_read_tokens=run.cache_read_tokens,
            cache_write_tokens=run.cache_write_tokens,
        )
        rows.append(
            AgentDashboardRunRow(
                run_id=run.id,
                thread_id=run.thread_id,
                thread_title=thread_title,
                model_name=run.model_name,
                surface=(run.surface or "app").strip() or "app",
                status=run.status,
                created_at=run.created_at,
                completed_at=run.completed_at,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                total_tokens=input_tokens + output_tokens,
                total_cost_usd=round(float(costs.total_cost_usd or 0.0), 12),
            )
        )
    return rows


def _build_metrics(rows: list[AgentDashboardRunRow]) -> AgentDashboardMetricsRead:
    total_cost_usd = round(sum(row.total_cost_usd for row in rows), 12)
    total_tokens = sum(row.total_tokens for row in rows)
    total_run_count = len(rows)
    completed_run_count = sum(1 for row in rows if row.status == AgentRunStatus.COMPLETED)
    failed_run_count = sum(1 for row in rows if row.status == AgentRunStatus.FAILED)
    total_input_tokens = sum(row.input_tokens for row in rows)
    total_cache_read_tokens = sum(row.cache_read_tokens for row in rows)
    model_counter = Counter(row.model_name for row in rows)
    most_used_model = None
    if model_counter:
        most_used_model = sorted(model_counter.items(), key=lambda item: (-item[1], item[0]))[0][0]

    avg_cost_per_run_usd = round(total_cost_usd / total_run_count, 6) if total_run_count else 0.0
    avg_tokens_per_run = round(total_tokens / total_run_count, 2) if total_run_count else 0.0
    cache_hit_rate = round(total_cache_read_tokens / total_input_tokens, 4) if total_input_tokens else 0.0
    failure_rate = round(failed_run_count / total_run_count, 4) if total_run_count else 0.0
    return AgentDashboardMetricsRead(
        total_cost_usd=total_cost_usd,
        total_tokens=total_tokens,
        total_run_count=total_run_count,
        completed_run_count=completed_run_count,
        failed_run_count=failed_run_count,
        avg_cost_per_run_usd=avg_cost_per_run_usd,
        avg_tokens_per_run=avg_tokens_per_run,
        cache_hit_rate=cache_hit_rate,
        most_used_model=most_used_model,
        failure_rate=failure_rate,
    )


def _bucket_start(created_at: datetime, *, granularity: AgentDashboardGranularity) -> datetime:
    if granularity == "day":
        bucket_date = created_at.date()
        return datetime.combine(bucket_date, time.min, tzinfo=timezone.utc)
    if granularity == "week":
        bucket_date = created_at.date() - timedelta(days=created_at.weekday())
        return datetime.combine(bucket_date, time.min, tzinfo=timezone.utc)
    bucket_date = date(created_at.year, created_at.month, 1)
    return datetime.combine(bucket_date, time.min, tzinfo=timezone.utc)


def _bucket_key(bucket_start: datetime, *, granularity: AgentDashboardGranularity) -> str:
    if granularity == "month":
        return bucket_start.strftime("%Y-%m")
    return bucket_start.date().isoformat()


def _bucket_label(bucket_start: datetime, *, granularity: AgentDashboardGranularity) -> str:
    if granularity == "day":
        return bucket_start.strftime("%b %-d")
    if granularity == "week":
        return f"Week of {bucket_start.strftime('%b %-d')}"
    return bucket_start.strftime("%b %Y")


def _build_cost_series(
    rows: list[AgentDashboardRunRow],
    *,
    granularity: AgentDashboardGranularity,
) -> list[AgentDashboardCostPointRead]:
    buckets: dict[str, dict[str, object]] = {}
    for row in rows:
        bucket_start = _bucket_start(row.created_at, granularity=granularity)
        bucket_key = _bucket_key(bucket_start, granularity=granularity)
        if bucket_key not in buckets:
            buckets[bucket_key] = {
                "bucket_start": bucket_start,
                "total_cost_usd": 0.0,
                "run_count": 0,
                "costs_by_model": defaultdict(float),
            }
        bucket = buckets[bucket_key]
        bucket["total_cost_usd"] = round(float(bucket["total_cost_usd"]) + row.total_cost_usd, 12)
        bucket["run_count"] = int(bucket["run_count"]) + 1
        costs_by_model = bucket["costs_by_model"]
        assert isinstance(costs_by_model, defaultdict)
        costs_by_model[row.model_name] += row.total_cost_usd

    series: list[AgentDashboardCostPointRead] = []
    for bucket_key in sorted(buckets):
        bucket = buckets[bucket_key]
        bucket_start = bucket["bucket_start"]
        assert isinstance(bucket_start, datetime)
        costs_by_model = bucket["costs_by_model"]
        assert isinstance(costs_by_model, defaultdict)
        series.append(
            AgentDashboardCostPointRead(
                bucket_key=bucket_key,
                bucket_label=_bucket_label(bucket_start, granularity=granularity),
                bucket_start=bucket_start,
                total_cost_usd=round(float(bucket["total_cost_usd"]), 12),
                run_count=int(bucket["run_count"]),
                costs_by_model={
                    model_name: round(float(total_cost_usd), 12)
                    for model_name, total_cost_usd in sorted(costs_by_model.items())
                },
            )
        )
    return series


def _build_token_distribution(rows: list[AgentDashboardRunRow]) -> list[AgentDashboardTokenSliceRead]:
    slices = [
        ("Input", sum(row.input_tokens for row in rows)),
        ("Output", sum(row.output_tokens for row in rows)),
    ]
    grand_total = sum(token_count for _, token_count in slices)
    return [
        AgentDashboardTokenSliceRead(
            label=label,
            token_count=token_count,
            share=round(token_count / grand_total, 4) if grand_total else 0.0,
        )
        for label, token_count in slices
    ]


def _build_model_breakdown(rows: list[AgentDashboardRunRow]) -> list[AgentDashboardModelBreakdownRead]:
    grouped: dict[str, list[AgentDashboardRunRow]] = defaultdict(list)
    for row in rows:
        grouped[row.model_name].append(row)

    breakdown: list[AgentDashboardModelBreakdownRead] = []
    for model_name, model_rows in grouped.items():
        run_count = len(model_rows)
        total_cost_usd = round(sum(row.total_cost_usd for row in model_rows), 12)
        breakdown.append(
            AgentDashboardModelBreakdownRead(
                model_name=model_name,
                run_count=run_count,
                completed_run_count=sum(1 for row in model_rows if row.status == AgentRunStatus.COMPLETED),
                failed_run_count=sum(1 for row in model_rows if row.status == AgentRunStatus.FAILED),
                input_tokens=sum(row.input_tokens for row in model_rows),
                output_tokens=sum(row.output_tokens for row in model_rows),
                cache_read_tokens=sum(row.cache_read_tokens for row in model_rows),
                total_tokens=sum(row.total_tokens for row in model_rows),
                total_cost_usd=total_cost_usd,
                avg_cost_per_run_usd=round(total_cost_usd / run_count, 6) if run_count else 0.0,
            )
        )
    return sorted(
        breakdown,
        key=lambda row: (-row.total_cost_usd, -row.run_count, row.model_name),
    )


def _build_surface_breakdown(rows: list[AgentDashboardRunRow]) -> list[AgentDashboardSurfaceBreakdownRead]:
    grouped: dict[str, list[AgentDashboardRunRow]] = defaultdict(list)
    for row in rows:
        grouped[row.surface].append(row)

    breakdown: list[AgentDashboardSurfaceBreakdownRead] = []
    for surface in AGENT_DASHBOARD_SURFACES:
        surface_rows = grouped.get(surface, [])
        if not surface_rows and grouped:
            continue
        costs_by_model: dict[str, float] = defaultdict(float)
        for row in surface_rows:
            costs_by_model[row.model_name] += row.total_cost_usd
        breakdown.append(
            AgentDashboardSurfaceBreakdownRead(
                surface=surface,
                run_count=len(surface_rows),
                total_tokens=sum(row.total_tokens for row in surface_rows),
                total_cost_usd=round(sum(row.total_cost_usd for row in surface_rows), 12),
                costs_by_model={
                    model_name: round(float(total_cost_usd), 12)
                    for model_name, total_cost_usd in sorted(costs_by_model.items())
                },
            )
        )
    return breakdown


def _build_top_runs(rows: list[AgentDashboardRunRow]) -> list[AgentDashboardTopRunRead]:
    top_rows = sorted(
        rows,
        key=lambda row: (-row.total_cost_usd, -row.total_tokens, row.created_at.timestamp(), row.run_id),
        reverse=False,
    )[:AGENT_DASHBOARD_TOP_RUN_LIMIT]
    return [
        AgentDashboardTopRunRead(
            run_id=row.run_id,
            thread_id=row.thread_id,
            thread_title=row.thread_title,
            model_name=row.model_name,
            surface=row.surface,
            status=row.status,
            created_at=row.created_at,
            completed_at=row.completed_at,
            total_tokens=row.total_tokens,
            total_cost_usd=row.total_cost_usd,
        )
        for row in top_rows
    ]
