"""두 Streamable HTTP MCP Server를 연결하는 무료 공개 여행 브리프 웹 앱."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date as date_type, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, field_validator

from _multi_mcp_client import MultiMCPClient, connect_to_mcp_servers


STATIC_DIR = Path(__file__).with_name("static")
load_dotenv(Path(__file__).with_name(".env"))


CompanionType = Literal["friend", "family", "couple"]

COURSE_PROFILES: dict[CompanionType, dict[str, Any]] = {
    "friend": {
        "label": "친구",
        "headline": "걷고, 보고, 밤 풍경으로 마무리하는 코스",
        "description": "대화가 끊기지 않도록 분위기가 다른 장소를 가볍게 이어 붙였습니다.",
        "categories": ["culture", "nature", "night_view", "history"],
        "guides": ["재미있게 시작", "천천히 걷기", "밤 풍경으로 마무리"],
    },
    "family": {
        "label": "가족",
        "headline": "함께 보고 편하게 걷는 가족 나들이 코스",
        "description": "볼거리와 산책을 섞어 세대가 달라도 무리 없이 즐기도록 구성했습니다.",
        "categories": ["history", "culture", "nature", "night_view"],
        "guides": ["차분하게 시작", "함께 둘러보기", "편안하게 산책"],
    },
    "couple": {
        "label": "연인",
        "headline": "산책에서 야경까지 자연스럽게 이어지는 데이트 코스",
        "description": "나란히 걷고 이야기하기 좋은 장소를 골라 마지막 풍경까지 연결했습니다.",
        "categories": ["nature", "culture", "night_view", "history"],
        "guides": ["천천히 걷기", "함께 둘러보기", "야경으로 마무리"],
    },
}


class TripBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: Literal["서울", "부산", "제주"] = "부산"
    date: str
    companion: CompanionType = "couple"

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        selected = date_type.fromisoformat(value)
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        if not today <= selected <= today + timedelta(days=15):
            raise ValueError("여행 날짜는 오늘부터 15일 안에서 선택해야 합니다.")
        return value


def _build_course(location: str, companion: CompanionType, spots: list[dict[str, Any]]) -> dict[str, Any]:
    profile = COURSE_PROFILES[companion]
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for category in profile["categories"]:
        match = next(
            (spot for spot in spots if spot.get("category") == category and str(spot.get("id")) not in used_ids),
            None,
        )
        if match:
            selected.append(match)
            used_ids.add(str(match.get("id")))
        if len(selected) == 3:
            break
    for spot in spots:
        spot_id = str(spot.get("id"))
        if spot_id not in used_ids and len(selected) < 3:
            selected.append(spot)
            used_ids.add(spot_id)

    stops = [
        {**spot, "sequence": index + 1, "guide": profile["guides"][index]}
        for index, spot in enumerate(selected)
    ]
    return {
        "location": location,
        "companion": companion,
        "companion_label": profile["label"],
        "title": f"{location} {profile['label']} 코스",
        "headline": profile["headline"],
        "description": profile["description"],
        "stop_count": len(stops),
        "stops": stops,
    }


def _tool_payload(result: Any) -> dict[str, Any]:
    if getattr(result, "structuredContent", None) is not None:
        return dict(result.structuredContent)
    raw = "\n".join(
        item.text
        for item in getattr(result, "content", [])
        if getattr(item, "type", None) == "text"
    )
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"text": raw}


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with connect_to_mcp_servers() as client:
        app.state.mcp = client
        yield


app = FastAPI(
    title="Two MCP Travel Brief",
    version="2.0.0",
    description="Weather와 Tour 두 Streamable HTTP MCP Server를 실제 호출하는 공개 데모",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: "
        "https://*.kakaocdn.net https://*.daumcdn.net http://*.kakaocdn.net http://*.daumcdn.net; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' https://dapi.kakao.com http://dapi.kakao.com "
        "https://t1.daumcdn.net http://t1.daumcdn.net; "
        "connect-src 'self' https://*.kakao.com https://*.daum.net "
        "http://*.kakao.com http://*.daum.net; frame-ancestors 'none'"
    )
    return response


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.head("/", include_in_schema=False)
async def home_head() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    client: MultiMCPClient = request.app.state.mcp
    return {
        "status": "ok",
        "mcp": "2_streamable_http_servers_ready",
        "servers": list(client.server_names),
        "tools": sorted(client.tool_to_server),
        "weather_provider_configured": bool(os.getenv("KMA_SERVICE_KEY", "").strip()),
        "kakao_map_configured": bool(os.getenv("KAKAO_JAVASCRIPT_KEY", "").strip()),
        "kakao_local_configured": bool(os.getenv("KAKAO_REST_API_KEY", "").strip()),
        "storage": "none",
    }


@app.get("/api/v1/public-config")
async def public_config() -> dict[str, Any]:
    # JavaScript 지도 키는 공식 SDK가 브라우저에서 사용하므로 공개되는 플랫폼 키입니다.
    # Kakao Developers에서 허용 도메인을 반드시 제한해야 합니다.
    key = os.getenv("KAKAO_JAVASCRIPT_KEY", "").strip()
    return {
        "kakao_map_enabled": bool(key),
        "kakao_javascript_key": key,
        "setup": {
            "kma": "https://www.data.go.kr/data/15084084/openapi.do",
            "kakao": "https://developers.kakao.com/console/app",
        },
    }


async def _run_bundle(
    client: MultiMCPClient,
    calls: list[tuple[str, dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    results: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    for tool, arguments in calls:
        started = time.perf_counter()
        result = await client.call_tool(tool, arguments)
        payload = _tool_payload(result)
        if getattr(result, "isError", False):
            raise RuntimeError(f"{tool}: MCP Tool 실행 오류")
        results[tool] = payload
        trace.append(
            {
                "server": client.tool_to_server[tool],
                "tool": tool,
                "arguments": arguments,
                "transport": "streamable_http",
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "source": payload.get("source"),
                "provider_status": payload.get("provider_status"),
            }
        )
    return results, trace


@app.post("/api/v1/trip-briefs")
async def create_trip_brief(payload: TripBriefRequest, request: Request) -> dict[str, Any]:
    client: MultiMCPClient = request.app.state.mcp
    started = time.perf_counter()
    weather_calls = [
        ("get_current_weather", {"location": payload.location}),
        ("get_weather_forecast", {"location": payload.location, "date": payload.date}),
    ]
    tour_calls = [("search_spots", {"location": payload.location, "category": "all", "limit": 6})]
    try:
        (weather, weather_trace), (tour, tour_trace) = await asyncio.gather(
            _run_bundle(client, weather_calls),
            _run_bundle(client, tour_calls),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP Server 호출에 실패했습니다: {exc}") from exc

    current = weather["get_current_weather"]
    forecast = weather["get_weather_forecast"]
    spots = tour["search_spots"]
    course = _build_course(payload.location, payload.companion, spots.get("spots", []))
    warnings = list(
        dict.fromkeys(
            item
            for item in [current.get("warning"), forecast.get("warning"), spots.get("warning")]
            if item
        )
    )
    return {
        "request_id": f"trip-{uuid.uuid4().hex[:12]}",
        "intent_summary": {
            "location": payload.location,
            "date": payload.date,
            "companion": payload.companion,
            "companion_label": COURSE_PROFILES[payload.companion]["label"],
        },
        "weather": {"current": current, "forecast": forecast},
        "course": {
            **course,
            "source": spots.get("source"),
            "provider_status": spots.get("provider_status"),
        },
        "warnings": warnings,
        "mcp_execution": {
            "architecture": "two_independent_http_servers",
            "transport": "streamable_http",
            "servers_called": ["weather", "tour"],
            "registered_servers": list(client.server_names),
            "discovered_tools": sorted(client.tool_to_server),
            "trace": weather_trace + tour_trace,
            "parallel_server_calls": True,
            "total_duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
