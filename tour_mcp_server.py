"""관광·장소 조회를 담당하는 독립 Tour MCP Server입니다."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from date_course_tools import (
    CompanionType,
    DateContextResult,
    PlaceDetailsResult,
    SearchPlacesResult,
    SupportedCity,
    TourAttractionsResult,
    TourismCategory,
    get_place_details as get_place_details_impl,
    get_tourist_attractions as get_tourist_attractions_impl,
    search_date_context as search_date_context_impl,
    search_places as search_places_impl,
)


mcp = FastMCP("tour-and-place-lookup")


@mcp.tool()
def get_tourist_attractions(
    city: SupportedCity,
    categories: list[TourismCategory] | None = None,
    limit: int = 6,
) -> TourAttractionsResult:
    """부산 또는 서울의 관광 명소와 재사용 가능한 place_id를 반환합니다."""
    return get_tourist_attractions_impl(city, categories, limit)


@mcp.tool()
def search_places(
    query: str,
    location: str,
    radius_m: int | None = None,
    categories: list[str] | None = None,
) -> SearchPlacesResult:
    """지역과 조건에 맞는 장소 후보를 검색합니다."""
    return search_places_impl(query, location, radius_m, categories)


@mcp.tool()
def get_place_details(place_id: str) -> PlaceDetailsResult:
    """장소의 영업시간·가격·실내 여부·접근성을 조회합니다."""
    return get_place_details_impl(place_id)


@mcp.tool()
def search_date_context(
    companion_type: CompanionType,
    mood: str,
    preferences: list[str],
    constraints: list[str],
    candidate_place_ids: list[str] | None = None,
) -> DateContextResult:
    """후보 장소의 분위기와 동행 맥락 점수를 반환합니다."""
    return search_date_context_impl(
        companion_type,
        mood,
        preferences,
        constraints,
        candidate_place_ids,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
