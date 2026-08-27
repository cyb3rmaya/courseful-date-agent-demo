"""두 Streamable HTTP MCP Server와 네 Tool을 실제 호출해 확인합니다."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta

from _multi_mcp_client import connect_to_mcp_servers


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    target_date = (datetime.now() + timedelta(days=1)).date().isoformat()
    async with connect_to_mcp_servers() as client:
        tools = (await client.list_tools()).tools
        print("연결된 MCP Server:", ", ".join(client.server_names))
        for server_name in client.server_names:
            names = sorted(name for name, routed in client.tool_to_server.items() if routed == server_name)
            print(f"- {server_name}: {', '.join(names)}")

        current = await client.call_tool("get_current_weather", {"location": "부산"})
        forecast = await client.call_tool("get_weather_forecast", {"location": "부산", "date": target_date})
        hotels = await client.call_tool("search_hotels", {"location": "부산", "max_price_per_night": 150_000})
        spots = await client.call_tool("search_spots", {"location": "부산"})
        print("발견한 Tool 수:", len(tools))
        print("현재 날씨 source:", current.structuredContent["source"])
        print("예보 source:", forecast.structuredContent["source"])
        print("15만원 이하 호텔 수:", hotels.structuredContent["count"])
        print("명소 수:", spots.structuredContent["count"])


if __name__ == "__main__":
    asyncio.run(main())
