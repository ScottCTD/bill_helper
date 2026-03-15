# CALLING SPEC:
# - Purpose: implement focused service logic for `docker_cli`.
# - Inputs: callers that import `backend/services/docker_cli.py` and pass module-defined arguments or framework events.
# - Outputs: thin Docker CLI helper functions for image, volume, container, and exec lifecycle work.
# - Side effects: shelling out to the configured Docker binary.
from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess


@dataclass(slots=True)
class DockerCliError(Exception):
    command: list[str]
    exit_code: int
    stderr: str
    stdout: str = ""

    def __str__(self) -> str:
        stderr = self.stderr.strip() or self.stdout.strip() or "docker command failed"
        return f"{' '.join(self.command)}: {stderr}"


def _run_docker(
    *,
    docker_binary: str,
    args: list[str],
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [docker_binary, *args]
    result = subprocess.run(
        command,
        capture_output=capture_output,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DockerCliError(
            command=command,
            exit_code=result.returncode,
            stderr=result.stderr,
            stdout=result.stdout,
        )
    return result


def image_exists(*, docker_binary: str, image: str) -> bool:
    try:
        _run_docker(docker_binary=docker_binary, args=["image", "inspect", image])
        return True
    except DockerCliError:
        return False


def ensure_volume(*, docker_binary: str, volume_name: str) -> None:
    try:
        _run_docker(docker_binary=docker_binary, args=["volume", "inspect", volume_name])
    except DockerCliError:
        _run_docker(docker_binary=docker_binary, args=["volume", "create", volume_name])


def remove_volume_if_exists(*, docker_binary: str, volume_name: str) -> None:
    try:
        _run_docker(docker_binary=docker_binary, args=["volume", "rm", "-f", volume_name])
    except DockerCliError as error:
        if "No such volume" not in error.stderr:
            raise


def container_exists(*, docker_binary: str, container_name: str) -> bool:
    try:
        _run_docker(
            docker_binary=docker_binary,
            args=["container", "inspect", container_name],
        )
        return True
    except DockerCliError:
        return False


def inspect_container(*, docker_binary: str, container_name: str) -> dict[str, object]:
    result = _run_docker(
        docker_binary=docker_binary,
        args=["container", "inspect", container_name],
    )
    payload = json.loads(result.stdout)
    if not payload:
        raise DockerCliError(
            command=[docker_binary, "container", "inspect", container_name],
            exit_code=1,
            stderr="container inspect returned no payload",
        )
    return payload[0]


def remove_container_if_exists(*, docker_binary: str, container_name: str) -> None:
    try:
        _run_docker(
            docker_binary=docker_binary,
            args=["rm", "-f", container_name],
        )
    except DockerCliError as error:
        if "No such container" not in error.stderr:
            raise


def create_container(
    *,
    docker_binary: str,
    container_name: str,
    image: str,
    workspace_volume_name: str,
    data_bind_source: str,
    published_tcp_ports: list[int] | None = None,
    labels: dict[str, str] | None = None,
) -> None:
    args = [
        "create",
        "--name",
        container_name,
        "--workdir",
        "/workspace",
        "--mount",
        f"type=volume,src={workspace_volume_name},dst=/workspace",
        "--mount",
        f"type=bind,src={data_bind_source},dst=/data,readonly",
    ]
    for tcp_port in published_tcp_ports or []:
        args.extend(["--publish", f"127.0.0.1::{tcp_port}/tcp"])
    for key, value in sorted((labels or {}).items()):
        args.extend(["--label", f"{key}={value}"])
    args.append(image)
    _run_docker(docker_binary=docker_binary, args=args)


def start_container(*, docker_binary: str, container_name: str) -> None:
    try:
        _run_docker(docker_binary=docker_binary, args=["start", container_name])
    except DockerCliError as error:
        if "is already running" not in error.stderr:
            raise


def stop_container(*, docker_binary: str, container_name: str) -> None:
    try:
        _run_docker(docker_binary=docker_binary, args=["stop", container_name])
    except DockerCliError as error:
        if "is not running" not in error.stderr and "No such container" not in error.stderr:
            raise


def exec_in_container(
    *,
    docker_binary: str,
    container_name: str,
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return _run_docker(
        docker_binary=docker_binary,
        args=["exec", container_name, *command],
    )


def container_host_port(
    *,
    inspected: dict[str, object],
    container_port: int,
    protocol: str = "tcp",
) -> int | None:
    network_settings = inspected.get("NetworkSettings")
    if not isinstance(network_settings, dict):
        return None
    ports = network_settings.get("Ports")
    if not isinstance(ports, dict):
        return None
    bindings = ports.get(f"{container_port}/{protocol}")
    if not isinstance(bindings, list) or not bindings:
        return None
    binding = bindings[0]
    if not isinstance(binding, dict):
        return None
    host_port = binding.get("HostPort")
    if not isinstance(host_port, str) or not host_port:
        return None
    try:
        return int(host_port)
    except ValueError:
        return None
