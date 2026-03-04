from __future__ import annotations

import os
import tempfile
import threading
import time

import pytest
from fastapi.testclient import TestClient

_test_db_dir = tempfile.mkdtemp(prefix="bill_helper_test_")
os.environ["BILL_HELPER_DATABASE_URL"] = f"sqlite:///{_test_db_dir}/test_bill_helper.db"
os.environ["GOOGLE_API_KEY"] = "test-google-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"

from backend.config import get_settings  # noqa: E402

get_settings.cache_clear()

from backend.database import Base, engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers import agent as agent_router  # noqa: E402


def _wait_for_background_agent_threads(timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        background_threads = [
            thread
            for thread in threading.enumerate()
            if thread.is_alive() and getattr(thread, "_target", None) is agent_router._run_agent_in_background
        ]
        if not background_threads:
            return
        for thread in background_threads:
            thread.join(timeout=0.05)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    _wait_for_background_agent_threads()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
