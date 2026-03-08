from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(slots=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None
    timeout_seconds: float = 30.0


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


type HttpTransport = Callable[[HttpRequest], HttpResponse]


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def urllib_transport(request: HttpRequest) -> HttpResponse:
    raw_request = Request(
        request.url,
        data=request.body,
        headers=request.headers,
        method=request.method,
    )
    try:
        with urlopen(raw_request, timeout=request.timeout_seconds) as response:
            return HttpResponse(
                status_code=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except HTTPError as exc:
        return HttpResponse(
            status_code=exc.code,
            headers=dict(exc.headers.items()),
            body=exc.read(),
        )
    except URLError as exc:
        reason = exc.reason if isinstance(exc.reason, str) else repr(exc.reason)
        raise RuntimeError(f"HTTP request failed: {reason}") from exc