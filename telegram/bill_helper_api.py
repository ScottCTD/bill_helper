from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import TypeAdapter

from backend.schemas_agent import AgentRunRead, AgentThreadDetailRead, AgentThreadRead, AgentThreadSummaryRead
from backend.schemas_finance import RuntimeSettingsRead, RuntimeSettingsUpdate
from telegram.config import TelegramSettings


@dataclass(frozen=True, slots=True)
class AttachmentUpload:
    filename: str
    mime_type: str
    content: bytes


class BillHelperApiError(RuntimeError):
    def __init__(self, *, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class BillHelperApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_headers: Mapping[str, str] | None = None,
        auth_token: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_headers = dict(auth_headers or {})
        self._auth_token = auth_token.strip() if auth_token else None
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(
        cls,
        settings: TelegramSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> BillHelperApiClient:
        return cls(
            base_url=settings.backend_base_url,
            auth_headers=settings.backend_auth_headers,
            auth_token=settings.backend_auth_token,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )

    def list_threads(self) -> list[AgentThreadSummaryRead]:
        payload = self._request_json("GET", "/agent/threads")
        return TypeAdapter(list[AgentThreadSummaryRead]).validate_python(payload)

    def create_thread(self, *, title: str | None = None) -> AgentThreadRead:
        payload = self._request_json("POST", "/agent/threads", json_body={"title": title} if title else {})
        return AgentThreadRead.model_validate(payload)

    def get_thread(self, thread_id: str) -> AgentThreadDetailRead:
        payload = self._request_json("GET", f"/agent/threads/{thread_id}")
        return AgentThreadDetailRead.model_validate(payload)

    def get_run(self, run_id: str) -> AgentRunRead:
        payload = self._request_json(
            "GET",
            f"/agent/runs/{run_id}",
            query_params={"surface": "telegram"},
        )
        return AgentRunRead.model_validate(payload)

    def send_thread_message(
        self,
        *,
        thread_id: str,
        content: str = "",
        files: Sequence[AttachmentUpload] = (),
    ) -> AgentRunRead:
        response = self._request(
            "POST",
            f"/agent/threads/{thread_id}/messages",
            files=[
                ("content", (None, content)),
                ("surface", (None, "telegram")),
                *[("files", (upload.filename, upload.content, upload.mime_type)) for upload in files],
            ],
        )
        payload = self._read_json_response(response, expected_status=200)
        return AgentRunRead.model_validate(payload)

    def interrupt_run(self, run_id: str) -> AgentRunRead:
        payload = self._request_json("POST", f"/agent/runs/{run_id}/interrupt", json_body={})
        return AgentRunRead.model_validate(payload)

    def get_settings(self) -> RuntimeSettingsRead:
        payload = self._request_json("GET", "/settings")
        return RuntimeSettingsRead.model_validate(payload)

    def patch_settings(
        self,
        payload: RuntimeSettingsUpdate | Mapping[str, Any],
    ) -> RuntimeSettingsRead:
        request_payload = payload if isinstance(payload, RuntimeSettingsUpdate) else RuntimeSettingsUpdate.model_validate(payload)
        response_payload = self._request_json(
            "PATCH",
            "/settings",
            json_body=request_payload.model_dump(exclude_none=True),
        )
        return RuntimeSettingsRead.model_validate(response_payload)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        query_params: Mapping[str, Any] | None = None,
    ) -> Any:
        response = self._request(method, path, json_body=json_body, query_params=query_params)
        return self._read_json_response(response, expected_status=200 if method != "POST" or path.endswith("/interrupt") else 201)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        query_params: Mapping[str, Any] | None = None,
        files: Sequence[tuple[str, Any]] | None = None,
    ) -> httpx.Response:
        try:
            with httpx.Client(
                headers=self._build_headers(),
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                return client.request(
                    method,
                    self._build_url(path, query_params=query_params),
                    headers={"Accept": "application/json"},
                    json=json_body,
                    files=files,
                )
        except httpx.RequestError as exc:
            raise RuntimeError(f"HTTP request failed: {exc}") from exc

    def _build_url(
        self,
        path: str,
        *,
        query_params: Mapping[str, Any] | None = None,
    ) -> str:
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        if not query_params:
            return url
        filtered = {key: value for key, value in query_params.items() if value is not None}
        if not filtered:
            return url
        return f"{url}?{urlencode(filtered)}"

    def _build_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "bill-helper-telegram"}
        headers.update(self._auth_headers)
        if self._auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def _read_json_response(self, response: httpx.Response, *, expected_status: int) -> Any:
        if response.status_code != expected_status:
            raise BillHelperApiError(status_code=response.status_code, message=self._extract_error_message(response))
        if not response.content or not response.content.strip():
            raise BillHelperApiError(
                status_code=response.status_code,
                message="Bill Helper API returned an empty JSON response.",
            )
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise BillHelperApiError(
                status_code=response.status_code,
                message="Bill Helper API returned invalid JSON.",
            ) from exc

    def _extract_error_message(self, response: httpx.Response) -> str:
        if response.content:
            try:
                parsed = response.json()
            except json.JSONDecodeError:
                return response.text.strip() or "Bill Helper API request failed"
            detail = parsed.get("detail") if isinstance(parsed, dict) else None
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
        return f"Bill Helper API request failed with status {response.status_code}"
