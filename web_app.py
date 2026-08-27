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
from pydantic import BaseModel, Field, field_validator

from _multi_mcp_client import MultiMCPClient, connect_to_mcp_servers


STATIC_DIR = Path(__file__).with_name("static")
load_dotenv(Path(__file__).with_name(".env"))


class TripBriefRequest(BaseModel):
    location: Literal["서울", "부산", "제주"] = "부산"
    date: str
    max_hotel_price: int = Field(default=150_000, ge=10_000, le=1_000_000)

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        selected = date_type.fromisoformat(value)
        today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        if not today <= selected <= today + timedelta(days=15):
            raise ValueError("여행 날짜는 오늘부터 15일 안에서 선택해야 합니다.")
        return value


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
        "default-src 'self'; img-src 'self' data: https://*.kakaocdn.net https://*.daumcdn.net; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' https://dapi.kakao.com; "
        "connect-src 'self' https://*.kakao.com https://*.daum.net; frame-ancestors 'none'"
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
    tour_calls = [
        (
            "search_hotels",
            {"location": payload.location, "max_price_per_night": payload.max_hotel_price, "limit": 5},
        ),
        ("search_spots", {"location": payload.location, "category": "all", "limit": 6}),
    ]
    try:
        (weather, weather_trace), (tour, tour_trace) = await asyncio.gather(
            _run_bundle(client, weather_calls),
            _run_bundle(client, tour_calls),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP Server 호출에 실패했습니다: {exc}") from exc

    current = weather["get_current_weather"]
    forecast = weather["get_weather_forecast"]
    hotels = tour["search_hotels"]
    spots = tour["search_spots"]
    warnings = [
        item
        for item in [current.get("warning"), forecast.get("warning"), spots.get("warning"), hotels.get("notice")]
        if item
    ]
    return {
        "request_id": f"trip-{uuid.uuid4().hex[:12]}",
        "intent_summary": {
            "location": payload.location,
            "date": payload.date,
            "max_hotel_price": payload.max_hotel_price,
        },
        "weather": {"current": current, "forecast": forecast},
        "hotels": hotels,
        "spots": spots,
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
