"""URI로 식별된 읽기 전용 MCP Resource를 조회합니다."""

import asyncio

from _stdio_client import connect_to_travel_server


async def main() -> None:
    async with connect_to_travel_server() as session:
        resources = await session.list_resources()
        for resource in resources.resources:
            print(f"Resource: {resource.uri} | {resource.name}")

        result = await session.read_resource("travel://policy/baggage")
        print("\nResource Content:")
        for content in result.contents:
            if hasattr(content, "text"):
                print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
