"""DateCourseAgent가 사용하는 Common/Domain Tool MCP Adapter입니다."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from date_course_tools import (
    BudgetResult,
    CompanionType,
    CourseStopInput,
    DateContextResult,
    PlaceDetailsResult,
    RouteResult,
    SearchPlacesResult,
    Transportation,
    UserIntentInput,
    ValidationResult,
    WeatherResult,
    calculate_route as calculate_route_impl,
    estimate_course_budget as estimate_course_budget_impl,
    get_place_details as get_place_details_impl,
    get_weather as get_weather_impl,
    search_date_context as search_date_context_impl,
    search_places as search_places_impl,
    validate_course as validate_course_impl,
)


mcp = FastMCP(
    "date-course-tools",
    instructions=(
        "PLAN.md 기반 데이트 코스 도구입니다. 동적 사실은 Provider Tool에서 조회하고, "
        "비용과 코스 적합성은 결정론적 Tool 결과를 따르세요."
    ),
)


@mcp.tool()
def get_weather(location: str, date: str) -> WeatherResult:
    """지역/날짜의 날씨를 조회합니다. Mock 결과는 source로 명시됩니다."""
    return get_weather_impl(location, date)


@mcp.tool()
def search_places(
    query: str,
    location: str,
    radius_m: int | None = None,
    categories: list[str] | None = None,
) -> SearchPlacesResult:
    """지역, 키워드, 카테고리에 맞는 장소 후보를 검색합니다."""
    return search_places_impl(query, location, radius_m, categories)


@mcp.tool()
def get_place_details(place_id: str) -> PlaceDetailsResult:
    """장소의 영업시간, 가격, 실내 여부와 접근성을 확인합니다."""
    return get_place_details_impl(place_id)


@mcp.tool()
def calculate_route(
    origin_place_id: str,
    destination_place_id: str,
    transportation: Transportation,
) -> RouteResult:
    """두 장소 사이의 거리, 시간, 도보량을 계산합니다."""
    return calculate_route_impl(origin_place_id, destination_place_id, transportation)


@mcp.tool()
def search_date_context(
    companion_type: CompanionType,
    mood: str,
    preferences: list[str],
    constraints: list[str],
    candidate_place_ids: list[str] | None = None,
) -> DateContextResult:
    """후보 장소의 분위기와 동행 맥락 같은 의미적 특징을 검색합니다."""
    return search_date_context_impl(
        companion_type,
        mood,
        preferences,
        constraints,
        candidate_place_ids,
    )


@mcp.tool()
def estimate_course_budget(
    stops: list[CourseStopInput],
    party_size: int,
    transport_costs: list[int],
    budget_limit: int | None = None,
) -> BudgetResult:
    """알려진 비용만 합산하고 미확인 가격을 별도로 반환합니다."""
    return estimate_course_budget_impl(stops, party_size, transport_costs, budget_limit)


@mcp.tool()
def validate_course(
    intent: UserIntentInput,
    stops: list[CourseStopInput],
) -> ValidationResult:
    """코스를 결정론적으로 검증합니다. 최종 답변 전에 반드시 호출하세요."""
    return validate_course_impl(intent, stops)


if __name__ == "__main__":
    mcp.run(transport="stdio")
