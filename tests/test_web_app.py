"""무료 공개 FastAPI 앱의 핵심 동작을 검증합니다."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


MODULE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

from web_app import app  # noqa: E402


client = TestClient(app)


def _payload(**overrides):
    payload = {
        "request": "비가 오면 실내에서 대화하기 좋은 부산 커플 코스",
        "location": "부산",
        "companion_type": "couple",
        "date": "2026-08-26",
        "start_time": "14:00",
        "end_time": "21:00",
        "party_size": 2,
        "budget": 100_000,
        "transportation": "public_transport",
        "hard_constraints": ["비 오면 실내"],
        "soft_preferences": ["카페", "대화"],
        "tourism_categories": ["문화관광", "도시명소"],
    }
    payload.update(overrides)
    return payload


def test_public_ui_and_health() -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert "Courseful" in home.text
    assert "가볼 곳부터 이동시간까지" in home.text
    assert "Mock Agent" not in home.text
    assert "�" not in home.text
    assert "default-src 'self'" in home.headers["content-security-policy"]

    assert client.head("/").status_code == 200
    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "mode": "deterministic_mock",
        "storage": "none",
    }


def test_course_endpoint_obeys_rainy_indoor_constraint() -> None:
    response = client.post("/api/v1/course-plans", json=_payload())
    assert response.status_code == 200
    result = response.json()

    assert result["validation"]["status"] == "pass"
    assert len(result["course"]["stops"]) >= 2
    assert all(stop["indoor"] is True for stop in result["course"]["stops"])
    assert result["known_total_cost"] <= 100_000
    assert result["agent_execution"]["mode"] == "deterministic_mock"
    assert result["tourism"]["source"] == "local-tour-catalog"
    assert result["tourism"]["count"] >= 1
    assert "get_tourist_attractions" in result["agent_execution"]["tools"]
    assert any("Mock" in warning for warning in result["warnings"])


def test_invalid_time_range_returns_422() -> None:
    response = client.post(
        "/api/v1/course-plans",
        json=_payload(start_time="21:00", end_time="14:00"),
    )
    assert response.status_code == 422
    assert "종료 시간" in response.json()["detail"]
