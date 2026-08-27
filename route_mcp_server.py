"""경로·예산·코스 검증을 담당하는 독립 Route MCP Server입니다."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from date_course_tools import (
    BudgetResult,
    CourseStopInput,
    RouteResult,
    Transportation,
    UserIntentInput,
    ValidationResult,
    calculate_route as calculate_route_impl,
    estimate_course_budget as estimate_course_budget_impl,
    validate_course as validate_course_impl,
)


mcp = FastMCP("route-budget-validation")


@mcp.tool()
def calculate_route(
    origin_place_id: str,
    destination_place_id: str,
    transportation: Transportation,
) -> RouteResult:
    """두 장소 사이의 거리·시간·도보량을 계산합니다."""
    return calculate_route_impl(origin_place_id, destination_place_id, transportation)


@mcp.tool()
def estimate_course_budget(
    stops: list[CourseStopInput],
    party_size: int,
    transport_costs: list[int],
    budget_limit: int | None = None,
) -> BudgetResult:
    """알려진 비용만 합산하고 미확인 비용은 별도로 반환합니다."""
    return estimate_course_budget_impl(stops, party_size, transport_costs, budget_limit)


@mcp.tool()
def validate_course(
    intent: UserIntentInput,
    stops: list[CourseStopInput],
) -> ValidationResult:
    """코스를 결정론적으로 검증합니다. 최종 확정 전에 호출해야 합니다."""
    return validate_course_impl(intent, stops)


if __name__ == "__main__":
    mcp.run(transport="stdio")
