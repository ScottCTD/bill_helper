#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import ensure_env_file_variables_loaded  # noqa: E402


BACKEND_LOG_NAME = "backend"
FRONTEND_LOG_NAME = "frontend"
TELEGRAM_LOG_NAME = "telegram"
SHUTDOWN_GRACE_SECONDS = 5.0
POLL_INTERVAL_SECONDS = 0.2
VITE_CACHE_DIR = ROOT_DIR / "frontend" / "node_modules" / ".vite"

STAMP_CHECK_CODE = (
    "from backend.database import build_engine, build_session_maker; "
    "from backend.services.bootstrap import should_stamp_existing_schema; "
    "eng = build_engine(); "
    "SessionLocal = build_session_maker(eng); "
    "db = SessionLocal(); "
    "should_stamp = should_stamp_existing_schema(db); "
    "db.close(); "
    "eng.dispose(); "
    "raise SystemExit(0 if should_stamp else 1)"
)
SEED_CHECK_CODE = (
    "from backend.database import build_engine, build_session_maker; "
    "from backend.services.bootstrap import should_seed_demo_data; "
    "eng = build_engine(); "
    "SessionLocal = build_session_maker(eng); "
    "db = SessionLocal(); "
    "should_seed = should_seed_demo_data(db); "
    "db.close(); "
    "eng.dispose(); "
    "raise SystemExit(0 if should_seed else 1)"
)


