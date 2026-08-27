"""두 MCP 공개 웹 앱의 핵심 계약 테스트."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from web_app import _build_course, app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def payload(**overrides):
    value = {
        "location": "부산",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "companion": "couple",
    }
    value.update(overrides)
    return value


def test_public_ui_is_utf8_and_has_only_simple_course_inputs(client: TestClient) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert "누구와 갈지만 고르면" in home.text
    assert "같이 가는 오늘의 코스" in home.text
    assert all(label in home.text for label in ("친구", "가족", "연인"))
    assert "Weather MCP" in home.text and "Tour MCP" in home.text
    assert "Booking MCP" not in home.text and "Route MCP" not in home.text
    assert home.text.count("<select") == 1
    assert home.text.count('type="radio"') == 3
    assert home.text.count('type="number"') == 0
    assert "max_hotel_price" not in home.text
    assert "\ufffd" not in home.text
    assert "dapi.kakao.com" in home.headers["content-security-policy"]
    assert "t1.daumcdn.net" in home.headers["content-security-policy"]


def test_health_reports_exactly_two_http_servers(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mcp"] == "2_streamable_http_servers_ready"
    assert body["servers"] == ["weather", "tour"]
    assert body["tools"] == [
        "get_current_weather",
        "get_weather_forecast",
        "search_hotels",
        "search_spots",
    ]


def test_trip_brief_calls_both_servers_and_builds_three_stop_course(client: TestClient) -> None:
    response = client.post("/api/v1/trip-briefs", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["intent_summary"]["location"] == "부산"
    assert body["intent_summary"]["companion"] == "couple"
    assert body["intent_summary"]["companion_label"] == "연인"
    assert "hotels" not in body and "spots" not in body
    assert body["course"]["stop_count"] == 3
    assert [stop["sequence"] for stop in body["course"]["stops"]] == [1, 2, 3]
    assert body["mcp_execution"]["servers_called"] == ["weather", "tour"]
    assert body["mcp_execution"]["transport"] == "streamable_http"
    assert {item["tool"] for item in body["mcp_execution"]["trace"]} == {
        "get_current_weather",
        "get_weather_forecast",
        "search_spots",
    }
    assert all(item["transport"] == "streamable_http" for item in body["mcp_execution"]["trace"])


@pytest.mark.parametrize(
    ("companion", "first_category"),
    [("friend", "culture"), ("family", "history"), ("couple", "nature")],
)
def test_companion_changes_course_order(companion: str, first_category: str) -> None:
    spots = [
        {"id": category, "name": category, "category": category}
        for category in ("history", "culture", "nature", "night_view")
    ]
    course = _build_course("부산", companion, spots)
    assert course["stop_count"] == 3
    assert course["stops"][0]["category"] == first_category


def test_invalid_or_legacy_input_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/trip-briefs", json=payload(companion="coworker")).status_code == 422
    assert client.post("/api/v1/trip-briefs", json=payload(max_hotel_price=150_000)).status_code == 422
