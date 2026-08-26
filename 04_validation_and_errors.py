"""잘못된 arguments가 MCP Tool 실행 오류로 반환되는지 확인합니다."""

import asyncio

from _stdio_client import connect_to_travel_server


async def main() -> None:
    async with connect_to_travel_server() as session:
        result = await session.call_tool(
            "search_hotels",
            {"city": "부산", "max_price": -1},
        )
        print("isError:", result.isError)
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
