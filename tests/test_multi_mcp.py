"""JSON 레지스트리로 네 MCP Server를 동시에 연결하는 통합 테스트입니다."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from _multi_mcp_client import connect_to_mcp_servers, load_server_specs  # noqa: E402
from ai_agent import REQUIRED_TOOLS  # noqa: E402


def test_registry_declares_four_stdio_servers() -> None:
    specs = load_server_specs()
    assert [spec.name for spec in specs] == ["weather", "tour", "route", "booking"]
    assert all(spec.transport == "stdio" for spec in specs)
    assert all(Path(spec.args[0]).is_absolute() for spec in specs)


def test_multi_mcp_discovers_and_routes_all_tools() -> None:
    async def scenario() -> None:
        async with connect_to_mcp_servers() as client:
            assert client.server_names == ("weather", "tour", "route", "booking")
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == REQUIRED_TOOLS
            assert client.tool_to_server["get_weather"] == "weather"
            assert client.tool_to_server["get_tourist_attractions"] == "tour"
            assert client.tool_to_server["validate_course"] == "route"
            assert client.tool_to_server["confirm_booking"] == "booking"

            weather = await client.call_tool(
                "get_weather",
                {"location": "부산", "date": "2026-08-27"},
            )
            assert weather.isError is False
            assert weather.structuredContent["source"] == "mock-weather-provider"

            draft = await client.call_tool(
                "prepare_booking",
                {
                    "course_id": "course-test",
                    "date": "2026-08-27",
                    "party_size": 2,
                    "stops": [
                        {
                            "place_id": "busan-museum-1",
                            "name": "부산 현대미술관",
                            "start_time": "14:00",
                        }
                    ],
                },
            )
            assert draft.isError is False
            token = draft.structuredContent["booking_token"]
            rejected = await client.call_tool(
                "confirm_booking",
                {"booking_token": token, "user_confirmed": False},
            )
            assert rejected.structuredContent["error_code"] == "CONFIRMATION_REQUIRED"

    asyncio.run(scenario())
