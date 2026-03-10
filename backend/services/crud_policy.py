from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from starlette import status


TName = TypeVar("TName")


@dataclass(slots=True)
class PolicyViolation(Exception):
    detail: str
    status_code: int

    @classmethod
    def bad_request(cls, detail: str) -> PolicyViolation:
        return cls(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)

    @classmethod
    def conflict(cls, detail: str) -> PolicyViolation:
        return cls(detail=detail, status_code=status.HTTP_409_CONFLICT)

    @classmethod
    def forbidden(cls, detail: str) -> PolicyViolation:
        return cls(detail=detail, status_code=status.HTTP_403_FORBIDDEN)

    @classmethod
    def not_found(cls, detail: str) -> PolicyViolation:
        return cls(detail=detail, status_code=status.HTTP_404_NOT_FOUND)
def normalize_required_name(
    raw_name: str | None,
    *,
    normalizer: Callable[[str], str],
    empty_detail: str,
) -> str:
    normalized = normalizer(raw_name or "")
    if not normalized:
        raise PolicyViolation.bad_request(empty_detail)
    return normalized


def assert_unique_name(
    *,
    existing_id: TName | None,
    current_id: TName | None,
    conflict_detail: str,
) -> None:
    if existing_id is None:
        return
    if current_id is not None and existing_id == current_id:
        return
    raise PolicyViolation.conflict(conflict_detail)


def map_value_error(
    error: ValueError,
    *,
    not_found_patterns: Iterable[str] = (),
    conflict_patterns: Iterable[str] = (),
) -> PolicyViolation:
    message = str(error)
    lowered = message.lower()
    if any(pattern.lower() in lowered for pattern in not_found_patterns):
        return PolicyViolation.not_found(message)
    if any(pattern.lower() in lowered for pattern in conflict_patterns):
        return PolicyViolation.conflict(message)
    return PolicyViolation.bad_request(message)
