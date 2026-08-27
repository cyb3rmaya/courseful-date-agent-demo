"""JSON 레지스트리의 두 Streamable HTTP MCP Server를 발견하고 라우팅합니다."""

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
from urllib.parse import urlparse

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("mcp_servers.json")


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    transport: str
    url: str
    command: str | None
    args: tuple[str, ...]


def load_server_specs(path: Path = DEFAULT_REGISTRY_PATH) -> list[MCPServerSpec]:
    """version 2 레지스트리를 검증하고 환경변수 URL을 우선 적용합니다."""
    registry_path = path.resolve()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if data.get("version") != 2 or not isinstance(data.get("servers"), dict):
        raise ValueError("mcp_servers.json에는 version 2와 servers 객체가 필요합니다.")

    specs: list[MCPServerSpec] = []
    for name, raw in data["servers"].items():
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        if raw.get("transport") != "streamable_http":
            raise ValueError(f"{name}: transport는 streamable_http여야 합니다.")
        url_env = raw.get("url_env")
        configured_url = os.getenv(url_env, "").strip() if isinstance(url_env, str) else ""
        url = configured_url or raw.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"{name}: 유효한 Streamable HTTP URL이 필요합니다.")

        raw_command = raw.get("command")
        command = sys.executable if raw_command == "{python}" else raw_command
        raw_args = raw.get("args", [])
        if command is not None and (not isinstance(command, str) or not command):
            raise ValueError(f"{name}: command가 올바르지 않습니다.")
        if not isinstance(raw_args, list) or not all(isinstance(item, str) for item in raw_args):
            raise ValueError(f"{name}: args는 문자열 배열이어야 합니다.")
        args = tuple(
            str((registry_path.parent / item).resolve())
            if item.endswith(".py") and not Path(item).is_absolute()
            else item
            for item in raw_args
        )
        # 원격 URL 환경변수를 사용하면 로컬 프로세스는 시작하지 않습니다.
        specs.append(MCPServerSpec(name, "streamable_http", url, None if configured_url else command, args))
    if not specs:
        raise ValueError("활성화된 MCP Server가 없습니다.")
    return specs


async def _port_is_open(host: str, port: int) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=0.4)
        writer.close()
        await writer.wait_closed()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def _wait_until_ready(spec: MCPServerSpec, process: asyncio.subprocess.Process | None) -> None:
    parsed = urlparse(spec.url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for _ in range(80):
        if process is not None and process.returncode is not None:
            raise RuntimeError(f"{spec.name} MCP Server가 시작 중 종료되었습니다. code={process.returncode}")
        if await _port_is_open(parsed.hostname or "127.0.0.1", port):
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(f"{spec.name} MCP Server 시작 시간이 초과되었습니다: {spec.url}")


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def _start_local_server(spec: MCPServerSpec) -> asyncio.subprocess.Process | None:
    if spec.command is None:
        await _wait_until_ready(spec, None)
        return None
    parsed = urlparse(spec.url)
    port = parsed.port or 80
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return None
    if await _port_is_open(parsed.hostname, port):
        return None
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    process = await asyncio.create_subprocess_exec(
        spec.command,
        *spec.args,
        cwd=str(DEFAULT_REGISTRY_PATH.parent),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await _wait_until_ready(spec, process)
    return process


class MultiMCPClient:
    """여러 HTTP Session의 Tool을 이름으로 발견하고 해당 서버로 라우팅합니다."""

    def __init__(self, sessions: dict[str, ClientSession], specs: list[MCPServerSpec]) -> None:
        self.sessions = sessions
        self.specs = {spec.name: spec for spec in specs}
        self._tools: list[Any] = []
        self._tool_to_server: dict[str, str] = {}

    @property
    def server_names(self) -> tuple[str, ...]:
        return tuple(self.sessions)

    @property
    def tool_to_server(self) -> dict[str, str]:
        return dict(self._tool_to_server)

    @property
    def server_urls(self) -> dict[str, str]:
        return {name: spec.url for name, spec in self.specs.items()}

    async def refresh_tools(self) -> None:
        results = await asyncio.gather(*(session.list_tools() for session in self.sessions.values()))
        tools: list[Any] = []
        routes: dict[str, str] = {}
        for server_name, result in zip(self.sessions, results, strict=True):
            for tool in result.tools:
                if tool.name in routes:
                    raise RuntimeError(f"중복 Tool 이름 '{tool.name}': {routes[tool.name]}, {server_name}")
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
    """필요한 로컬 HTTP 서버를 시작한 뒤 URL로 연결하고 모두 정리합니다."""
    specs = load_server_specs(registry_path)
    if server_names is not None:
        available = {spec.name for spec in specs}
        missing = server_names - available
        if missing:
            raise ValueError("등록되지 않은 MCP Server입니다: " + ", ".join(sorted(missing)))
        specs = [spec for spec in specs if spec.name in server_names]

    async with AsyncExitStack() as stack:
        for spec in specs:
            process = await _start_local_server(spec)
            if process is not None:
                stack.push_async_callback(_stop_process, process)

        sessions: dict[str, ClientSession] = {}
        for spec in specs:
            read_stream, write_stream, _session_id = await stack.enter_async_context(
                streamable_http_client(spec.url)
            )
            sessions[spec.name] = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await asyncio.gather(*(session.initialize() for session in sessions.values()))
        client = MultiMCPClient(sessions, specs)
        await client.refresh_tools()
        yield client


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "MCPServerSpec",
    "MultiMCPClient",
    "connect_to_mcp_servers",
    "load_server_specs",
]
