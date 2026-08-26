"""PLAN.md의 결정론적 Tool 계약에 대한 단위 테스트입니다."""

from __future__ import annotations

import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from date_course_tools import (  # noqa: E402
    CourseStopInput,
    RouteInput,
    UserIntentInput,
    calculate_route,
    estimate_course_budget,
    get_place_details,
    search_places,
    validate_course,
)


def _intent(**overrides):
    values = {
        "companion_type": "couple",
        "location": "부산",
        "date": "2026-08-26",
        "start_time": "14:00",
        "end_time": "21:00",
        "party_size": 2,
        "budget": 100_000,
        "transportation": "public_transport",
        "hard_constraints": [],
        "soft_preferences": ["대화", "카페"],
    }
    values.update(overrides)
    return UserIntentInput(**values)


def _stop(stop_id: str, place_id: str, start: str, end: str, **overrides):
    details = get_place_details(place_id)
    values = {
        "stop_id": stop_id,
        "place_id": place_id,
        "name": details.name,
        "category": details.category,
        "start_time": start,
        "end_time": end,
        "expected_cost": details.estimated_cost_per_person,
        "opening_hours": details.opening_hours,
        "opening_hours_verified": details.opening_hours_verified,
        "indoor": details.indoor,
        "accessible": details.accessible,
    }
    values.update(overrides)
    return CourseStopInput(**values)


def test_place_search_and_route_return_verifiable_metadata() -> None:
    result = search_places("카페", "부산", categories=["cafe"])
    assert [place.place_id for place in result.places] == ["busan-cafe-1"]
    assert result.source == "mock-place-provider"
    assert result.fetched_at.endswith("Z")

    route = calculate_route(
        "busan-cafe-1",
        "busan-restaurant-1",
        "public_transport",
    )
    assert route.error_code is None
    assert route.distance_m and route.distance_m > 0
    assert route.duration_min and route.duration_min > 0


def test_budget_keeps_unknown_price_separate() -> None:
    stops = [
        _stop("stop_1", "busan-cafe-1", "14:00", "15:00"),
        _stop("stop_2", "busan-activity-1", "16:00", "17:00"),
    ]
    result = estimate_course_budget(stops, 2, [4_000], budget_limit=40_000)

    assert result.known_total == 28_000
    assert result.unknown_items == ["stop_2_price"]
    assert result.within_known_budget is True


def test_validator_reports_only_failed_stop_for_closed_place() -> None:
    stops = [
        _stop("stop_1", "busan-cafe-1", "14:00", "15:00"),
        _stop(
            "stop_2",
            "busan-museum-1",
            "19:00",
            "20:00",
            route_from_previous=RouteInput(
                distance_m=1_000,
                duration_min=20,
                walking_distance_m=300,
                transportation="public_transport",
            ),
        ),
    ]
    result = validate_course(_intent(), stops)

    assert result.valid is False
    closed = [issue for issue in result.errors if issue.code == "CLOSED_AT_VISIT_TIME"]
    assert [issue.stop_id for issue in closed] == ["stop_2"]
    assert not any(issue.stop_id == "stop_1" for issue in result.errors)


def test_rainy_indoor_hard_constraint_is_not_offset_by_preference() -> None:
    outdoor = _stop("stop_2", "busan-night-1", "19:00", "20:00")
    result = validate_course(
        _intent(
            hard_constraints=["비 오면 실내"],
            soft_preferences=["야경"],
            weather_condition="rain",
        ),
        [outdoor],
    )

    assert result.valid is False
    assert any(
        issue.code == "INDOOR_CONSTRAINT_VIOLATION" and issue.stop_id == "stop_2"
        for issue in result.errors
    )


def test_validator_checks_party_budget_and_unknown_price() -> None:
    stops = [
        _stop("stop_1", "busan-restaurant-1", "14:00", "15:00"),
        _stop("stop_2", "busan-activity-1", "16:00", "17:00"),
    ]
    result = validate_course(_intent(budget=40_000), stops)

    assert result.known_total_cost == 48_000
    assert result.unknown_costs == ["stop_2_price"]
    assert any(issue.code == "KNOWN_BUDGET_EXCEEDED" for issue in result.errors)
    assert any(issue.code == "PRICE_UNKNOWN" for issue in result.warnings)
