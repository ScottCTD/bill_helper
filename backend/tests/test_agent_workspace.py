from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import backend.models_agent  # noqa: F401
import backend.models_files  # noqa: F401
import backend.models_finance  # noqa: F401
import backend.models_settings  # noqa: F401
from backend.main import create_app
from backend.auth.contracts import RequestPrincipal
from backend.config import get_settings
from backend.contracts_users import UserCreateCommand
from backend.database import get_engine, get_session_maker
from backend.db_meta import Base
from backend.services import docker_cli
from backend.services.agent_workspace import (
    WORKSPACE_CONTAINER_REVISION,
    _mount_source_matches_expected,
    build_user_workspace_spec,
    ensure_user_workspace_provisioned,
    remove_user_workspace,
    start_user_workspace,
    stop_user_workspace,
)
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    delete_user_file_root,
    store_user_file_bytes,
)
from backend.services.workspace_ide import WORKSPACE_IDE_SESSION_COOKIE_NAME

pytestmark = pytest.mark.workspace_docker
from backend.services.workspace_browser import build_user_workspace_snapshot
from backend.services.users import (
    create_or_reset_admin_user,
    create_user_for_admin,
    delete_user_for_admin,
)


def _docker_available() -> bool:
    docker_binary = shutil.which("docker")
    if docker_binary is None:
        return False
    result = subprocess.run(
        [docker_binary, "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def test_mount_source_match_accepts_docker_desktop_host_prefix() -> None:
    expected = Path("/Users/scottcui/.local/share/bill_helper/user_files/user-1")

    assert _mount_source_matches_expected(  # noqa: SLF001
        mount_source="/host_mnt/Users/scottcui/.local/share/bill_helper/user_files/user-1",
        expected_source=expected,
    )
    assert not _mount_source_matches_expected(  # noqa: SLF001
        mount_source="/host_mnt/Users/scottcui/.local/share/bill-helper/user_files/user-1",
        expected_source=expected,
    )


@lru_cache(maxsize=1)
def _build_workspace_test_image() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    image_tag = "bill-helper-agent-workspace:test"
    result = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            image_tag,
            "-f",
            "docker/agent-workspace.dockerfile",
            ".",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "docker build failed")
    return image_tag


@pytest.fixture()
def workspace_session(tmp_path, monkeypatch):
    if not _docker_available():
        pytest.skip("Docker is unavailable.")

    image_tag = _build_workspace_test_image()
    data_dir = tmp_path / "data"
    database_path = tmp_path / "workspace.sqlite"
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BILL_HELPER_DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_IMAGE", image_tag)
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_DOCKER_BINARY", "docker")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_maker.cache_clear()

    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.close()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_maker.cache_clear()


def test_bootstrap_and_admin_user_create_provision_named_workspace_resources(workspace_session: Session):
    admin = create_or_reset_admin_user(
        workspace_session,
        raw_name="admin",
        password="admin-password",
    )
    workspace_session.commit()
    admin_principal = RequestPrincipal(
        user_id=admin.id,
        user_name=admin.name,
        is_admin=True,
    )

    created_user = create_user_for_admin(
        workspace_session,
        command=UserCreateCommand(name="alice", password="alice-password", is_admin=False),
        principal=admin_principal,
    )
    workspace_session.commit()

    admin_spec = build_user_workspace_spec(user_id=admin.id)
    user_spec = build_user_workspace_spec(user_id=created_user.id)
    try:
        inspected = docker_cli.inspect_container(
            docker_binary="docker",
            container_name=user_spec.container_name,
        )
        mounts = inspected.get("Mounts", [])
        config = inspected.get("Config", {})
        labels = config.get("Labels", {}) if isinstance(config, dict) else {}
        assert admin_spec.data_bind_source.exists()
        assert user_spec.data_bind_source.exists()
        assert docker_cli.container_exists(docker_binary="docker", container_name=admin_spec.container_name)
        assert docker_cli.container_exists(docker_binary="docker", container_name=user_spec.container_name)
        assert labels.get("bill-helper.user-id") == created_user.id
        assert labels.get("bill-helper.workspace-revision") == WORKSPACE_CONTAINER_REVISION
        assert any(mount.get("Name") == user_spec.volume_name for mount in mounts if isinstance(mount, dict))
        assert any(
            mount.get("Type") == "bind"
            and mount.get("Destination") == "/data"
            and mount.get("RW") is False
            for mount in mounts
            if isinstance(mount, dict)
        )
        assert not any(
            mount.get("Type") == "bind" and mount.get("Destination") == "/workspace/user_data"
            for mount in mounts
            if isinstance(mount, dict)
        )

        delete_user_for_admin(
            workspace_session,
            user_id=created_user.id,
            principal=admin_principal,
        )
        workspace_session.commit()

        assert not user_spec.data_bind_source.exists()
        assert not docker_cli.container_exists(docker_binary="docker", container_name=user_spec.container_name)
    finally:
        remove_user_workspace(user_id=created_user.id)
        delete_user_file_root(user_id=created_user.id)
        remove_user_workspace(user_id=admin.id)
        delete_user_file_root(user_id=admin.id)


def test_workspace_container_mounts_data_read_only_and_workspace_persists(workspace_session: Session):
    admin = create_or_reset_admin_user(
        workspace_session,
        raw_name="admin",
        password="admin-password",
    )
    workspace_session.commit()

    uploaded = store_user_file_bytes(
        workspace_session,
        owner_user_id=admin.id,
        storage_area=STORAGE_AREA_UPLOAD,
        source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
        mime_type="text/plain",
        file_bytes=b"read-only evidence",
        original_filename="evidence.txt",
    )
    workspace_session.commit()

    spec = start_user_workspace(user_id=admin.id)
    uploaded_name = Path(uploaded.stored_relative_path).name
    try:
        inspected = docker_cli.inspect_container(
            docker_binary="docker",
            container_name=spec.container_name,
        )
        host_port = docker_cli.container_host_port(inspected=inspected, container_port=spec.ide_port)
        assert host_port is not None
        response = httpx.get(f"http://127.0.0.1:{host_port}/", follow_redirects=False, timeout=5.0)
        assert response.status_code in {200, 302}

        docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", f"test -f /data/uploads/{uploaded_name}"],
        )
        with pytest.raises(docker_cli.DockerCliError):
            docker_cli.exec_in_container(
                docker_binary="docker",
                container_name=spec.container_name,
                command=["bash", "-lc", "echo no >/data/uploads/should-fail.txt"],
            )

        docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "echo persisted >/workspace/workspace/persist.txt"],
        )
        docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "test ! -e /data/bill_helper.db"],
        )
    finally:
        stop_user_workspace(user_id=admin.id)

    start_user_workspace(user_id=admin.id)
    try:
        persisted = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "cat /workspace/workspace/persist.txt"],
        )
        code_server_settings = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "cat /workspace/.ide/code-server/User/settings.json"],
        )
        installed_extensions = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "code-server --list-extensions --extensions-dir /workspace/.ide/extensions | sort"],
        )
        obsolete_extensions = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "test -f /workspace/.ide/extensions/.obsolete && cat /workspace/.ide/extensions/.obsolete || true"],
        )
        workspace_root_listing = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=[
                "bash",
                "-lc",
                "find /workspace -maxdepth 1 -mindepth 1 ! -name '.*' -printf '%f\\n' | sort",
            ],
        )
        workspace_user_data_link = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "readlink /workspace/user_data"],
        )
        user_data_listing = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=[
                "bash",
                "-lc",
                "find -L /workspace/user_data/uploads -maxdepth 1 -mindepth 1 -printf '%f\\n' | sort",
            ],
        )
        listing = docker_cli.exec_in_container(
            docker_binary="docker",
            container_name=spec.container_name,
            command=["bash", "-lc", "find /data -maxdepth 2 -type f | sort"],
        )
        assert "persisted" in persisted.stdout
        assert '"chat.disableAIFeatures": true' in code_server_settings.stdout
        assert '"chat.agent.enabled": false' in code_server_settings.stdout
        assert '"workbench.startupEditor": "none"' in code_server_settings.stdout
        assert '"workbench.sideBar.location": "right"' in code_server_settings.stdout
        assert '"security.workspace.trust.enabled": false' in code_server_settings.stdout
        assert '"modernPdfViewer.defaultSpreadMode": "none"' in code_server_settings.stdout
        assert "chocolatedesue.modern-pdf-preview" in installed_extensions.stdout
        assert "tomoki1207.pdf" not in installed_extensions.stdout
        assert "modern-pdf-preview" not in obsolete_extensions.stdout
        assert "tomoki1207.pdf" not in obsolete_extensions.stdout
        assert workspace_root_listing.stdout.splitlines() == ["user_data", "workspace"]
        assert workspace_user_data_link.stdout.strip() == "/data/user_data"
        assert user_data_listing.stdout == "evidence.txt\n"
        assert "/data/uploads/" in listing.stdout
        assert "bill_helper.db" not in listing.stdout

        snapshot = build_user_workspace_snapshot(user_id=admin.id)
        assert snapshot.status == "running"
        assert snapshot.ide_ready is True
        assert snapshot.ide_launch_path == "/api/v1/workspace/ide/"
        assert snapshot.degraded_reason is None
    finally:
        stop_user_workspace(user_id=admin.id)
        remove_user_workspace(user_id=admin.id)
        delete_user_file_root(user_id=admin.id)


def test_workspace_ide_session_endpoint_sets_cookie_and_proxies_code_server(workspace_session: Session):
    admin = create_or_reset_admin_user(
        workspace_session,
        raw_name="admin",
        password="admin-password",
    )
    workspace_session.commit()

    try:
        app = create_app()
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "admin-password"},
            )
            login_response.raise_for_status()
            client.headers["Authorization"] = f"Bearer {login_response.json()['token']}"

            ide_response = client.post("/api/v1/workspace/ide/session")

            assert ide_response.status_code == 200
            assert WORKSPACE_IDE_SESSION_COOKIE_NAME in ide_response.headers.get("set-cookie", "")
            assert ide_response.json()["snapshot"]["status"] == "running"
            assert ide_response.json()["snapshot"]["ide_ready"] is True

            proxied_index = client.get("/api/v1/workspace/ide/")

            assert proxied_index.status_code == 200
            assert "text/html" in proxied_index.headers.get("content-type", "")
            assert "code-server" in proxied_index.text.lower()
    finally:
        stop_user_workspace(user_id=admin.id)
        remove_user_workspace(user_id=admin.id)
        delete_user_file_root(user_id=admin.id)
