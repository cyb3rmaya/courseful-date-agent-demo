"""PLAN.md 계약을 강제하는 MCP 기반 DateCourseAgent입니다."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, Callable

from openai import AsyncOpenAI

from _date_course_client import connect_to_date_course_server


MAX_REPLAN_COUNT = 2
MAX_AGENT_TURNS = 14
TOOL_TIMEOUT_SECONDS = 10
REQUIRED_TOOLS = {
    "get_weather",
    "search_places",
    "get_place_details",
    "calculate_route",
    "search_date_context",
    "estimate_course_budget",
    "validate_course",
}

DEFAULT_INSTRUCTIONS = """You are DateCourseAgent.

Your job is not to simply list places. Your job is to create an executable
course from complex user constraints.

Separate hard constraints from soft preferences. First structure the request,
then decide which information is missing and select only the tools needed.
Use tools when external or current facts are needed. Never invent weather,
opening hours, route duration, live price, availability, or another dynamic
fact that is not present in tool results. Mock sources must be disclosed as a
warning; do not present them as live provider data.

Prefer deterministic tools for budget arithmetic, time overlap, opening-hours,
route limits, and hard-constraint checks. Before returning a final course:
1. build a candidate course;
2. call validate_course;
3. if validation fails, preserve unaffected stops;
4. replace only failed or conflicting stops where possible;
5. revalidate.

At most two replans are allowed after the first validation. If validation still
fails, return the best current course with the unresolved errors and conditions
the user could relax. Unknown prices must remain unknown.

Do not reveal hidden reasoning. Return concise rationale, warnings, and unknowns.
If critical information is missing and no safe assumption can produce a useful
result, ask only the minimum necessary question using validation.status
"needs_clarification".

