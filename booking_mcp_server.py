"""실제 외부 쓰기 없이 예약 액션 경계를 보여주는 Booking MCP Server입니다."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from booking_tools import (
    BookingActionResult,
    BookingDraftResult,
    BookingStop,
    confirm_booking as confirm_booking_impl,
    get_booking_status as get_booking_status_impl,
    prepare_booking as prepare_booking_impl,
)


mcp = FastMCP(
    "booking-actions",
    instructions=(
        "예약 액션 실습 서버입니다. prepare_booking으로 초안을 만든 뒤 사용자가 "
        "명시적으로 확인한 경우에만 confirm_booking을 호출하세요. 모든 결과는 모의 실행입니다."
    ),
)


@mcp.tool()
def prepare_booking(
    course_id: str,
    date: str,
    party_size: int,
    stops: list[BookingStop],
) -> BookingDraftResult:
    """실제 예약 전에 멱등적인 모의 예약 초안을 만듭니다."""
    return prepare_booking_impl(course_id, date, party_size, stops)


@mcp.tool()
def confirm_booking(
    booking_token: str,
    user_confirmed: bool,
) -> BookingActionResult:
    """사용자가 명시적으로 확인한 예약 초안만 모의 확정합니다."""
    return confirm_booking_impl(booking_token, user_confirmed)


@mcp.tool()
def get_booking_status(booking_token: str) -> BookingActionResult:
    """현재 MCP 프로세스 메모리에 있는 모의 예약 상태를 조회합니다."""
    return get_booking_status_impl(booking_token)


if __name__ == "__main__":
    mcp.run(transport="stdio")
