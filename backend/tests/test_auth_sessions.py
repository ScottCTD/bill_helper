from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from fastapi.testclient import TestClient

from backend.database import get_session_maker
from backend.models_finance import UserSession
from backend.routers import admin as admin_router
from backend.routers import auth as auth_router
from backend.services.passwords import password_reset_required_hash
from backend.services.sessions import create_session, utc_now
from backend.services.users import create_user_with_unique_name, find_user_by_name


def _login(client: TestClient, *, username: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def test_logout_revokes_current_session_and_blocks_token_reuse(client):
    me_response = client.get("/api/v1/auth/me")
    me_response.raise_for_status()
    session_id = me_response.json()["session_id"]

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 204

    revoked_response = client.get("/api/v1/auth/me")
    assert revoked_response.status_code == 401
    assert revoked_response.json()["detail"] == "Invalid or expired session."

    db = get_session_maker()()
    try:
        assert db.get(UserSession, session_id) is None
    finally:
        db.close()


def test_login_triggers_best_effort_workspace_start(anonymous_client, monkeypatch):
    started_user_ids: list[str] = []
    monkeypatch.setattr(
        auth_router,
        "queue_best_effort_user_workspace_start",
        lambda *, user_id: started_user_ids.append(user_id),
    )

    response = _login(
        anonymous_client,
        username="admin",
        password="admin-password",
    )

    response.raise_for_status()
    assert started_user_ids == [response.json()["user"]["id"]]


def test_admin_can_revoke_another_users_session(client, anonymous_client):
    create_response = client.post(
        "/api/v1/admin/users",
        json={"name": "alice", "password": "alice-password"},
    )
    create_response.raise_for_status()

    login_response = _login(
        anonymous_client,
        username="alice",
        password="alice-password",
    )
    login_response.raise_for_status()
    user_headers = {
        "Authorization": f"Bearer {login_response.json()['token']}",
    }

    me_response = anonymous_client.get("/api/v1/auth/me", headers=user_headers)
    me_response.raise_for_status()
    session_id = me_response.json()["session_id"]

    sessions_response = client.get("/api/v1/admin/sessions")
    sessions_response.raise_for_status()
    assert any(
        session["id"] == session_id and session["user_name"] == "alice"
        for session in sessions_response.json()
    )

    revoke_response = client.delete(f"/api/v1/admin/sessions/{session_id}")
    assert revoke_response.status_code == 204

    revoked_response = anonymous_client.get("/api/v1/auth/me", headers=user_headers)
    assert revoked_response.status_code == 401
    assert revoked_response.json()["detail"] == "Invalid or expired session."


def test_logout_stops_workspace_only_when_last_session_is_revoked(anonymous_client, monkeypatch):
    stopped_user_ids: list[str] = []
    monkeypatch.setattr(
        auth_router,
        "queue_best_effort_user_workspace_stop",
        lambda *, user_id: stopped_user_ids.append(user_id),
    )

    first_login = _login(
        anonymous_client,
        username="admin",
        password="admin-password",
    )
    second_login = _login(
        anonymous_client,
        username="admin",
        password="admin-password",
    )
    first_login.raise_for_status()
    second_login.raise_for_status()

    first_headers = {"Authorization": f"Bearer {first_login.json()['token']}"}
    second_headers = {"Authorization": f"Bearer {second_login.json()['token']}"}

    first_logout = anonymous_client.post("/api/v1/auth/logout", headers=first_headers)
    assert first_logout.status_code == 204
    assert stopped_user_ids == []

    second_logout = anonymous_client.post("/api/v1/auth/logout", headers=second_headers)
    assert second_logout.status_code == 204
    assert stopped_user_ids == [second_login.json()["user"]["id"]]


def test_admin_login_as_returns_impersonation_session_with_target_scope(
    client,
    anonymous_client,
    monkeypatch,
):
    started_user_ids: list[str] = []
    monkeypatch.setattr(
        admin_router,
        "queue_best_effort_user_workspace_start",
        lambda *, user_id: started_user_ids.append(user_id),
    )
    create_response = client.post(
        "/api/v1/admin/users",
        json={"name": "alice", "password": "alice-password"},
    )
    create_response.raise_for_status()
    alice = create_response.json()

    login_as_response = client.post(f"/api/v1/admin/users/{alice['id']}/login-as")
    login_as_response.raise_for_status()
    payload = login_as_response.json()

    assert payload["user"]["id"] == alice["id"]
    assert payload["user"]["name"] == "alice"
    assert payload["user"]["is_admin"] is False
    assert payload["is_admin_impersonation"] is True
    assert payload["session_id"] is not None

    impersonation_headers = {
        "Authorization": f"Bearer {payload['token']}",
    }

    me_response = anonymous_client.get("/api/v1/auth/me", headers=impersonation_headers)
    me_response.raise_for_status()
    me_payload = me_response.json()
    assert me_payload["user"]["name"] == "alice"
    assert me_payload["is_admin_impersonation"] is True

    users_response = anonymous_client.get("/api/v1/users", headers=impersonation_headers)
    users_response.raise_for_status()
    assert [user["name"] for user in users_response.json()] == ["alice"]

    admin_response = anonymous_client.get("/api/v1/admin/users", headers=impersonation_headers)
    assert admin_response.status_code == 403
    assert admin_response.json()["detail"] == "Only admin principal can access this resource."
    assert started_user_ids == [alice["id"]]


def test_change_password_rotates_login_credentials(client, anonymous_client):
    create_response = client.post(
        "/api/v1/admin/users",
        json={"name": "alice", "password": "alice-password"},
    )
    create_response.raise_for_status()

    login_response = _login(
        anonymous_client,
        username="alice",
        password="alice-password",
    )
    login_response.raise_for_status()
    headers = {"Authorization": f"Bearer {login_response.json()['token']}"}

    change_response = anonymous_client.post(
        "/api/v1/users/me/change-password",
        json={
            "current_password": "alice-password",
            "new_password": "new-secret-password",
        },
        headers=headers,
    )
    assert change_response.status_code == 204

    old_login_response = _login(
        anonymous_client,
        username="alice",
        password="alice-password",
    )
    assert old_login_response.status_code == 403
    assert old_login_response.json()["detail"] == "Invalid username or password."

    new_login_response = _login(
        anonymous_client,
        username="alice",
        password="new-secret-password",
    )
    new_login_response.raise_for_status()
    assert new_login_response.json()["user"]["name"] == "alice"


def test_login_rejects_users_marked_for_password_reset(anonymous_client):
    db = get_session_maker()()
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="alice",
            password="temporary-password",
        )
        user.password_hash = password_reset_required_hash()
        db.add(user)
        db.commit()
    finally:
        db.close()

    response = _login(
        anonymous_client,
        username="alice",
        password="temporary-password",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Password reset is required for this user."


def test_auth_me_accepts_session_rows_with_naive_expiry_timestamps(anonymous_client):
    db = get_session_maker()()
    try:
        user = create_user_with_unique_name(
            db,
            raw_name="naive-expiry-user",
            password="ignored-password",
        )
        token, session_row = create_session(
            db,
            user=user,
            expires_at=utc_now() + timedelta(minutes=10),
        )
        session_row.expires_at = session_row.expires_at.replace(tzinfo=None)
        db.add(session_row)
        db.commit()
    finally:
        db.close()

    response = anonymous_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    response.raise_for_status()
    assert response.json()["user"]["name"] == "naive-expiry-user"

def test_logout_removes_current_session_from_admin_session_listing(
    client,
    anonymous_client,
):
    login_response = _login(
        anonymous_client,
        username="admin",
        password="admin-password",
    )
    login_response.raise_for_status()
    headers = {"Authorization": f"Bearer {login_response.json()['token']}"}

    me_response = anonymous_client.get("/api/v1/auth/me", headers=headers)
    me_response.raise_for_status()
    session_id = me_response.json()["session_id"]

    logout_response = anonymous_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    sessions_response = client.get("/api/v1/admin/sessions")
    sessions_response.raise_for_status()
    assert all(session["id"] != session_id for session in sessions_response.json())

    db = get_session_maker()()
    try:
        session_ids = list(db.scalars(select(UserSession.id)))
    finally:
        db.close()
    assert session_id not in session_ids


def test_admin_session_revoke_stops_workspace_when_last_session_disappears(client, anonymous_client, monkeypatch):
    stopped_user_ids: list[str] = []
    monkeypatch.setattr(
        admin_router,
        "queue_best_effort_user_workspace_stop",
        lambda *, user_id: stopped_user_ids.append(user_id),
    )

    create_response = client.post(
        "/api/v1/admin/users",
        json={"name": "alice", "password": "alice-password"},
    )
    create_response.raise_for_status()
    alice = create_response.json()

    alice_login = _login(
        anonymous_client,
        username="alice",
        password="alice-password",
    )
    alice_login.raise_for_status()
    alice_headers = {"Authorization": f"Bearer {alice_login.json()['token']}"}
    me_response = anonymous_client.get("/api/v1/auth/me", headers=alice_headers)
    me_response.raise_for_status()

    revoke_response = client.delete(f"/api/v1/admin/sessions/{me_response.json()['session_id']}")

    assert revoke_response.status_code == 204
    assert stopped_user_ids == [alice["id"]]
