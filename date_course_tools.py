"""PLAN.md 계약을 따르는 결정론적 데이트 코스 Tool 구현입니다.

외부 Provider가 확정되지 않은 교육 단계이므로 동적 데이터는 명시적인 Mock
Provider에서만 가져옵니다. 예산 합계와 코스 검증은 LLM이 아니라 이 모듈의
일반 Python 코드가 담당합니다.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


CompanionType = Literal["couple", "family", "friends"]
Transportation = Literal["walking", "public_transport", "car"]


def _fetched_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ToolMetadata(BaseModel):
    source: str
    fetched_at: str = Field(default_factory=_fetched_at)
    error_code: str | None = None


class WeatherResult(ToolMetadata):
    location: str
    date: str
    condition: str | None = None
    temperature_c: int | None = None
    rain_probability: int | None = None


class PlaceSummary(BaseModel):
    place_id: str
    name: str
    category: str
    address: str
    lat: float
    lng: float


class SearchPlacesResult(ToolMetadata):
    places: list[PlaceSummary] = Field(default_factory=list)


class PlaceDetailsResult(ToolMetadata):
    place_id: str
    name: str | None = None
    category: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    opening_hours: str | None = None
    opening_hours_verified: bool = False
    estimated_cost_per_person: int | None = None
    official_url: str | None = None
    indoor: bool | None = None
    accessible: bool | None = None


class RouteResult(ToolMetadata):
    distance_m: int | None = None
    duration_min: int | None = None
    walking_distance_m: int | None = None
    transportation: Transportation


class DateContext(BaseModel):
    place_id: str
    semantic_tags: list[str]
    scores: dict[str, int]
    source: str
    last_verified_at: str


class DateContextResult(ToolMetadata):
    contexts: list[DateContext] = Field(default_factory=list)


class RouteInput(BaseModel):
    distance_m: int = Field(ge=0)
    duration_min: int = Field(ge=0)
    walking_distance_m: int = Field(ge=0)
    transportation: Transportation


class CourseStopInput(BaseModel):
    stop_id: str = Field(min_length=1)
    place_id: str = Field(min_length=1)
    name: str | None = None
    category: str | None = None
    start_time: str
    end_time: str
    expected_cost: int | None = Field(
        default=None,
        ge=0,
        description="교통비를 제외한 1인당 예상 비용",
    )
    opening_hours: str | None = None
    opening_hours_verified: bool = False
    indoor: bool | None = None
    accessible: bool | None = None
    route_from_previous: RouteInput | None = None
    recommendation_rationale: str | None = None


class UserIntentInput(BaseModel):
    session_id: str | None = None
    companion_type: CompanionType
    location: str
    date: str
    start_time: str
    end_time: str
    party_size: int = Field(ge=1, le=20)
    budget: int | None = Field(default=None, ge=0)
    transportation: Transportation
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    weather_condition: str | None = None
    max_walking_distance_m: int | None = Field(default=None, ge=0)


class BudgetResult(ToolMetadata):
    known_total: int
    unknown_items: list[str]
    budget_limit: int | None
    within_known_budget: bool | None


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning"]
    stop_id: str | None = None
    message: str
    suggested_action: str | None = None


class ValidationResult(ToolMetadata):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    unknowns: list[str]
    known_total_cost: int
    unknown_costs: list[str]
    total_route_time: int
    total_walking_distance: int


_PLACES: tuple[dict[str, Any], ...] = (
    {
        "place_id": "busan-museum-1",
        "name": "부산 현대미술관",
        "category": "museum",
        "address": "부산광역시 사하구 낙동남로 1191",
        "lat": 35.1092,
        "lng": 128.9425,
        "opening_hours": "10:00-18:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 0,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "quiet", "conversation", "family"],
        "scores": {"romantic": 3, "conversation": 5, "photo": 4, "family": 5},
    },
    {
        "place_id": "busan-cafe-1",
        "name": "광안 바다서가",
        "category": "cafe",
        "address": "부산광역시 수영구 광안해변로 219",
        "lat": 35.1532,
        "lng": 129.1187,
        "opening_hours": "11:00-22:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 12_000,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "romantic", "conversation", "ocean-view"],
        "scores": {"romantic": 5, "conversation": 5, "photo": 5, "family": 3},
    },
    {
        "place_id": "busan-restaurant-1",
        "name": "남천 온기식탁",
        "category": "restaurant",
        "address": "부산광역시 수영구 남천동로 31",
        "lat": 35.1421,
        "lng": 129.1099,
        "opening_hours": "11:30-21:30",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 24_000,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "quiet", "conversation", "family"],
        "scores": {"romantic": 4, "conversation": 5, "photo": 3, "family": 5},
    },
    {
        "place_id": "busan-night-1",
        "name": "황령산 전망쉼터",
        "category": "night_view",
        "address": "부산광역시 부산진구 전포동 산50-25",
        "lat": 35.1578,
        "lng": 129.0828,
        "opening_hours": "00:00-23:59",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 0,
        "indoor": False,
        "accessible": False,
        "semantic_tags": ["outdoor", "romantic", "night-view", "photo"],
        "scores": {"romantic": 5, "conversation": 3, "photo": 5, "family": 2},
    },
    {
        "place_id": "busan-activity-1",
        "name": "센텀 미디어아트홀",
        "category": "activity",
        "address": "부산광역시 해운대구 센텀서로 30",
        "lat": 35.1728,
        "lng": 129.1270,
        "opening_hours": "10:00-20:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": None,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "activity", "photo", "friends"],
        "scores": {"romantic": 4, "conversation": 2, "photo": 5, "family": 4},
    },
    {
        "place_id": "seoul-cafe-1",
        "name": "서울숲 대화카페",
        "category": "cafe",
        "address": "서울특별시 성동구 서울숲길 42",
        "lat": 37.5468,
        "lng": 127.0410,
        "opening_hours": "10:00-22:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 11_000,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "quiet", "conversation", "romantic"],
        "scores": {"romantic": 5, "conversation": 5, "photo": 4, "family": 3},
    },
    {
        "place_id": "seoul-palace-1",
        "name": "덕수궁 돌담길",
        "category": "walk",
        "address": "서울특별시 중구 세종대로 99",
        "lat": 37.5658,
        "lng": 126.9751,
        "opening_hours": "09:00-21:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 1_000,
        "indoor": False,
        "accessible": True,
        "semantic_tags": ["outdoor", "romantic", "walk", "photo"],
        "scores": {"romantic": 5, "conversation": 4, "photo": 5, "family": 4},
    },
    {
        "place_id": "seoul-restaurant-1",
        "name": "시청 담소식당",
        "category": "restaurant",
        "address": "서울특별시 중구 서소문로 120",
        "lat": 37.5631,
        "lng": 126.9766,
        "opening_hours": "11:30-21:00",
        "opening_hours_verified": True,
        "estimated_cost_per_person": 22_000,
        "indoor": True,
        "accessible": True,
        "semantic_tags": ["indoor", "quiet", "conversation", "family"],
        "scores": {"romantic": 4, "conversation": 5, "photo": 3, "family": 5},
    },
)


def _place(place_id: str) -> dict[str, Any] | None:
    return next((item for item in _PLACES if item["place_id"] == place_id), None)


def get_weather(location: str, date: str) -> WeatherResult:
    """Mock Provider에서 지역/날짜 날씨를 조회합니다."""
    normalized = location.strip()
    if normalized not in {"부산", "서울"}:
        return WeatherResult(
            location=normalized,
            date=date,
            source="mock-weather-provider",
            error_code="UNSUPPORTED_LOCATION",
        )
    is_busan = normalized == "부산"
    return WeatherResult(
        location=normalized,
        date=date,
        condition="rain" if is_busan else "clear",
        temperature_c=25 if is_busan else 27,
        rain_probability=80 if is_busan else 20,
        source="mock-weather-provider",
    )


def search_places(
    query: str,
    location: str,
    radius_m: int | None = None,
    categories: list[str] | None = None,
) -> SearchPlacesResult:
    """Mock 장소 카탈로그에서 실제 식별자를 가진 후보를 검색합니다."""
    if radius_m is not None and radius_m < 1:
        raise ValueError("radius_m는 1 이상이어야 합니다.")
    normalized_location = location.strip()
    normalized_query = query.strip().lower()
    aliases = {
        "카페": "cafe",
        "식당": "restaurant",
        "맛집": "restaurant",
        "미술관": "museum",
        "박물관": "museum",
        "야경": "night_view",
        "산책": "walk",
        "체험": "activity",
    }
    query_terms = [
        aliases.get(term, term)
        for term in normalized_query.replace("+", " ").split()
    ]
    wanted_categories = {item.strip().lower() for item in categories or []}
    matches: list[PlaceSummary] = []
    for item in _PLACES:
        if normalized_location not in item["address"]:
            continue
        if wanted_categories and item["category"].lower() not in wanted_categories:
            continue
        searchable = " ".join(
            [item["name"], item["category"], *item["semantic_tags"]]
        ).lower()
        if normalized_query and normalized_query not in searchable:
            if not any(term in searchable for term in query_terms):
                continue
        matches.append(PlaceSummary(**item))
    return SearchPlacesResult(places=matches, source="mock-place-provider")


def get_place_details(place_id: str) -> PlaceDetailsResult:
    """장소의 영업시간과 가격 등 실행 가능성 정보를 조회합니다."""
    item = _place(place_id)
    if item is None:
        return PlaceDetailsResult(
            place_id=place_id,
            source="mock-place-provider",
            error_code="PLACE_NOT_FOUND",
        )
    return PlaceDetailsResult(
        **{key: value for key, value in item.items() if key not in {"semantic_tags", "scores"}},
        official_url=None,
        source="mock-place-provider",
    )


def _haversine_distance_m(origin: PlaceDetailsResult, destination: PlaceDetailsResult) -> int:
    if None in {origin.lat, origin.lng, destination.lat, destination.lng}:
        raise ValueError("경로 계산에 좌표가 필요합니다.")
    lat1, lng1, lat2, lng2 = map(
        math.radians,
        (origin.lat, origin.lng, destination.lat, destination.lng),
    )
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return round(6_371_000 * 2 * math.asin(math.sqrt(value)))


def calculate_route(
    origin_place_id: str,
    destination_place_id: str,
    transportation: Transportation,
) -> RouteResult:
    """Mock 좌표에 기반해 거리와 이동시간을 결정론적으로 계산합니다."""
    origin = get_place_details(origin_place_id)
    destination = get_place_details(destination_place_id)
    if origin.error_code or destination.error_code:
        return RouteResult(
            transportation=transportation,
            source="deterministic-route-calculator",
            error_code="PLACE_NOT_FOUND",
        )
    distance_m = _haversine_distance_m(origin, destination)
    if transportation == "walking":
        duration_min = max(1, math.ceil(distance_m / 80))
        walking_distance_m = distance_m
    elif transportation == "public_transport":
        duration_min = max(8, math.ceil(distance_m / 300) + 8)
        walking_distance_m = min(distance_m, 700)
    else:
        duration_min = max(5, math.ceil(distance_m / 500) + 5)
        walking_distance_m = min(distance_m, 150)
    return RouteResult(
        distance_m=distance_m,
        duration_min=duration_min,
        walking_distance_m=walking_distance_m,
        transportation=transportation,
        source="deterministic-route-calculator",
    )


def search_date_context(
    companion_type: CompanionType,
    mood: str,
    preferences: list[str],
    constraints: list[str],
    candidate_place_ids: list[str] | None = None,
) -> DateContextResult:
    """Mock RAG 문서의 의미적 특징만 반환하고 동적 사실은 반환하지 않습니다."""
    del companion_type, mood, preferences, constraints
    allowed = set(candidate_place_ids or [])
    contexts = [
        DateContext(
            place_id=item["place_id"],
            semantic_tags=item["semantic_tags"],
            scores=item["scores"],
            source="mock-date-context-rag",
            last_verified_at="2026-08-26T00:00:00Z",
        )
        for item in _PLACES
        if not allowed or item["place_id"] in allowed
    ]
    return DateContextResult(contexts=contexts, source="mock-date-context-rag")


def estimate_course_budget(
    stops: list[CourseStopInput],
    party_size: int,
    transport_costs: list[int],
    budget_limit: int | None = None,
) -> BudgetResult:
    """알려진 비용만 합산하고 미확인 비용은 별도로 유지합니다."""
    if party_size < 1:
        raise ValueError("party_size는 1 이상이어야 합니다.")
    if any(cost < 0 for cost in transport_costs):
        raise ValueError("transport_costs는 음수일 수 없습니다.")
    known_total = party_size * sum(
        stop.expected_cost for stop in stops if stop.expected_cost is not None
    ) + sum(transport_costs)
    unknown_items = [
        f"{stop.stop_id}_price" for stop in stops if stop.expected_cost is None
    ]
    within = None if budget_limit is None else known_total <= budget_limit
    return BudgetResult(
        known_total=known_total,
        unknown_items=unknown_items,
        budget_limit=budget_limit,
        within_known_budget=within,
        source="deterministic-budget-calculator",
    )


def _minutes(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError(f"시간은 HH:MM 형식이어야 합니다: {value}") from exc
    return parsed.hour * 60 + parsed.minute


def _issue(
    code: str,
    severity: Literal["error", "warning"],
    message: str,
    stop_id: str | None = None,
    suggested_action: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        stop_id=stop_id,
        message=message,
        suggested_action=suggested_action,
    )


def validate_course(
    intent: UserIntentInput,
    stops: list[CourseStopInput],
) -> ValidationResult:
    """시간·운영·이동·예산·Hard Constraint를 결정론적으로 검증합니다."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    unknowns: list[str] = []
    known_total = intent.party_size * sum(
        stop.expected_cost for stop in stops if stop.expected_cost is not None
    )
    unknown_costs = [
        f"{stop.stop_id}_price" for stop in stops if stop.expected_cost is None
    ]
    total_route_time = sum(
        stop.route_from_previous.duration_min
        for stop in stops
        if stop.route_from_previous is not None
    )
    total_walking_distance = sum(
        stop.route_from_previous.walking_distance_m
        for stop in stops
        if stop.route_from_previous is not None
    )

    if not stops:
        errors.append(_issue("EMPTY_COURSE", "error", "코스에 장소가 없습니다."))

    intent_start = _minutes(intent.start_time)
    intent_end = _minutes(intent.end_time)
    previous_end: int | None = None
    seen_places: set[str] = set()
    categories: dict[str, int] = {}
    hard_text = " ".join(intent.hard_constraints).lower()

    for stop in stops:
        start = _minutes(stop.start_time)
        end = _minutes(stop.end_time)
        if start >= end:
            errors.append(
                _issue(
                    "INVALID_TIME_RANGE",
                    "error",
                    "종료 시간은 시작 시간보다 늦어야 합니다.",
                    stop.stop_id,
                    "방문 시간을 다시 배치하세요.",
                )
            )
        if start < intent_start or end > intent_end:
            errors.append(
                _issue(
                    "OUTSIDE_REQUESTED_TIME",
                    "error",
                    "요청한 코스 시간 범위를 벗어났습니다.",
                    stop.stop_id,
                    "요청 시간 안으로 이동하세요.",
                )
            )
        if previous_end is not None:
            required_gap = (
                stop.route_from_previous.duration_min
                if stop.route_from_previous is not None
                else 0
            )
            if start < previous_end + required_gap:
                errors.append(
                    _issue(
                        "INSUFFICIENT_ROUTE_TIME",
                        "error",
                        "이전 장소에서 이동할 시간이 부족합니다.",
                        stop.stop_id,
                        "이동시간만큼 시작 시간을 늦추세요.",
                    )
                )
        previous_end = max(previous_end or end, end)

        if stop.place_id in seen_places:
            errors.append(
                _issue(
                    "DUPLICATE_PLACE",
                    "error",
                    "같은 장소가 중복되었습니다.",
                    stop.stop_id,
                    "중복 Stop만 다른 장소로 교체하세요.",
                )
            )
        seen_places.add(stop.place_id)

        if stop.category:
            categories[stop.category] = categories.get(stop.category, 0) + 1

        if stop.opening_hours_verified and stop.opening_hours:
            open_at, close_at = map(_minutes, stop.opening_hours.split("-", maxsplit=1))
            if start < open_at or end > close_at:
                errors.append(
                    _issue(
                        "CLOSED_AT_VISIT_TIME",
                        "error",
                        "예정 방문 시간에 영업 여부를 충족하지 못합니다.",
                        stop.stop_id,
                        "해당 Stop의 시간 또는 장소만 교체하세요.",
                    )
                )
        else:
            unknowns.append(f"{stop.stop_id}_opening_hours")
            warnings.append(
                _issue(
                    "OPENING_HOURS_UNKNOWN",
                    "warning",
                    "영업시간을 확인하지 못했습니다.",
                    stop.stop_id,
                )
            )

        indoor_required = "실내" in hard_text or (
            intent.weather_condition == "rain" and "비 오면 실내" in hard_text
        )
        if indoor_required and stop.indoor is not True:
            errors.append(
                _issue(
                    "INDOOR_CONSTRAINT_VIOLATION",
                    "error",
                    "실내 Hard Constraint를 충족하지 못합니다.",
                    stop.stop_id,
                    "이 Stop만 실내 장소로 교체하세요.",
                )
            )
        if any(term in hard_text for term in ("휠체어", "접근성", "걷기 어려움")):
            if stop.accessible is not True:
                errors.append(
                    _issue(
                        "ACCESSIBILITY_CONSTRAINT_VIOLATION",
                        "error",
                        "접근성 Hard Constraint를 충족하지 못합니다.",
                        stop.stop_id,
                        "이 Stop만 접근 가능한 장소로 교체하세요.",
                    )
                )

    if intent.budget is not None and known_total > intent.budget:
        errors.append(
            _issue(
                "KNOWN_BUDGET_EXCEEDED",
                "error",
                "확인된 비용만으로 예산을 초과합니다.",
                suggested_action="비용이 큰 Stop만 더 저렴한 장소로 교체하세요.",
            )
        )
    for item in unknown_costs:
        warnings.append(
            _issue("PRICE_UNKNOWN", "warning", "가격을 확인하지 못했습니다.", item.removesuffix("_price"))
        )
    if (
        intent.max_walking_distance_m is not None
        and total_walking_distance > intent.max_walking_distance_m
    ):
        errors.append(
            _issue(
                "WALKING_LIMIT_EXCEEDED",
                "error",
                "총 도보 거리가 허용 범위를 초과합니다.",
                suggested_action="문제가 되는 이동 구간 또는 인접 Stop만 교체하세요.",
            )
        )
    for category, count in categories.items():
        if count >= 3:
            warnings.append(
                _issue(
                    "CATEGORY_OVERREPRESENTED",
                    "warning",
                    f"{category} 카테고리가 {count}회 반복됩니다.",
                )
            )

    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        unknowns=unknowns,
        known_total_cost=known_total,
        unknown_costs=unknown_costs,
        total_route_time=total_route_time,
        total_walking_distance=total_walking_distance,
        source="deterministic-course-validator",
    )


__all__ = [
    "BudgetResult",
    "CompanionType",
    "CourseStopInput",
    "DateContextResult",
    "PlaceDetailsResult",
    "RouteResult",
    "SearchPlacesResult",
    "Transportation",
    "UserIntentInput",
    "ValidationResult",
    "WeatherResult",
    "calculate_route",
    "estimate_course_budget",
    "get_place_details",
    "get_weather",
    "search_date_context",
    "search_places",
    "validate_course",
]
