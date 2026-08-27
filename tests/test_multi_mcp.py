"""두 Streamable HTTP MCP Server의 발견과 라우팅 통합 테스트."""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from _multi_mcp_client import connect_to_mcp_servers, load_server_specs  # noqa: E402
from ai_agent import REQUIRED_TOOLS  # noqa: E402


def test_registry_declares_two_streamable_http_servers() -> None:
    specs = load_server_specs()
    assert [spec.name for spec in specs] == ["weather", "tour"]
    assert all(spec.transport == "streamable_http" for spec in specs)
    assert specs[0].url.endswith(":8101/mcp")
    assert specs[1].url.endswith(":8102/mcp")


def test_multi_mcp_discovers_and_routes_four_tools() -> None:
    async def scenario() -> None:
        async with connect_to_mcp_servers() as client:
            assert client.server_names == ("weather", "tour")
            assert {tool.name for tool in (await client.list_tools()).tools} == REQUIRED_TOOLS
            assert client.tool_to_server == {
                "get_current_weather": "weather",
                "get_weather_forecast": "weather",
                "search_hotels": "tour",
                "search_spots": "tour",
            }
            current = await client.call_tool("get_current_weather", {"location": "부산"})
            forecast = await client.call_tool(
                "get_weather_forecast",
                {"location": "부산", "date": (date.today() + timedelta(days=1)).isoformat()},
            )
            hotels = await client.call_tool(
                "search_hotels",
                {"location": "부산", "max_price_per_night": 150_000},
            )
            spots = await client.call_tool("search_spots", {"location": "부산"})
            assert current.isError is False
            assert forecast.isError is False
            assert hotels.structuredContent["count"] == 3
            assert spots.structuredContent["count"] >= 1

    asyncio.run(scenario())
