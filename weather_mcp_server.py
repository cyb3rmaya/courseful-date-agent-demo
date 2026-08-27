"""현재 날씨와 단기예보를 제공하는 독립 Streamable HTTP MCP Server."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from travel_data import (
    SupportedCity,
    WeatherCurrent,
    WeatherForecast,
    get_current_weather as get_current_weather_impl,
    get_weather_forecast as get_weather_forecast_impl,
)


mcp = FastMCP(
    "weather-http",
    instructions="기상청 실황과 단기예보를 조회합니다. current와 forecast 두 Tool만 제공합니다.",
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def get_current_weather(location: SupportedCity) -> WeatherCurrent:
    """서울·부산·제주의 현재 날씨를 조회합니다. 결과의 source와 provider_status를 확인하세요."""
    return get_current_weather_impl(location)


@mcp.tool()
def get_weather_forecast(location: SupportedCity, date: str) -> WeatherForecast:
    """지정한 날짜의 단기예보를 조회합니다. 날짜는 YYYY-MM-DD 형식입니다."""
    return get_weather_forecast_impl(location, date)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "weather", "transport": "streamable_http"})


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weather Streamable HTTP MCP Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    return parser.parse_args()


if __name__ == "__main__":
    args = _arguments()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")
