"""Booking 도메인의 확인 경계와 멱등성을 검증합니다."""

from __future__ import annotations

import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from booking_tools import (  # noqa: E402
    BookingStop,
    confirm_booking,
    get_booking_status,
    prepare_booking,
    reset_booking_store,
)


def test_booking_requires_confirmation_and_reuses_confirmation_id() -> None:
    reset_booking_store()
    stops = [
        BookingStop(
            place_id="busan-museum-1",
            name="부산 현대미술관",
            start_time="14:00",
        )
    ]
    first_draft = prepare_booking("course-1", "2026-08-27", 2, stops)
    second_draft = prepare_booking("course-1", "2026-08-27", 2, stops)
    assert first_draft.booking_token == second_draft.booking_token
    assert first_draft.status == "awaiting_confirmation"

    rejected = confirm_booking(first_draft.booking_token, False)
    assert rejected.status == "confirmation_required"
    assert rejected.error_code == "CONFIRMATION_REQUIRED"

    first = confirm_booking(first_draft.booking_token, True)
    second = confirm_booking(first_draft.booking_token, True)
    assert first.status == second.status == "confirmed"
    assert first.confirmation_id == second.confirmation_id
    assert get_booking_status(first_draft.booking_token).status == "confirmed"


def test_unknown_booking_token_is_not_found() -> None:
    reset_booking_store()
    result = get_booking_status("booking-does-not-exist")
    assert result.status == "not_found"
    assert result.error_code == "BOOKING_NOT_FOUND"
