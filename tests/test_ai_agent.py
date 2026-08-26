"""DateCourseAgent의 검증 및 국소 재계획 경계 테스트입니다."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from ai_agent import DateCourseAgent, REQUIRED_TOOLS  # noqa: E402


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name

    def model_dump(self, **_kwargs):
        return {"inputSchema": {"type": "object", "properties": {}}}


class FakeResponses:
    def __init__(self, responses) -> None:
        self._responses = iter(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


class FakeClient:
    def __init__(self, responses) -> None:
        self.responses = FakeResponses(responses)


class FakeSession:
    def __init__(self, validation_results) -> None:
        self.validation_results = iter(validation_results)
        self.called_arguments = []

    async def list_tools(self):
        return SimpleNamespace(tools=[FakeTool(name) for name in sorted(REQUIRED_TOOLS)])

    async def call_tool(self, name, arguments):
        self.called_arguments.append((name, arguments))
        if name != "validate_course":
            raise AssertionError(f"예상하지 않은 Tool: {name}")
        payload = next(self.validation_results)
        return SimpleNamespace(
            structuredContent=payload,
            content=[],
            isError=False,
        )


def _response(response_id: str, *, call=None, output_text=""):
    output = [] if call is None else [call]
    return SimpleNamespace(id=response_id, output=output, output_text=output_text)


def _call(call_id: str, arguments):
    return SimpleNamespace(
        type="function_call",
        name="validate_course",
        arguments=json.dumps(arguments, ensure_ascii=False),
        call_id=call_id,
    )


def _arguments(stops):
    return {
        "intent": {
            "companion_type": "couple",
            "location": "부산",
            "date": "2026-08-26",
            "start_time": "14:00",
            "end_time": "21:00",
            "party_size": 2,
            "budget": 100_000,
            "transportation": "public_transport",
        },
        "stops": stops,
    }


def _stop(stop_id: str, place_id: str):
    return {
        "stop_id": stop_id,
        "place_id": place_id,
        "start_time": "14:00" if stop_id == "stop_1" else "16:00",
        "end_time": "15:00" if stop_id == "stop_1" else "17:00",
        "expected_cost": 10_000,
    }


def _validation(valid: bool, *, failed_stop_id=None):
    errors = []
    if failed_stop_id:
        errors.append(
            {
                "code": "CLOSED_AT_VISIT_TIME",
                "severity": "error",
                "stop_id": failed_stop_id,
                "message": "휴무",
            }
        )
    return {
        "valid": valid,
        "errors": errors,
        "warnings": [],
        "unknowns": [],
        "known_total_cost": 40_000,
        "unknown_costs": [],
        "total_route_time": 20,
        "total_walking_distance": 300,
        "source": "deterministic-course-validator",
        "error_code": None,
    }


def test_validated_stops_override_unvalidated_final_text() -> None:
    import asyncio

    validated = [_stop("stop_1", "busan-cafe-1")]
    hallucinated = [_stop("stop_1", "unknown-place")]
    responses = [
        _response("r1", call=_call("c1", _arguments(validated))),
        _response(
            "r2",
            output_text=json.dumps(
                {
                    "intent_summary": {"location": "부산"},
                    "course": {"stops": hallucinated},
                    "validation": {"status": "pass"},
                },
                ensure_ascii=False,
            ),
        ),
    ]
    session = FakeSession([_validation(True)])

    @asynccontextmanager
    async def connector():
        yield session

    agent = DateCourseAgent(
        model="fake-model",
        client=FakeClient(responses),
        connector=connector,
    )
    result = asyncio.run(agent.answer("부산 데이트 코스를 만들어 줘"))

    assert result["validation"]["status"] == "pass"
    assert result["course"]["stops"] == validated
    assert result["known_total_cost"] == 40_000
    assert result["agent_execution"]["replan_count"] == 0


def test_local_replan_guard_preserves_unaffected_place() -> None:
    import asyncio

    first = [_stop("stop_1", "keep-me"), _stop("stop_2", "closed-place")]
    non_local = [_stop("stop_1", "changed-illegally"), _stop("stop_2", "replacement")]
    local = [_stop("stop_1", "keep-me"), _stop("stop_2", "replacement")]
    responses = [
        _response("r1", call=_call("c1", _arguments(first))),
        _response("r2", call=_call("c2", _arguments(non_local))),
        _response("r3", call=_call("c3", _arguments(local))),
        _response("r4", output_text="{}"),
    ]
    # 두 번째 호출은 Agent locality guard에서 차단되므로 MCP Validator는 두 번만 실행됩니다.
    session = FakeSession(
        [_validation(False, failed_stop_id="stop_2"), _validation(True)]
    )

    @asynccontextmanager
    async def connector():
        yield session

    agent = DateCourseAgent(
        model="fake-model",
        client=FakeClient(responses),
        connector=connector,
    )
    result = asyncio.run(agent.answer("휴무 장소만 바꿔 줘"))

    assert result["validation"]["status"] == "pass"
    assert result["course"]["stops"] == local
    assert len(session.called_arguments) == 2
    assert result["agent_execution"]["trace"][1]["is_error"] is False
    guarded = json.loads(result["agent_execution"]["trace"][1]["result"])
    assert guarded["errors"][0]["code"] == "NON_LOCAL_REPLAN"
    assert result["agent_execution"]["replan_count"] == 2
