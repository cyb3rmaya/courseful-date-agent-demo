"""날씨 조회만 담당하는 독립 Weather MCP Server입니다."""

from mcp.server.fastmcp import FastMCP

from date_course_tools import WeatherResult, get_weather as get_weather_impl


mcp = FastMCP("weather-lookup")


@mcp.tool()
def get_weather(location: str, date: str) -> WeatherResult:
    """지역과 날짜의 날씨를 조회합니다. source가 Mock 여부를 밝힙니다."""
    return get_weather_impl(location, date)


if __name__ == "__main__":
    mcp.run(transport="stdio")