@dataclass(slots=True)
class ManagedService:
    name: str
    command: list[str]
    cwd: Path
    log_path: Path
    process: subprocess.Popen[str] | None = None
    output_thread: threading.Thread | None = None

    def start(self) -> None:
        print(f"Starting {self.name} (log: {self.log_path})")
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.output_thread = threading.Thread(target=self._stream_output, name=f"{self.name}-log", daemon=True)
        self.output_thread.start()

    @property
    def pid(self) -> int | None:
        return None if self.process is None else self.process.pid

    def poll(self) -> int | None:
        return None if self.process is None else self.process.poll()

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=SHUTDOWN_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=SHUTDOWN_GRACE_SECONDS)
        if self.output_thread is not None:
            self.output_thread.join(timeout=1.0)

    def _stream_output(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", encoding="utf-8") as log_file:
            for line in self.process.stdout:
                prefixed = f"[{self.name}] {line}"
                sys.stdout.write(prefixed)
                sys.stdout.flush()
                log_file.write(prefixed)
                log_file.flush()
            self.process.stdout.close()


@dataclass(slots=True)
class DevUpRunner:
    root_dir: Path
    interrupted: threading.Event = field(default_factory=threading.Event)
    shutting_down: bool = False

    def run(self) -> int:
        ensure_env_file_variables_loaded()
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_dir = self.root_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

        try:
            self._prepare_environment()
            services = self._build_services(timestamp=timestamp, log_dir=log_dir)
            for service in services:
                service.start()

            self._print_service_summary(services)
            return self._wait_for_services(services)
        except subprocess.CalledProcessError as exc:
            return exc.returncode or 1
        except KeyboardInterrupt:
            return 130

    def _prepare_environment(self) -> None:
        print("Checking migration metadata...")
        if self._run_python_check(STAMP_CHECK_CODE) == 0:
            print("Detected existing schema without Alembic revision metadata. Stamping head...")
            self._run_command(["uv", "run", "alembic", "stamp", "head"])

        print("Applying database migrations...")
        self._run_command(["uv", "run", "alembic", "upgrade", "head"])

        print("Checking whether demo seed is needed...")
        if self._run_python_check(SEED_CHECK_CODE) == 0:
            seed_csv = os.getenv("BILL_HELPER_SEED_CREDIT_CSV", "").strip()
            if seed_csv:
                print(f"No accounts found. Seeding demo data from {seed_csv}...")
                self._run_command(["uv", "run", "python", "scripts/seed_demo.py", seed_csv])
            else:
                print("No accounts found but BILL_HELPER_SEED_CREDIT_CSV is not set. Skipping demo seed.")
                print("To seed demo data, set BILL_HELPER_SEED_CREDIT_CSV to a credit-card CSV path and restart.")
        else:
            print("Existing accounts found. Skipping demo seed.")

        print("Syncing frontend dependencies...")
        self._run_command(["npm", "install"], cwd=self.root_dir / "frontend")

        print("Resetting frontend Vite optimized deps cache...")
        shutil.rmtree(VITE_CACHE_DIR, ignore_errors=True)

    def _build_services(self, *, timestamp: str, log_dir: Path) -> list[ManagedService]:
        services = [
            ManagedService(
                name=BACKEND_LOG_NAME,
                command=["uv", "run", "bill-helper-api"],
                cwd=self.root_dir,
                log_path=log_dir / f"{BACKEND_LOG_NAME}-{timestamp}.log",
            ),
            ManagedService(
                name=FRONTEND_LOG_NAME,
                command=["npm", "run", "dev"],
                cwd=self.root_dir / "frontend",
                log_path=log_dir / f"{FRONTEND_LOG_NAME}-{timestamp}.log",
            ),
        ]

        if self._telegram_configured():
            services.append(
                ManagedService(
                    name=TELEGRAM_LOG_NAME,
                    command=["uv", "run", "python", "-m", "telegram.polling"],
                    cwd=self.root_dir,
                    log_path=log_dir / f"{TELEGRAM_LOG_NAME}-{timestamp}.log",
                )
            )
        else:
            print("Skipping telegram startup because TELEGRAM_BOT_TOKEN is not configured.")

        return services

    def _print_service_summary(self, services: list[ManagedService]) -> None:
        service_by_name = {service.name: service for service in services}
        print(f"Backend PID: {service_by_name[BACKEND_LOG_NAME].pid}")
        print(f"Frontend PID: {service_by_name[FRONTEND_LOG_NAME].pid}")
        telegram = service_by_name.get(TELEGRAM_LOG_NAME)
        if telegram is None:
            print("Telegram: skipped")
        else:
            print(f"Telegram PID: {telegram.pid}")
        print("Frontend URL: http://localhost:5173")
        print("Backend API:  http://localhost:8000/api/v1")
        print("Backend Docs: http://localhost:8000/docs")
        print("Press Ctrl+C to stop all started services.")

    def _wait_for_services(self, services: list[ManagedService]) -> int:
        try:
            while True:
                if self.interrupted.is_set():
                    return 130
                for service in services:
                    exit_code = service.poll()
                    if exit_code is None:
                        continue
                    print()
                    print("A service exited unexpectedly. Shutting down all started services...")
                    return exit_code
                time.sleep(POLL_INTERVAL_SECONDS)
        finally:
            self._cleanup(services)

    def _cleanup(self, services: list[ManagedService]) -> None:
        if self.shutting_down:
            return
        self.shutting_down = True

        print()
        print("Stopping services...")
        for service in services:
            service.stop()

    def _handle_interrupt(self, signum: int, _frame: object) -> None:
        del signum
        self.interrupted.set()

    def _run_command(self, command: list[str], *, cwd: Path | None = None) -> None:
        subprocess.run(command, cwd=cwd or self.root_dir, check=True)

    def _run_python_check(self, code: str) -> int:
        completed = subprocess.run([sys.executable, "-c", code], cwd=self.root_dir, check=False)
        return completed.returncode

    def _telegram_configured(self) -> bool:
        token = (
            os.getenv("TELEGRAM_BOT_TOKEN")
            or os.getenv("BILL_HELPER_TELEGRAM_BOT_TOKEN")
            or ""
        ).strip()
        return bool(token)


def main() -> int:
    return DevUpRunner(root_dir=ROOT_DIR).run()


if __name__ == "__main__":
    raise SystemExit(main())
