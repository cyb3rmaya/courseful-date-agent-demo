"""예약 액션 MCP가 사용하는 결정론적 모의 예약 도메인 로직입니다.

이 모듈은 결제, 외부 예약사 호출, 데이터베이스 쓰기를 수행하지 않습니다.
과제의 액션 Tool 경계를 안전하게 확인할 수 있도록 명시적 사용자 확인과
멱등성 키를 강제하고 프로세스 메모리에만 상태를 보관합니다.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field


BookingStatus = Literal[
    "awaiting_confirmation",
    "confirmed",
    "confirmation_required",
    "not_found",
]


class BookingStop(BaseModel):
    place_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    start_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class BookingDraftResult(BaseModel):
    booking_token: str
    course_id: str
    date: str
    party_size: int
    stops: list[BookingStop]
    status: Literal["awaiting_confirmation"] = "awaiting_confirmation"
    source: Literal["simulated-booking-memory"] = "simulated-booking-memory"
    warning: str = "모의 예약이며 실제 예약·결제·DB 저장은 수행되지 않습니다."
    error_code: str | None = None


class BookingActionResult(BaseModel):
    booking_token: str
    confirmation_id: str | None = None
    status: BookingStatus
    source: Literal["simulated-booking-memory"] = "simulated-booking-memory"
    message: str
    error_code: str | None = None


_BOOKINGS: dict[str, dict] = {}


def _valid_date(value: str) -> str:
    date_type.fromisoformat(value)
    return value


def _stable_id(prefix: str, payload: dict) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def prepare_booking(
    course_id: str,
    date: str,
    party_size: int,
    stops: list[BookingStop],
) -> BookingDraftResult:
    """확정 전 예약 초안을 만들고 재호출에도 같은 token을 반환합니다."""
    if not course_id.strip():
        raise ValueError("course_id가 필요합니다.")
    if party_size not in range(1, 11):
        raise ValueError("party_size는 1명에서 10명 사이여야 합니다.")
    if not 1 <= len(stops) <= 6:
        raise ValueError("예약할 장소는 1곳에서 6곳 사이여야 합니다.")
    normalized_date = _valid_date(date)
    normalized_stops = [BookingStop.model_validate(stop) for stop in stops]
    payload = {
        "course_id": course_id.strip(),
        "date": normalized_date,
        "party_size": party_size,
        "stops": [stop.model_dump() for stop in normalized_stops],
    }
    token = _stable_id("booking", payload)
    _BOOKINGS.setdefault(
        token,
        {
            **payload,
            "status": "awaiting_confirmation",
            "confirmation_id": None,
        },
    )
    return BookingDraftResult(booking_token=token, **payload)


def confirm_booking(
    booking_token: str,
    user_confirmed: bool,
) -> BookingActionResult:
    """명시적 확인이 있을 때만 모의 예약을 확정합니다."""
    record = _BOOKINGS.get(booking_token)
    if record is None:
        return BookingActionResult(
            booking_token=booking_token,
            status="not_found",
            message="예약 초안을 찾을 수 없습니다.",
            error_code="BOOKING_NOT_FOUND",
        )
    if not user_confirmed:
        return BookingActionResult(
            booking_token=booking_token,
            status="confirmation_required",
            message="예약 액션을 실행하려면 사용자의 명시적 확인이 필요합니다.",
            error_code="CONFIRMATION_REQUIRED",
        )
    if record["status"] != "confirmed":
        confirmation_id = _stable_id(
            "sim-confirm",
            {"booking_token": booking_token, "course_id": record["course_id"]},
        )
        record["status"] = "confirmed"
        record["confirmation_id"] = confirmation_id
        # stdio MCP의 stdout은 프로토콜 전용이므로 실습 로그는 stderr로 보냅니다.
        print(
            json.dumps(
                {
                    "event": "simulated_booking_confirmed",
                    "booking_token": booking_token,
                    "confirmation_id": confirmation_id,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
    return BookingActionResult(
        booking_token=booking_token,
        confirmation_id=record["confirmation_id"],
        status="confirmed",
        message="모의 예약이 확정되었습니다. 실제 예약이나 결제는 발생하지 않았습니다.",
    )


def get_booking_status(booking_token: str) -> BookingActionResult:
    record = _BOOKINGS.get(booking_token)
    if record is None:
        return BookingActionResult(
            booking_token=booking_token,
            status="not_found",
            message="예약 초안을 찾을 수 없습니다.",
            error_code="BOOKING_NOT_FOUND",
        )
    if record["status"] == "confirmed":
        return BookingActionResult(
            booking_token=booking_token,
            confirmation_id=record["confirmation_id"],
            status="confirmed",
            message="모의 예약이 확정된 상태입니다.",
        )
    return BookingActionResult(
        booking_token=booking_token,
        status="awaiting_confirmation",
        message="사용자 확인을 기다리는 예약 초안입니다.",
    )


def reset_booking_store() -> None:
    """테스트 격리를 위한 메모리 저장소 초기화 함수입니다."""
    _BOOKINGS.clear()


__all__ = [
    "BookingActionResult",
    "BookingDraftResult",
    "BookingStop",
    "confirm_booking",
    "get_booking_status",
    "prepare_booking",
    "reset_booking_store",
]
