"""MCP Server의 Tool을 발견하고 이름으로 호출합니다."""

import asyncio

from _stdio_client import connect_to_travel_server


async def main() -> None:
    async with connect_to_travel_server() as session:
        tools = await session.list_tools()
        print("발견한 Tool:")
        for tool in tools.tools:
            print(f"- {tool.name}: {tool.description}")

        result = await session.call_tool(
            "get_current_weather",
            {"city": "부산"},
        )
        print("\nTool Result:")
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