After a successful validation, return only one JSON object with this shape:
{
  "intent_summary": {},
  "assumptions": [],
  "course": {"stops": []},
  "recommendation_rationale": [],
  "known_total_cost": 0,
  "unknown_costs": [],
  "warnings": [],
  "validation": {"status": "pass"}
}
"""


def _to_openai_tool(tool: Any) -> dict[str, Any]:
    """MCP Tool Schema를 OpenAI Responses API Function Tool로 변환합니다."""
    raw = tool.model_dump(by_alias=True)
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": raw["inputSchema"],
        "strict": False,
    }


def _text_result(result: Any) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return "\n".join(
        content.text for content in result.content if hasattr(content, "text")
    )


def _json_object(text: str) -> dict[str, Any] | None:
    """JSON 본문 또는 JSON code fence에서 객체 하나를 안전하게 추출합니다."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1])
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _error_output(code: str, message: str) -> str:
    return json.dumps(
        {"error_code": code, "message": message},
        ensure_ascii=False,
    )


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _validation_messages(validation: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    for issue in _list(validation.get("warnings")):
        if isinstance(issue, dict) and issue.get("message"):
            messages.append(str(issue["message"]))
    return messages


class DateCourseAgent:
    """LLM은 판단하고 MCP Tool은 조회·계산·검증하는 단일 Agent입니다."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str = "",
        instructions: str = DEFAULT_INSTRUCTIONS,
        client: Any | None = None,
        connector: Callable[..., Any] = connect_to_date_course_server,
    ) -> None:
        if client is None and not api_key:
            raise ValueError("OPENAI_API_KEY가 필요합니다.")
        self.model = model
        self.instructions = instructions
        self.client = client or AsyncOpenAI(api_key=api_key)
        self.connector = connector
        self._owns_client = client is None

    async def answer(self, question: str) -> dict[str, Any]:
        if not question.strip():
            raise ValueError("질문을 입력해 주세요.")

        trace: list[dict[str, Any]] = []
        llm_calls = 0
        validation_attempts = 0
        validation: dict[str, Any] = {}
        last_candidate_stops: list[dict[str, Any]] = []
        validated_stops: list[dict[str, Any]] | None = None
        protected_place_ids: dict[str, str] = {}
        agent_warnings: list[str] = []
        forced_validation = False

        async with self.connector() as session:
            discovered = (await session.list_tools()).tools
            available = {tool.name for tool in discovered}
            missing = REQUIRED_TOOLS - available
            if missing:
                raise RuntimeError(
                    "Date Course MCP Server의 필수 Tool이 없습니다: "
                    + ", ".join(sorted(missing))
                )
            openai_tools = [_to_openai_tool(tool) for tool in discovered]
            response = await self.client.responses.create(
                model=self.model,
                instructions=self.instructions,
                input=(
                    f"현재 날짜: {date.today().isoformat()}\n"
                    f"사용자 요청: {question.strip()}"
                ),
                tools=openai_tools,
                parallel_tool_calls=False,
            )
            llm_calls += 1

            for turn in range(1, MAX_AGENT_TURNS + 1):
                calls = [
                    item for item in response.output if item.type == "function_call"
                ]
                if not calls:
                    payload = _json_object(response.output_text) or {}
                    status = _dict(payload.get("validation")).get("status")
                    validation_done = bool(validation.get("valid")) or (
                        validation_attempts >= MAX_REPLAN_COUNT + 1
                    )
                    if validation_done or status == "needs_clarification":
                        return self._result(
                            question=question,
                            available=available,
                            trace=trace,
                            llm_calls=llm_calls,
                            validation_attempts=validation_attempts,
                            payload=payload,
                            validation=validation,
                            validated_stops=validated_stops,
                            fallback_stops=last_candidate_stops,
                            agent_warnings=agent_warnings,
                        )
                    if forced_validation:
                        agent_warnings.append(
                            "Agent가 필수 validate_course를 호출하지 않아 안전한 fallback을 반환했습니다."
                        )
                        break
                    forced_validation = True
                    response = await self.client.responses.create(
                        model=self.model,
                        instructions=self.instructions,
                        previous_response_id=response.id,
                        input=(
                            "최종 답변 전에 후보 코스를 만들고 validate_course를 호출하세요. "
                            "검증 없이 코스를 확정할 수 없습니다."
                        ),
                        tools=openai_tools,
                        parallel_tool_calls=False,
                    )
                    llm_calls += 1
                    continue

                forced_validation = False
                tool_outputs: list[dict[str, str]] = []
                validated_this_turn = False
                exhausted_this_turn = False
                for call in calls:
                    arguments: dict[str, Any] = {}
                    is_error = False
                    locality_rejected = False
                    try:
                        parsed_arguments = json.loads(call.arguments)
                        if not isinstance(parsed_arguments, dict):
                            raise ValueError("Tool arguments는 JSON 객체여야 합니다.")
                        arguments = parsed_arguments
                    except (json.JSONDecodeError, ValueError) as exc:
                        output_text = _error_output("INVALID_ARGUMENTS", str(exc))
                        is_error = True
                    else:
                        if call.name not in available:
                            output_text = _error_output(
                                "TOOL_NOT_ALLOWED",
                                f"MCP Server가 제공하지 않는 Tool입니다: {call.name}",
                            )
                            is_error = True
                        else:
                            if call.name == "validate_course" and protected_place_ids:
                                candidate_by_id = {
                                    item.get("stop_id"): item.get("place_id")
                                    for item in _list(arguments.get("stops"))
                                    if isinstance(item, dict)
                                }
                                changed = [
                                    stop_id
                                    for stop_id, place_id in protected_place_ids.items()
                                    if candidate_by_id.get(stop_id) != place_id
                                ]
                                if changed:
                                    locality_rejected = True
                                    output_text = json.dumps(
                                        {
                                            "valid": False,
                                            "errors": [
                                                {
                                                    "code": "NON_LOCAL_REPLAN",
                                                    "severity": "error",
                                                    "stop_id": stop_id,
                                                    "message": "문제가 없던 Stop의 장소가 변경되었습니다.",
                                                    "suggested_action": "기존 place_id를 복원하고 실패한 Stop만 교체하세요.",
                                                }
                                                for stop_id in changed
                                            ],
                                            "warnings": [],
                                            "unknowns": [],
                                            "known_total_cost": validation.get(
                                                "known_total_cost", 0
                                            ),
                                            "unknown_costs": validation.get(
                                                "unknown_costs", []
                                            ),
                                            "total_route_time": validation.get(
                                                "total_route_time", 0
                                            ),
                                            "total_walking_distance": validation.get(
                                                "total_walking_distance", 0
                                            ),
                                            "source": "agent-locality-guard",
                                            "error_code": None,
                                        },
                                        ensure_ascii=False,
                                    )
                            if not locality_rejected:
                                try:
                                    tool_result = await asyncio.wait_for(
                                        session.call_tool(call.name, arguments),
                                        timeout=TOOL_TIMEOUT_SECONDS,
                                    )
                                    output_text = _text_result(tool_result)
                                    semantic_result = _json_object(output_text) or {}
                                    is_error = bool(tool_result.isError) or bool(
                                        semantic_result.get("error_code")
                                    )
                                except TimeoutError:
                                    output_text = _error_output(
                                        "TOOL_TIMEOUT",
                                        f"{call.name} Tool이 제한 시간 안에 응답하지 않았습니다.",
                                    )
                                    is_error = True
                                except Exception as exc:  # MCP 실패는 Agent 전체를 중단하지 않습니다.
                                    output_text = _error_output(
                                        "TOOL_EXECUTION_ERROR",
                                        f"{call.name} 실행 실패: {exc}",
                                    )
                                    is_error = True

                    trace.append(
                        {
                            "turn": turn,
                            "tool": call.name,
                            "arguments": arguments,
                            "is_error": is_error,
                            "result": output_text,
                        }
                    )
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": output_text,
                        }
                    )

                    if call.name == "validate_course" and not is_error:
                        validation_attempts += 1
                        last_candidate_stops = [
                            item
                            for item in _list(arguments.get("stops"))
                            if isinstance(item, dict)
                        ]
                        parsed_validation = _json_object(output_text)
                        if parsed_validation is not None:
                            validation = parsed_validation
                        if validation.get("valid") is True:
                            validated_stops = last_candidate_stops
                            validated_this_turn = True
                        elif validation_attempts >= MAX_REPLAN_COUNT + 1:
                            exhausted_this_turn = True
                        elif not locality_rejected:
                            failed_stop_ids = {
                                issue.get("stop_id")
                                for issue in _list(validation.get("errors"))
                                if isinstance(issue, dict) and issue.get("stop_id")
                            }
                            protected_place_ids = (
                                {
                                    str(item["stop_id"]): str(item["place_id"])
                                    for item in last_candidate_stops
                                    if item.get("stop_id") not in failed_stop_ids
                                    and item.get("stop_id")
                                    and item.get("place_id")
                                }
                                if failed_stop_ids
                                else {}
                            )

                if validated_this_turn or exhausted_this_turn:
                    if exhausted_this_turn:
                        agent_warnings.append(
                            "최대 2회 재계획 후에도 검증을 통과하지 못했습니다."
                        )
                    response = await self.client.responses.create(
                        model=self.model,
                        instructions=self.instructions,
                        previous_response_id=response.id,
                        input=tool_outputs,
                    )
                else:
                    response = await self.client.responses.create(
                        model=self.model,
                        instructions=self.instructions,
                        previous_response_id=response.id,
                        input=tool_outputs,
                        tools=openai_tools,
                        parallel_tool_calls=False,
                    )
                llm_calls += 1

            agent_warnings.append("Agent 최대 실행 횟수에 도달해 fallback을 반환했습니다.")
            return self._result(
                question=question,
                available=available,
                trace=trace,
                llm_calls=llm_calls,
                validation_attempts=validation_attempts,
                payload={},
                validation=validation,
                validated_stops=validated_stops,
                fallback_stops=last_candidate_stops,
                agent_warnings=agent_warnings,
            )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.close()

    def _result(
        self,
        *,
        question: str,
        available: set[str],
        trace: list[dict[str, Any]],
        llm_calls: int,
        validation_attempts: int,
        payload: dict[str, Any],
        validation: dict[str, Any],
        validated_stops: list[dict[str, Any]] | None,
        fallback_stops: list[dict[str, Any]],
        agent_warnings: list[str],
    ) -> dict[str, Any]:
        """LLM 표현과 무관하게 PLAN.md Structured Output Contract를 보장합니다."""
        model_course = _dict(payload.get("course"))
        course_stops = validated_stops
        if course_stops is None:
            course_stops = fallback_stops or [
                item
                for item in _list(model_course.get("stops"))
                if isinstance(item, dict)
            ]

        if validation.get("valid") is True:
            validation_status = "pass"
        elif validation:
            validation_status = "fail"
        else:
            requested_status = _dict(payload.get("validation")).get("status")
            validation_status = (
                "needs_clarification"
                if requested_status == "needs_clarification"
                else "fallback"
            )

        warnings = [str(item) for item in _list(payload.get("warnings"))]
        warnings.extend(_validation_messages(validation))
        warnings.extend(agent_warnings)
        if any(
            isinstance(item, dict) and str(item.get("source", "")).startswith("mock-")
            for item in (_json_object(entry["result"]) or {} for entry in trace)
        ):
            warnings.append("현재 예제는 실시간 Provider가 아닌 Mock 데이터를 사용합니다.")
        warnings = list(dict.fromkeys(warnings))

        validation_output: dict[str, Any] = {"status": validation_status}
        if validation:
            validation_output.update(
                {
                    "errors": _list(validation.get("errors")),
                    "warnings": _list(validation.get("warnings")),
                    "unknowns": _list(validation.get("unknowns")),
                }
            )

        return {
            "intent_summary": _dict(payload.get("intent_summary")),
            "assumptions": [str(item) for item in _list(payload.get("assumptions"))],
            "course": {**model_course, "stops": course_stops},
            "recommendation_rationale": [
                str(item) for item in _list(payload.get("recommendation_rationale"))
            ],
            "known_total_cost": int(validation.get("known_total_cost", 0)),
            "unknown_costs": [
                str(item) for item in _list(validation.get("unknown_costs"))
            ],
            "warnings": warnings,
            "validation": validation_output,
            "agent_execution": {
                "question": question,
                "model": self.model,
                "discovered_tools": sorted(available),
                "llm_calls": llm_calls,
                "replan_count": max(0, validation_attempts - 1),
                "trace": trace,
            },
        }


# 기존 학습 코드에서 가져다 쓸 때 이름 변경으로 깨지지 않도록 제한적으로 유지합니다.
TravelAgent = DateCourseAgent


__all__ = [
    "DateCourseAgent",
    "MAX_REPLAN_COUNT",
    "TravelAgent",
]
