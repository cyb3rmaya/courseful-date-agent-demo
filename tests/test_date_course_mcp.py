"""실제 stdio 연결에서 MCP Tool 발견/호출 계약을 확인합니다."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from _date_course_client import connect_to_date_course_server  # noqa: E402
from ai_agent import REQUIRED_TOOLS  # noqa: E402


def test_date_course_server_exposes_plan_tools() -> None:
    async def scenario() -> None:
        async with connect_to_date_course_server() as session:
            tools = (await session.list_tools()).tools
            assert {tool.name for tool in tools} == REQUIRED_TOOLS

            result = await session.call_tool(
                "get_weather",
                {"location": "부산", "date": "2026-08-26"},
            )
            assert result.isError is False
            assert result.structuredContent["source"] == "mock-weather-provider"
            assert result.structuredContent["condition"] == "rain"

            tour_result = await session.call_tool(
                "get_tourist_attractions",
                {"city": "서울", "categories": ["역사관광"], "limit": 6},
            )
            assert tour_result.isError is False
            assert tour_result.structuredContent["source"] == "local-tour-catalog"
            assert tour_result.structuredContent["count"] >= 2

    asyncio.run(scenario())


def test_server_rejects_invalid_course_time_schema() -> None:
    async def scenario() -> None:
        async with connect_to_date_course_server() as session:
            result = await session.call_tool(
                "validate_course",
                {
                    "intent": {
                        "companion_type": "couple",
                        "location": "부산",
                        "date": "2026-08-26",
                        "start_time": "14:00",
                        "end_time": "21:00",
                        "party_size": 2,
                        "transportation": "public_transport",
                    },
                    "stops": [
                        {
                            "stop_id": "stop_1",
                            "place_id": "busan-cafe-1",
                            "start_time": "not-a-time",
                            "end_time": "15:00",
                        }
                    ],
                },
            )
            assert result.isError is True

    asyncio.run(scenario())


def test_server_rejects_unsupported_tour_city_schema() -> None:
    async def scenario() -> None:
        async with connect_to_date_course_server() as session:
            result = await session.call_tool(
                "get_tourist_attractions",
                {"city": "제주"},
            )
            assert result.isError is True

    asyncio.run(scenario())
