"""두 MCP 공개 웹 앱의 핵심 계약 테스트."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from web_app import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def payload(**overrides):
    value = {
        "location": "부산",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "max_hotel_price": 150_000,
    }
    value.update(overrides)
    return value


def test_public_ui_is_utf8_and_has_three_inputs(client: TestClient) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert "날씨를 확인하고" in home.text
    assert "세 가지만 정하세요" in home.text
    assert "Weather MCP" in home.text and "Tour MCP" in home.text
    assert "Booking MCP" not in home.text and "Route MCP" not in home.text
    assert home.text.count("<select") == 1
    assert home.text.count("<input") == 2
    assert "\ufffd" not in home.text
    assert "dapi.kakao.com" in home.headers["content-security-policy"]


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


def test_trip_brief_calls_both_servers_and_filters_hotels(client: TestClient) -> None:
    response = client.post("/api/v1/trip-briefs", json=payload())
    assert response.status_code == 200
    body = response.json()
    assert body["intent_summary"]["location"] == "부산"
    assert all(item["price_per_night"] <= 150_000 for item in body["hotels"]["hotels"])
    assert body["spots"]["count"] >= 1
    assert body["mcp_execution"]["servers_called"] == ["weather", "tour"]
    assert body["mcp_execution"]["transport"] == "streamable_http"
    assert {item["tool"] for item in body["mcp_execution"]["trace"]} == {
        "get_current_weather",
        "get_weather_forecast",
        "search_hotels",
        "search_spots",
    }
    assert all(item["transport"] == "streamable_http" for item in body["mcp_execution"]["trace"])


def test_invalid_hotel_price_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/trip-briefs", json=payload(max_hotel_price=0)).status_code == 422
