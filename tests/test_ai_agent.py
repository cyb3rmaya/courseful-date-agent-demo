"""축소된 AI Agent가 발견된 네 Tool만 호출하는지 검증합니다."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from ai_agent import DateCourseAgent, REQUIRED_TOOLS  # noqa: E402


class FakeTool:
    def __init__(self, name):
        self.name = name
        self.description = name

    def model_dump(self, **_kwargs):
        return {"inputSchema": {"type": "object", "properties": {}}}


class FakeMCP:
    server_names = ("weather", "tour")
    tool_to_server = {
        "get_current_weather": "weather",
        "get_weather_forecast": "weather",
        "search_hotels": "tour",
        "search_spots": "tour",
    }

    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=[FakeTool(name) for name in sorted(REQUIRED_TOOLS)])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(structuredContent={"source": "test", "tool": name}, content=[], isError=False)


class FakeResponses:
    def __init__(self):
        self.count = 0

    async def create(self, **_kwargs):
        self.count += 1
        if self.count == 1:
            calls = [
                SimpleNamespace(type="function_call", name=name, arguments="{}", call_id=f"call-{index}")
                for index, name in enumerate(sorted(REQUIRED_TOOLS))
            ]
            return SimpleNamespace(id="r1", output=calls, output_text="")
        return SimpleNamespace(id="r2", output=[], output_text=json.dumps({"hotels": [], "spots": []}))


class FakeOpenAI:
    def __init__(self):
        self.responses = FakeResponses()


def test_agent_uses_exactly_four_discovered_tools() -> None:
    mcp = FakeMCP()

    @asynccontextmanager
    async def connector():
        yield mcp

    agent = DateCourseAgent(model="fake", client=FakeOpenAI(), connector=connector)
    result = asyncio.run(agent.answer("부산 내일 날씨와 15만원 이하 호텔, 명소를 찾아줘"))
    assert {name for name, _ in mcp.calls} == REQUIRED_TOOLS
    assert result["agent_execution"]["transport"] == "streamable_http"
    assert result["agent_execution"]["servers"] == ["weather", "tour"]
    assert len(result["agent_execution"]["trace"]) == 4
