from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.database import build_engine
from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import AgentMessage, AgentRun, AgentThread
from backend.services.agent.pricing import UsageCosts
from backend.services.users import find_user_by_name


def _seed_agent_run(
    *,
    owner_user_id: str,
    thread_title: str,
    model_name: str,
    surface: str,
    status: AgentRunStatus,
    created_at: datetime,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
) -> AgentRun:
    with Session(build_engine()) as db:
        thread = AgentThread(
            owner_user_id=owner_user_id,
            title=thread_title,
            created_at=created_at,
            updated_at=created_at,
        )
        user_message = AgentMessage(
            thread=thread,
            role=AgentMessageRole.USER,
            content_markdown="seeded prompt",
            created_at=created_at,
        )
        run = AgentRun(
            thread=thread,
            user_message=user_message,
            status=status,
            model_name=model_name,
            surface=surface,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=0,
            created_at=created_at,
            completed_at=created_at + timedelta(minutes=1),
        )
        db.add_all([thread, user_message, run])
        db.commit()
        db.refresh(run)
        return run


def test_agent_dashboard_aggregates_usage_and_respects_filters(client, auth_headers, monkeypatch):
    alice_headers = auth_headers("alice")
    auth_headers("bob")

    def fake_calculate_usage_costs(**kwargs):
        input_tokens = int(kwargs.get("input_tokens") or 0)
        output_tokens = int(kwargs.get("output_tokens") or 0)
        total_cost = round((input_tokens + output_tokens) / 1000, 6)
        return UsageCosts(
            input_cost_usd=round(input_tokens / 1000, 6),
            output_cost_usd=round(output_tokens / 1000, 6),
            total_cost_usd=total_cost,
        )

    monkeypatch.setattr("backend.services.agent_dashboard.calculate_usage_costs", fake_calculate_usage_costs)

    with Session(build_engine()) as db:
        alice = find_user_by_name(db, "alice")
        bob = find_user_by_name(db, "bob")
        assert alice is not None
        assert bob is not None
        alice_user_id = alice.id
        bob_user_id = bob.id

    recent_day = datetime(2026, 3, 14, 15, 0, tzinfo=timezone.utc)
    _seed_agent_run(
        owner_user_id=alice_user_id,
        thread_title="Budget cleanup",
        model_name="gpt-4o",
        surface="app",
        status=AgentRunStatus.COMPLETED,
        created_at=recent_day,
        input_tokens=100,
        output_tokens=20,
        cache_read_tokens=40,
    )
    _seed_agent_run(
        owner_user_id=alice_user_id,
        thread_title="Receipt OCR",
        model_name="claude-3-5-sonnet",
        surface="app",
        status=AgentRunStatus.FAILED,
        created_at=recent_day - timedelta(days=1),
        input_tokens=50,
        output_tokens=10,
        cache_read_tokens=0,
    )
    _seed_agent_run(
        owner_user_id=alice_user_id,
        thread_title="Telegram follow-up",
        model_name="gpt-4o",
        surface="telegram",
        status=AgentRunStatus.COMPLETED,
        created_at=recent_day - timedelta(days=22),
        input_tokens=80,
        output_tokens=20,
        cache_read_tokens=10,
    )
    _seed_agent_run(
        owner_user_id=alice_user_id,
        thread_title="Old thread",
        model_name="gpt-4o",
        surface="app",
        status=AgentRunStatus.COMPLETED,
        created_at=datetime(2025, 10, 1, 9, 0, tzinfo=timezone.utc),
        input_tokens=999,
        output_tokens=1,
        cache_read_tokens=0,
    )
    _seed_agent_run(
        owner_user_id=bob_user_id,
        thread_title="Bob private run",
        model_name="gpt-4o",
        surface="app",
        status=AgentRunStatus.COMPLETED,
        created_at=recent_day,
        input_tokens=500,
        output_tokens=500,
        cache_read_tokens=0,
    )

    response = client.get(
        "/api/v1/agent/dashboard",
        params={"range": "90d"},
        headers=alice_headers,
    )
    response.raise_for_status()
    payload = response.json()

    assert payload["range_key"] == "90d"
    assert payload["granularity"] == "week"
    assert payload["available_models"] == ["claude-3-5-sonnet", "gpt-4o"]
    assert payload["available_surfaces"] == ["app", "telegram"]
    assert payload["selected_models"] == []
    assert payload["selected_surfaces"] == []

    metrics = payload["metrics"]
    assert metrics["total_run_count"] == 3
    assert metrics["completed_run_count"] == 2
    assert metrics["failed_run_count"] == 1
    assert metrics["total_tokens"] == 280
    assert metrics["total_cost_usd"] == 0.28
    assert metrics["avg_cost_per_run_usd"] == 0.093333
    assert metrics["avg_tokens_per_run"] == 93.33
    assert metrics["cache_hit_rate"] == 0.2174
    assert metrics["most_used_model"] == "gpt-4o"
    assert metrics["failure_rate"] == 0.3333

    top_runs = payload["top_runs"]
    assert [run["thread_title"] for run in top_runs[:3]] == [
        "Budget cleanup",
        "Telegram follow-up",
        "Receipt OCR",
    ]

    model_breakdown = {row["model_name"]: row for row in payload["model_breakdown"]}
    assert model_breakdown["gpt-4o"]["run_count"] == 2
    assert model_breakdown["gpt-4o"]["total_tokens"] == 220
    assert model_breakdown["gpt-4o"]["total_cost_usd"] == 0.22
    assert model_breakdown["claude-3-5-sonnet"]["failed_run_count"] == 1

    surface_breakdown = {row["surface"]: row for row in payload["surface_breakdown"]}
    assert surface_breakdown["app"]["run_count"] == 2
    assert surface_breakdown["app"]["total_cost_usd"] == 0.18
    assert surface_breakdown["telegram"]["run_count"] == 1
    assert surface_breakdown["telegram"]["total_cost_usd"] == 0.1

    token_distribution = {row["label"]: row for row in payload["token_distribution"]}
    assert token_distribution["Input"]["token_count"] == 230
    assert token_distribution["Output"]["token_count"] == 50

    filtered_response = client.get(
        "/api/v1/agent/dashboard",
        params=[
            ("range", "all"),
            ("model", "gpt-4o"),
            ("surface", "telegram"),
        ],
        headers=alice_headers,
    )
    filtered_response.raise_for_status()
    filtered_payload = filtered_response.json()

    assert filtered_payload["range_key"] == "all"
    assert filtered_payload["granularity"] == "month"
    assert filtered_payload["selected_models"] == ["gpt-4o"]
    assert filtered_payload["selected_surfaces"] == ["telegram"]
    assert filtered_payload["metrics"]["total_run_count"] == 1
    assert filtered_payload["metrics"]["total_tokens"] == 100
    assert filtered_payload["top_runs"][0]["thread_title"] == "Telegram follow-up"


def test_agent_dashboard_returns_empty_payload_for_no_runs(client, monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent_dashboard.calculate_usage_costs",
        lambda **_kwargs: UsageCosts(input_cost_usd=0.0, output_cost_usd=0.0, total_cost_usd=0.0),
    )

    response = client.get(
        "/api/v1/agent/dashboard",
        params={"range": "7d"},
    )
    response.raise_for_status()
    payload = response.json()

    assert payload["range_key"] == "7d"
    assert payload["metrics"]["total_run_count"] == 0
    assert payload["cost_series"] == []
    assert payload["model_breakdown"] == []
    assert payload["top_runs"] == []
