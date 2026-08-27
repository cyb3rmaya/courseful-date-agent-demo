"""무료 공개 배포용 Date Course Mock Agent FastAPI 애플리케이션입니다.

공개 서버에서 유료 LLM Key가 악용되지 않도록 이 웹 앱은 결정론적 Mock Tool만
사용합니다. 실제 OpenAI + MCP Agent 실행은 ``06_mcp_call.py``에 그대로 분리되어
있습니다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date as date_type
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from _multi_mcp_client import connect_to_mcp_servers
from booking_tools import BookingStop
from date_course_tools import (
    CourseStopInput,
    PlaceDetailsResult,
    RouteInput,
    TourismCategory,
    UserIntentInput,
    calculate_route,
    get_place_details,
    get_tourist_attractions,
    get_weather,
    search_date_context,
    search_places,
    validate_course,
)


STATIC_DIR = Path(__file__).with_name("static")
VISIT_MINUTES = {
    "cafe": 60,
    "restaurant": 75,
    "museum": 75,
    "activity": 75,
    "night_view": 60,
    "walk": 60,
    "nature": 70,
    "heritage": 75,
    "landmark": 70,
}
CATEGORY_LABELS = {
    "cafe": "카페",
    "restaurant": "식사",
    "museum": "문화",
    "activity": "체험",
    "night_view": "야경",
    "walk": "산책",
    "nature": "자연",
    "heritage": "역사",
    "landmark": "명소",
}


class CourseRequest(BaseModel):
    request: str = Field(default="", max_length=800)
    location: Literal["부산", "서울"] = "부산"
    companion_type: Literal["couple", "family", "friends"] = "couple"
    date: str
    start_time: str = "14:00"
    end_time: str = "21:00"
    party_size: int = Field(default=2, ge=1, le=10)
    budget: int = Field(default=100_000, ge=0, le=5_000_000)
    transportation: Literal["walking", "public_transport", "car"] = (
        "public_transport"
    )
    hard_constraints: list[str] = Field(default_factory=list, max_length=10)
    soft_preferences: list[str] = Field(default_factory=list, max_length=10)
    tourism_categories: list[TourismCategory] = Field(
        default_factory=list,
        max_length=4,
    )
    max_walking_distance_m: int | None = Field(default=None, ge=0, le=100_000)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        date_type.fromisoformat(value)
        return value

    @field_validator("start_time", "end_time")
    @classmethod
    def valid_time(cls, value: str) -> str:
        _minutes(value)
        return value


class BookingRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=120)
    date: str
    party_size: int = Field(ge=1, le=10)
    stops: list[BookingStop] = Field(min_length=1, max_length=6)
    user_confirmed: bool = False

    @field_validator("date")
    @classmethod
    def valid_booking_date(cls, value: str) -> str:
        date_type.fromisoformat(value)
        return value


def _minutes(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("시간은 HH:MM 형식이어야 합니다.")
    hour, minute = map(int, parts)
    if hour not in range(24) or minute not in range(60):
        raise ValueError("올바른 시간을 입력해 주세요.")
    return hour * 60 + minute


def _clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _course_id(payload: CourseRequest, stops: list[CourseStopInput]) -> str:
    canonical = json.dumps(
        {
            "location": payload.location,
            "date": payload.date,
            "party_size": payload.party_size,
            "stops": [
                {
                    "place_id": stop.place_id,
                    "start_time": stop.start_time,
                    "end_time": stop.end_time,
                }
                for stop in stops
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "course-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _opening_range(details: PlaceDetailsResult) -> tuple[int, int] | None:
    if not details.opening_hours_verified or not details.opening_hours:
        return None
    try:
        opened, closed = details.opening_hours.split("-", maxsplit=1)
        return _minutes(opened), _minutes(closed)
    except ValueError:
        return None


def _preferred_categories(preferences: list[str]) -> set[str]:
    aliases = {
        "카페": "cafe",
        "식사": "restaurant",
        "맛집": "restaurant",
        "문화": "museum",
        "미술관": "museum",
        "체험": "activity",
        "야경": "night_view",
        "산책": "walk",
        "자연": "nature",
        "역사": "heritage",
        "문화유산": "heritage",
        "랜드마크": "landmark",
        "명소": "landmark",
    }
    return {aliases[item] for item in preferences if item in aliases}


def _candidate_details(
    payload: CourseRequest,
    weather_condition: str,
    tour_place_ids: set[str],
) -> list[PlaceDetailsResult]:
    summaries = search_places("", payload.location).places
    context = search_date_context(
        payload.companion_type,
        " ".join(payload.soft_preferences),
        payload.soft_preferences,
        payload.hard_constraints,
        [place.place_id for place in summaries],
    )
    context_by_id = {item.place_id: item for item in context.contexts}
    preferred = _preferred_categories(payload.soft_preferences)
    hard_text = " ".join(payload.hard_constraints)
    indoor_required = "실내" in hard_text or (
        weather_condition == "rain" and "비 오면 실내" in hard_text
    )
    accessible_required = any(
        term in hard_text for term in ("휠체어", "접근성", "걷기 어려움")
    )

    ranked: list[tuple[int, PlaceDetailsResult]] = []
    for summary in summaries:
        details = get_place_details(summary.place_id)
        if details.error_code:
            continue
        if indoor_required and details.indoor is not True:
            continue
        if accessible_required and details.accessible is not True:
            continue
        semantic = context_by_id.get(details.place_id)
        score = 0
        if details.category in preferred:
            score += 20
        if details.place_id in tour_place_ids:
            score += 18
        if semantic:
            if payload.companion_type == "family":
                score += semantic.scores.get("family", 0) * 2
            else:
                score += semantic.scores.get("romantic", 0)
                score += semantic.scores.get("conversation", 0)
            if "사진" in payload.soft_preferences:
                score += semantic.scores.get("photo", 0) * 2
        ranked.append((score, details))
    ranked.sort(key=lambda item: (-item[0], item[1].category or "", item[1].name or ""))
    return [details for _, details in ranked]


def _compose_stops(
    payload: CourseRequest,
    candidates: list[PlaceDetailsResult],
    *,
    limit: int = 3,
) -> list[CourseStopInput]:
    current = _minutes(payload.start_time)
    requested_end = _minutes(payload.end_time)
    stops: list[CourseStopInput] = []
    selected_categories: set[str] = set()
    known_cost = 0

    # Agent가 만든 순위를 유지하되 동일 카테고리 후보는 뒤로 보냅니다.
    first_by_category: list[PlaceDetailsResult] = []
    repeated: list[PlaceDetailsResult] = []
    seen_categories: set[str] = set()
    for candidate in candidates:
        category = candidate.category or "unknown"
        target = repeated if category in seen_categories else first_by_category
        target.append(candidate)
        seen_categories.add(category)
    ordered = first_by_category + repeated
    for details in ordered:
        if len(stops) >= limit:
            break
        route = None
        if stops:
            route_result = calculate_route(
                stops[-1].place_id,
                details.place_id,
                payload.transportation,
            )
            if route_result.error_code:
                continue
            route = RouteInput(
                distance_m=route_result.distance_m or 0,
                duration_min=route_result.duration_min or 0,
                walking_distance_m=route_result.walking_distance_m or 0,
                transportation=payload.transportation,
            )
        start = current + (route.duration_min if route else 0)
        opening = _opening_range(details)
        if opening:
            start = max(start, opening[0])
        duration = VISIT_MINUTES.get(details.category or "", 60)
        end = start + duration
        if end > requested_end or (opening and end > opening[1]):
            continue

        next_known_cost = known_cost
        if details.estimated_cost_per_person is not None:
            next_known_cost += details.estimated_cost_per_person * payload.party_size
        if next_known_cost > payload.budget:
            continue

        stops.append(
            CourseStopInput(
                stop_id=f"stop_{len(stops) + 1}",
                place_id=details.place_id,
                name=details.name,
                category=details.category,
                start_time=_clock(start),
                end_time=_clock(end),
                expected_cost=details.estimated_cost_per_person,
                opening_hours=details.opening_hours,
                opening_hours_verified=details.opening_hours_verified,
                indoor=details.indoor,
                accessible=details.accessible,
                tourism_category=details.tourism_category,
                description=details.description,
                route_from_previous=route,
                recommendation_rationale=(
                    f"요청 조건에 맞춘 {CATEGORY_LABELS.get(details.category or '', details.category or '장소')} "
                    "Mock 후보입니다."
                ),
            )
        )
        known_cost = next_known_cost
        current = end
        if details.category:
            selected_categories.add(details.category)
    return stops


def _local_replan(
    payload: CourseRequest,
    candidates: list[PlaceDetailsResult],
    stops: list[CourseStopInput],
    failed_stop_ids: set[str],
) -> list[CourseStopInput]:
    failed_place_ids = {
        stop.place_id for stop in stops if stop.stop_id in failed_stop_ids
    }
    preserved_place_ids = [
        stop.place_id for stop in stops if stop.stop_id not in failed_stop_ids
    ]
    by_id = {candidate.place_id: candidate for candidate in candidates}
    ordered = [by_id[item] for item in preserved_place_ids if item in by_id]
    ordered.extend(
        candidate
        for candidate in candidates
        if candidate.place_id not in preserved_place_ids
        and candidate.place_id not in failed_place_ids
    )
    return _compose_stops(payload, ordered)


def build_mock_course(payload: CourseRequest) -> dict:
    weather = get_weather(payload.location, payload.date)
    if weather.error_code:
        raise ValueError("지원하지 않는 지역입니다.")
    intent = UserIntentInput(
        companion_type=payload.companion_type,
        location=payload.location,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        party_size=payload.party_size,
        budget=payload.budget,
        transportation=payload.transportation,
        hard_constraints=payload.hard_constraints,
        soft_preferences=payload.soft_preferences,
        assumptions=["외부 Provider 대신 교육용 Mock 데이터를 사용합니다."],
        weather_condition=weather.condition,
        max_walking_distance_m=payload.max_walking_distance_m,
    )
    tourism = get_tourist_attractions(
        payload.location,
        payload.tourism_categories or None,
        limit=8,
    )
    tour_place_ids = {item.place_id for item in tourism.items}
    candidates = _candidate_details(
        payload,
        weather.condition or "unknown",
        tour_place_ids,
    )
    stops = _compose_stops(payload, candidates)
    validation = validate_course(intent, stops)
    validation_attempts = 1
    preserved_history: list[list[str]] = []

    while not validation.valid and validation_attempts <= 2:
        failed_stop_ids = {
            issue.stop_id for issue in validation.errors if issue.stop_id
        }
        if not failed_stop_ids:
            break
        preserved_history.append(
            [stop.place_id for stop in stops if stop.stop_id not in failed_stop_ids]
        )
        stops = _local_replan(payload, candidates, stops, failed_stop_ids)
        validation = validate_course(intent, stops)
        validation_attempts += 1

    warnings = [issue.message for issue in validation.warnings]
    warnings.append("무료 공개 데모이므로 실시간 API가 아닌 Mock 데이터를 사용합니다.")
    if len(stops) < 2:
        warnings.append("현재 조건에서 구성 가능한 장소가 부족합니다. 시간 또는 예산을 넓혀 주세요.")

    return {
        "course_id": _course_id(payload, stops),
        "intent_summary": {
            "request": payload.request,
            "location": payload.location,
            "date": payload.date,
            "companion_type": payload.companion_type,
            "party_size": payload.party_size,
            "budget": payload.budget,
            "transportation": payload.transportation,
            "hard_constraints": payload.hard_constraints,
            "soft_preferences": payload.soft_preferences,
            "weather": weather.model_dump(),
        },
        "assumptions": intent.assumptions,
        "tourism": tourism.model_dump(),
        "course": {
            "stops": [stop.model_dump() for stop in stops],
            "total_route_time": validation.total_route_time,
            "total_walking_distance": validation.total_walking_distance,
        },
        "recommendation_rationale": [
            "Hard Constraint를 먼저 필터링하고 선호 카테고리와 의미 점수를 반영했습니다.",
            "관광 명소는 로컬 관광 카탈로그의 place_id를 장소·경로 검증에 연결했습니다.",
            "가격·시간·영업시간·이동시간은 결정론적 Validator로 확인했습니다.",
        ],
        "known_total_cost": validation.known_total_cost,
        "unknown_costs": validation.unknown_costs,
        "warnings": list(dict.fromkeys(warnings)),
        "validation": {
            "status": "pass" if validation.valid else "fail",
            "errors": [item.model_dump() for item in validation.errors],
            "warnings": [item.model_dump() for item in validation.warnings],
            "unknowns": validation.unknowns,
        },
        "agent_execution": {
            "mode": "deterministic_mock",
            "execution_path": "in_process_free_demo",
            "registered_mcp_servers": ["weather", "tour", "route", "booking"],
            "mcp_servers_called": [],
            "domain_steps": [
                "get_weather",
                "get_tourist_attractions",
                "search_places",
                "get_place_details",
                "search_date_context",
                "calculate_route",
                "validate_course",
            ],
            "available_action_tools": [
                "prepare_booking",
                "confirm_booking",
                "get_booking_status",
            ],
            "validation_attempts": validation_attempts,
            "replan_count": max(0, validation_attempts - 1),
            "preserved_place_ids": preserved_history,
        },
    }


app = FastAPI(
    title="Courseful City Course Planner",
    description="멀티 MCP 조회·검증·모의 예약 흐름을 제공하는 무료 공개 데모",
    version="1.2.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.head("/", include_in_schema=False)
def home_head() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "deterministic_mock",
        "storage": "none",
        "booking": "simulated_memory_only",
    }


@app.post("/api/v1/course-plans")
def create_course(payload: CourseRequest) -> dict:
    if _minutes(payload.start_time) >= _minutes(payload.end_time):
        raise HTTPException(status_code=422, detail="종료 시간은 시작 시간보다 늦어야 합니다.")
    try:
        return build_mock_course(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/bookings")
async def create_simulated_booking(payload: BookingRequest) -> dict:
    """명시적 확인이 있는 코스를 모의 예약하며 외부 쓰기는 수행하지 않습니다."""
    try:
        async with connect_to_mcp_servers(server_names={"booking"}) as client:
            draft_result = await client.call_tool(
                "prepare_booking",
                {
                    "course_id": payload.course_id,
                    "date": payload.date,
                    "party_size": payload.party_size,
                    "stops": [stop.model_dump() for stop in payload.stops],
                },
            )
            if draft_result.isError or not draft_result.structuredContent:
                raise ValueError("Booking MCP가 예약 초안을 만들지 못했습니다.")
            draft = draft_result.structuredContent
            action_result = await client.call_tool(
                "confirm_booking",
                {
                    "booking_token": draft["booking_token"],
                    "user_confirmed": payload.user_confirmed,
                },
            )
            if not action_result.structuredContent:
                raise ValueError("Booking MCP가 예약 결과를 반환하지 않았습니다.")
            action = action_result.structuredContent
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if action.get("error_code") == "CONFIRMATION_REQUIRED":
        raise HTTPException(status_code=409, detail=action["message"])
    return {
        "draft": draft,
        "booking": action,
        "mcp_server": "booking",
        "actual_side_effect": False,
    }
