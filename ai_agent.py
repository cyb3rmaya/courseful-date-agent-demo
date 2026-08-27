"""두 Streamable HTTP MCP Server를 발견해 호출하는 최소 AI Agent."""

from __future__ import annotations

import json
from contextlib import AbstractAsyncContextManager
from typing import Any, Callable

from openai import AsyncOpenAI

from _multi_mcp_client import connect_to_mcp_servers


REQUIRED_TOOLS = {
    "get_current_weather",
    "get_weather_forecast",
    "search_hotels",
    "search_spots",
}
ACTIVE_COURSE_TOOLS = {
    "get_current_weather",
    "get_weather_forecast",
    "search_spots",
}
# 이전 1서버 stdio 학습 예제의 독립 테스트 호환용입니다. 활성 레지스트리에는 포함되지 않습니다.
COURSE_REQUIRED_TOOLS = {
    "get_weather",
    "search_places",
    "get_place_details",
    "calculate_route",
    "search_date_context",
    "estimate_course_budget",
    "validate_course",
    "get_tourist_attractions",
}
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """당신은 한국 국내 나들이 코스 Agent입니다.
사용자 요청에서 지역, 날짜, 동행 유형(친구·가족·연인)을 파악하세요.
현재 날씨는 get_current_weather, 날짜 예보는 get_weather_forecast,
코스 후보는 search_spots를 사용합니다. 호텔과 가격은 묻거나 검색하지 마세요.
요청을 충족하기 전에 필요한 Tool을 실제로 호출하고, Tool 결과에 없는 내용을 만들지 마세요.
source, provider_status, warning을 숨기지 마세요.
장소는 세 곳만 고르고 동행 유형에 맞는 순서로 연결하세요.
친구는 문화→자연→야경, 가족은 역사→문화→자연, 연인은 자연→문화→야경 순서를 우선합니다.
마지막 답변은 다음 JSON 형태로만 작성하세요.
{
  "intent_summary": {"location": "", "date": "", "companion": "friend|family|couple"},
  "weather": {"current": {}, "forecast": {}},
  "course": {"title": "", "stops": []},
  "warnings": []
}
"""


def _tool_definition(tool: Any) -> dict[str, Any]:
    dumped = tool.model_dump(by_alias=True) if hasattr(tool, "model_dump") else {}
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or tool.name,
        "parameters": dumped.get("inputSchema") or dumped.get("input_schema") or {"type": "object", "properties": {}},
    }


def _tool_payload(result: Any) -> Any:
    if getattr(result, "structuredContent", None) is not None:
        return result.structuredContent
    texts = [item.text for item in getattr(result, "content", []) if getattr(item, "type", None) == "text"]
    raw = "\n".join(texts)
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"text": raw}


class DateCourseAgent:
    """기존 06 진입점 이름을 유지하면서 역할은 여행 브리프로 축소합니다."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str = "",
        client: Any | None = None,
        connector: Callable[[], AbstractAsyncContextManager] = connect_to_mcp_servers,
    ) -> None:
        self.model = model
        self.client = client or (AsyncOpenAI(api_key=api_key) if api_key else None)
        self.connector = connector

    async def answer(self, question: str) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY가 필요합니다. 공개 웹 데모는 키 없이 결정론적 MCP 호출을 사용합니다.")

        async with self.connector() as mcp_client:
            discovered = (await mcp_client.list_tools()).tools
            available = {tool.name for tool in discovered}
            missing = ACTIVE_COURSE_TOOLS - available
            if missing:
                raise RuntimeError("필수 MCP Tool이 없습니다: " + ", ".join(sorted(missing)))
            tools = [_tool_definition(tool) for tool in discovered]
            trace: list[dict[str, Any]] = []
            previous_response_id: str | None = None
            input_items: Any = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ]

            for _ in range(MAX_TOOL_ROUNDS):
                request: dict[str, Any] = {"model": self.model, "input": input_items, "tools": tools}
                if previous_response_id:
                    request["previous_response_id"] = previous_response_id
                response = await self.client.responses.create(**request)
                previous_response_id = response.id
                calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
                if not calls:
                    try:
                        final = json.loads(response.output_text or "{}")
                    except json.JSONDecodeError:
                        final = {"answer": response.output_text}
                    final["agent_execution"] = {
                        "transport": "streamable_http",
                        "servers": list(mcp_client.server_names),
                        "discovered_tools": sorted(available),
                        "trace": trace,
                    }
                    return final

                outputs = []
                for call in calls:
                    arguments: dict[str, Any] = {}
                    try:
                        arguments = json.loads(call.arguments or "{}")
                        if call.name not in available:
                            raise ValueError(f"허용되지 않은 Tool: {call.name}")
                        result = await mcp_client.call_tool(call.name, arguments)
                        payload = _tool_payload(result)
                        is_error = bool(getattr(result, "isError", False))
                    except Exception as exc:
                        payload = {"error": str(exc)}
                        is_error = True
                    trace.append({
                        "server": mcp_client.tool_to_server.get(call.name),
                        "tool": call.name,
                        "arguments": arguments,
                        "is_error": is_error,
                        "result": payload,
                    })
                    outputs.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(payload, ensure_ascii=False),
                    })
                input_items = outputs
            raise RuntimeError("Agent Tool 호출 횟수 제한을 초과했습니다.")

    async def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result


TravelAgent = DateCourseAgent

__all__ = [
    "ACTIVE_COURSE_TOOLS",
    "COURSE_REQUIRED_TOOLS",
    "DateCourseAgent",
    "MAX_TOOL_ROUNDS",
    "REQUIRED_TOOLS",
    "TravelAgent",
]
