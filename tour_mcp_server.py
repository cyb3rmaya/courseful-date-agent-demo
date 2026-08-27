"""관광 명소와 수업용 호텔 검색을 제공하는 독립 Streamable HTTP MCP Server."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from travel_data import (
    HotelSearch,
    SpotCategory,
    SpotSearch,
    SupportedCity,
    search_hotels as search_hotels_impl,
    search_spots as search_spots_impl,
)


mcp = FastMCP(
    "tour-http",
    instructions="코스 구성을 위한 지역 명소와 좌표를 제공합니다. 호텔 검색은 MCP 확장 수업용으로 보존합니다.",
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def search_hotels(
    location: SupportedCity,
    max_price_per_night: int = 150_000,
    limit: int = 5,
) -> HotelSearch:
    """지역과 1박 최대 가격으로 호텔을 검색합니다. 예: 부산, 150000원 이하."""
    return search_hotels_impl(location, max_price_per_night, limit)


@mcp.tool()
def search_spots(
    location: SupportedCity,
    category: SpotCategory = "all",
    limit: int = 6,
) -> SpotSearch:
    """지역의 관광 명소를 찾습니다. Kakao REST 키가 있으면 실시간 장소 검색을 사용합니다."""
    return search_spots_impl(location, category, limit)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "tour", "transport": "streamable_http"})


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tour Streamable HTTP MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8102)
    return parser.parse_args()


if __name__ == "__main__":
    args = _arguments()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")
