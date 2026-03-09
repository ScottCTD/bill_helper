from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db_meta import Base
from backend.models_shared import utc_now


class RuntimeSettings(Base):
    __tablename__ = "runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, default="default"
    )
    current_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_memory: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    dashboard_currency_code: Mapped[str | None] = mapped_column(
        String(3), nullable=True
    )
    agent_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_agent_models: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_max_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_bulk_max_concurrent_threads: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    agent_retry_max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_retry_initial_wait_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_retry_max_wait_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_retry_backoff_multiplier: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    agent_max_image_size_bytes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    agent_max_images_per_message: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    agent_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agent_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
