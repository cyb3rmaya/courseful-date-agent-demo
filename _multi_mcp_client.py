"""JSON 레지스트리에 등록된 여러 stdio MCP Server를 하나처럼 연결합니다."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("mcp_servers.json")


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    transport: str
    command: str
    args: tuple[str, ...]


def load_server_specs(path: Path = DEFAULT_REGISTRY_PATH) -> list[MCPServerSpec]:
    """설정 파일을 검증하고 활성화된 서버 정의만 반환합니다."""
    registry_path = path.resolve()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("servers"), dict):
        raise ValueError("mcp_servers.json은 version 1과 servers 객체가 필요합니다.")

    specs: list[MCPServerSpec] = []
    for name, raw in data["servers"].items():
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        transport = raw.get("transport")
        if transport != "stdio":
            raise ValueError(
                f"{name}: 현재 로컬 실행기는 stdio만 지원합니다. HTTP 배포는 별도 URL 어댑터가 필요합니다."
            )
        command = raw.get("command")
        args = raw.get("args", [])
        if not isinstance(command, str) or not command:
            raise ValueError(f"{name}: command가 필요합니다.")
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError(f"{name}: args는 문자열 배열이어야 합니다.")
        resolved_command = sys.executable if command == "{python}" else command
        resolved_args = tuple(
            str((registry_path.parent / item).resolve())
            if item.endswith(".py") and not Path(item).is_absolute()
            else item
            for item in args
        )
        specs.append(MCPServerSpec(name, transport, resolved_command, resolved_args))
    if not specs:
        raise ValueError("활성화된 MCP Server가 없습니다.")
    return specs


class MultiMCPClient:
    """여러 MCP Session의 Tool을 이름 기반으로 발견하고 올바른 서버로 라우팅합니다."""

    def __init__(self, sessions: dict[str, ClientSession]) -> None:
        self.sessions = sessions
        self._tools: list[Any] = []
        self._tool_to_server: dict[str, str] = {}

    @property
    def server_names(self) -> tuple[str, ...]:
        return tuple(self.sessions)

    @property
    def tool_to_server(self) -> dict[str, str]:
        return dict(self._tool_to_server)

    async def refresh_tools(self) -> None:
        results = await asyncio.gather(
            *(session.list_tools() for session in self.sessions.values())
        )
        tools: list[Any] = []
        routes: dict[str, str] = {}
        for server_name, result in zip(self.sessions, results, strict=True):
            for tool in result.tools:
                if tool.name in routes:
                    raise RuntimeError(
                        f"중복 Tool 이름 '{tool.name}': {routes[tool.name]}, {server_name}"
                    )
                routes[tool.name] = server_name
                tools.append(tool)
        self._tools = tools
        self._tool_to_server = routes

    async def list_tools(self) -> SimpleNamespace:
        if not self._tools:
            await self.refresh_tools()
        return SimpleNamespace(tools=list(self._tools))

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        if not self._tool_to_server:
            await self.refresh_tools()
        server_name = self._tool_to_server.get(name)
        if server_name is None:
            raise ValueError(f"등록된 MCP Server가 제공하지 않는 Tool입니다: {name}")
        return await self.sessions[server_name].call_tool(name, arguments)


@asynccontextmanager
async def connect_to_mcp_servers(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    server_names: set[str] | None = None,
):
    """활성화된 모든 stdio 서버를 한 수명 주기 안에서 동시에 유지합니다."""
    specs = load_server_specs(registry_path)
    if server_names is not None:
        available_names = {spec.name for spec in specs}
        missing_names = server_names - available_names
        if missing_names:
            raise ValueError(
                "등록되지 않은 MCP Server입니다: " + ", ".join(sorted(missing_names))
            )
        specs = [spec for spec in specs if spec.name in server_names]
    async with AsyncExitStack() as stack:
        sessions: dict[str, ClientSession] = {}
        for spec in specs:
            parameters = StdioServerParameters(
                command=spec.command,
                args=list(spec.args),
                env={
                    **os.environ,
                    "PYTHONUTF8": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
            )
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(parameters)
            )
            sessions[spec.name] = await stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
        await asyncio.gather(*(session.initialize() for session in sessions.values()))
        client = MultiMCPClient(sessions)
        await client.refresh_tools()
        yield client


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "MCPServerSpec",
    "MultiMCPClient",
    "connect_to_mcp_servers",
    "load_server_specs",
]
