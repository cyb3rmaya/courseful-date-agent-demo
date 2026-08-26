"""Date course MCP stdio Server 연결 도우미입니다."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("date_course_mcp_server.py")


@asynccontextmanager
async def connect_to_date_course_server():
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


__all__ = ["connect_to_date_course_server"]
