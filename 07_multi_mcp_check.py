"""JSON 설정으로 네 개 MCP Server가 함께 연결되는지 확인하는 실행 예제입니다."""

from __future__ import annotations

import asyncio
import sys

from _multi_mcp_client import connect_to_mcp_servers


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


async def main() -> None:
    async with connect_to_mcp_servers() as client:
        tools = (await client.list_tools()).tools
        print("연결된 MCP Server:", ", ".join(client.server_names))
        for server_name in client.server_names:
            names = sorted(
                name
                for name, routed_server in client.tool_to_server.items()
                if routed_server == server_name
            )
            print(f"- {server_name}: {', '.join(names)}")

        weather = await client.call_tool(
            "get_weather",
            {"location": "부산", "date": "2026-08-27"},
        )
        draft = await client.call_tool(
            "prepare_booking",
            {
                "course_id": "course-multi-mcp-demo",
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
        print("발견한 Tool 수:", len(tools))
        print("날씨 source:", weather.structuredContent["source"])
        print("예약 초안 상태:", draft.structuredContent["status"])
        print("확정 Tool은 사용자 확인 전이므로 호출하지 않았습니다.")


if __name__ == "__main__":
    asyncio.run(main())
