# CALLING SPEC:
# - Purpose: enable LiteLLM's Langfuse OpenTelemetry callback when Langfuse API keys are present, build per-request metadata, and flush OTLP spans (Langfuse uses a non-global TracerProvider).
# - Inputs: environment variables after `ensure_env_file_variables_loaded`; agent run/thread identifiers from the runtime loop.
# - Outputs: `ensure_langfuse_litellm_configured`, `force_flush_langfuse_otel_best_effort`, `agent_run_litellm_metadata`, and `langfuse_credentials_configured`.
# - Side effects: may append `"langfuse_otel"` to `litellm.callbacks` once per process; may instantiate LiteLLM's LangfuseOtelLogger eagerly.
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import litellm

from backend.config import ensure_env_file_variables_loaded

logger = logging.getLogger(__name__)

_configure_lock = threading.Lock()
_langfuse_callback_installed = False


def langfuse_credentials_configured() -> bool:
    ensure_env_file_variables_loaded()
    public_key = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()
    return bool(public_key and secret_key)


def _langfuse_otel_base_path_for_logging() -> str:
    """Match LiteLLM's LangfuseOtelLogger endpoint base (before `/v1/traces` is appended)."""
    host = (os.environ.get("LANGFUSE_OTEL_HOST") or os.environ.get("LANGFUSE_HOST") or "").strip()
    if host:
        if not host.startswith("http"):
            host = "https://" + host
        return f"{host.rstrip('/')}/api/public/otel"
    return "https://us.cloud.langfuse.com/api/public/otel"


def ensure_langfuse_litellm_configured() -> None:
    """Register LiteLLM's Langfuse OTEL callback when keys are set (idempotent)."""
    global _langfuse_callback_installed
    if _langfuse_callback_installed:
        return
    if not langfuse_credentials_configured():
        return
    with _configure_lock:
        if _langfuse_callback_installed:
            return
        if "langfuse_otel" not in litellm.callbacks:
            litellm.callbacks.append("langfuse_otel")
        # Eager-init: LiteLLM swallows init failures in _init_custom_logger_compatible_class (returns None).
        # Without this, missing OTEL deps or bad keys fail silently until LITELLM_LOG=DEBUG.
        from litellm.litellm_core_utils.litellm_logging import (
            _init_custom_logger_compatible_class,
        )

        _otel = _init_custom_logger_compatible_class(
            "langfuse_otel",
            internal_usage_cache=None,
            llm_router=None,
        )
        if _otel is None:
            logger.error(
                "Langfuse OTEL callback did not initialize. "
                "Check LiteLLM stderr for '[Non-Blocking Error] Error initializing custom logger'. "
                "Confirm opentelemetry-exporter-otlp-proto-http is installed and LANGFUSE_PUBLIC_KEY / "
                "LANGFUSE_SECRET_KEY match your Langfuse project."
            )
        _langfuse_callback_installed = True
        endpoint_base = _langfuse_otel_base_path_for_logging()
        logger.info(
            "Langfuse observability enabled for agent LLM calls (LiteLLM langfuse_otel); "
            "OTLP trace base %s (OpenTelemetry appends /v1/traces). "
            "EU cloud: set LANGFUSE_OTEL_HOST=https://cloud.langfuse.com — LiteLLM defaults to US.",
            endpoint_base,
        )


def force_flush_langfuse_otel_best_effort() -> None:
    """Flush Langfuse-bound OTLP spans.

    LiteLLM's Langfuse integration sets ``skip_set_global`` on the TracerProvider, so the
    global ``trace.get_tracer_provider().force_flush()`` does nothing. Batched exports can
    otherwise take several seconds to appear in Langfuse.
    """
    if not langfuse_credentials_configured():
        return
    try:
        from litellm.integrations.langfuse.langfuse_otel import LangfuseOtelLogger
        from litellm.litellm_core_utils import litellm_logging as litellm_logging_mod

        for cb in getattr(litellm_logging_mod, "_in_memory_loggers", []):
            if isinstance(cb, LangfuseOtelLogger):
                tracer = getattr(cb, "tracer", None)
                provider = getattr(tracer, "_tracer_provider", None) if tracer is not None else None
                if provider is not None and hasattr(provider, "force_flush"):
                    provider.force_flush(timeout_millis=5000)
                return
    except Exception:
        logger.debug("Langfuse OTEL force_flush skipped", exc_info=True)


def agent_run_litellm_metadata(
    *,
    run_id: str,
    thread_id: str,
    owner_user_id: str | None,
    step_index: int,
    surface: str,
) -> dict[str, Any]:
    """Metadata keys understood by Langfuse via LiteLLM OTEL (see Langfuse LiteLLM integration docs)."""
    tags = ["agent", surface]
    meta: dict[str, Any] = {
        "trace_id": run_id,
        "session_id": thread_id,
        "generation_name": f"agent-step-{step_index}",
        "tags": tags,
    }
    if owner_user_id:
        # LiteLLM maps `trace_user_id` to Langfuse user correlation (not plain `user_id`).
        meta["trace_user_id"] = owner_user_id
    return meta
