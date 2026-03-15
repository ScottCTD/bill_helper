from __future__ import annotations

import os
import tempfile
import threading
import time

import pytest
from fastapi.testclient import TestClient

_test_db_dir = tempfile.mkdtemp(prefix="bill_helper_test_")
os.environ["BILL_HELPER_DATABASE_URL"] = f"sqlite:///{_test_db_dir}/test_bill_helper.db"
os.environ["BILL_HELPER_AGENT_WORKSPACE_ENABLED"] = "0"
os.environ["GOOGLE_API_KEY"] = "test-google-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"

from backend.config import get_settings  # noqa: E402

get_settings.cache_clear()

from backend.database import build_engine  # noqa: E402
from backend.database import get_session_maker  # noqa: E402
from backend.db_meta import Base  # noqa: E402
from backend.main import create_app  # noqa: E402
from backend.services.agent.execution import run_agent_in_background  # noqa: E402
from backend.services.passwords import hash_password  # noqa: E402
from backend.services.users import create_or_reset_admin_user, find_user_by_name  # noqa: E402

engine = build_engine()
app = create_app()


def _wait_for_background_agent_threads(timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        background_threads = [
            thread
            for thread in threading.enumerate()
            if thread.is_alive() and getattr(thread, "_target", None) is run_agent_in_background
        ]
        if not background_threads:
            return
        for thread in background_threads:
            thread.join(timeout=0.05)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = get_session_maker()()
    try:
        create_or_reset_admin_user(db, raw_name="admin", password="admin-password")
        db.commit()
    finally:
        db.close()
    yield
    _wait_for_background_agent_threads()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-password"},
        )
        response.raise_for_status()
        test_client.headers["Authorization"] = f"Bearer {response.json()['token']}"
        yield test_client


@pytest.fixture()
def anonymous_client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient):
    def _auth_headers(
        name: str,
        *,
        password: str = "test-password",
        is_admin: bool = False,
    ) -> dict[str, str]:
        db = get_session_maker()()
        try:
            user = find_user_by_name(db, name)
            if user is None:
                if is_admin:
                    user = create_or_reset_admin_user(db, raw_name=name, password=password)
                else:
                    from backend.services.users import create_user_with_unique_name

                    user = create_user_with_unique_name(
                        db,
                        raw_name=name,
                        password=password,
                        is_admin=False,
                    )
            else:
                user.is_admin = is_admin
                user.password_hash = hash_password(password)
                db.add(user)
                db.flush()
            db.commit()
        finally:
            db.close()

        response = client.post(
            "/api/v1/auth/login",
            json={"username": name, "password": password},
        )
        response.raise_for_status()
        return {"Authorization": f"Bearer {response.json()['token']}"}

    return _auth_headers
