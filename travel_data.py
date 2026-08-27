"""Weather/Tour MCP 서버가 공유하는 외부 Provider 어댑터와 안전한 폴백 데이터."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field


SupportedCity = Literal["서울", "부산", "제주"]
SpotCategory = Literal["all", "nature", "culture", "history", "night_view"]

KST = ZoneInfo("Asia/Seoul")
KMA_BASE_URL = (
    "https://apis.data.go.kr/1360000/"
    "VilageFcstInfoService_2.0"
)
KAKAO_LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

CITY_META = {
    "서울": {"nx": 60, "ny": 127, "lat": 37.5665, "lng": 126.9780},
    "부산": {"nx": 98, "ny": 76, "lat": 35.1796, "lng": 129.0756},
    "제주": {"nx": 52, "ny": 38, "lat": 33.4996, "lng": 126.5312},
}


class WeatherCurrent(BaseModel):
    location: str
    observed_at: str
    condition: str
    temperature_c: float
    humidity_percent: int | None = None
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None
    source: str
    provider_status: Literal["live", "fallback"]
    fetched_at: str
    warning: str | None = None


class WeatherForecast(BaseModel):
    location: str
    date: str
    condition: str
    temperature_c: float
    min_temperature_c: float | None = None
    max_temperature_c: float | None = None
    rain_probability_percent: int | None = None
    source: str
    provider_status: Literal["live", "fallback"]
    fetched_at: str
    warning: str | None = None


class Hotel(BaseModel):
    id: str
    name: str
    location: str
    district: str
    price_per_night: int
    rating: float
    lat: float
    lng: float
    kakao_map_url: str


class HotelSearch(BaseModel):
    location: str
    max_price_per_night: int
    count: int
    hotels: list[Hotel]
    source: str
    fetched_at: str
    notice: str


class Spot(BaseModel):
    id: str
    name: str
    location: str
    category: str
    description: str
    address: str
    lat: float
    lng: float
    kakao_map_url: str


class SpotSearch(BaseModel):
    location: str
    category: str
    count: int
    spots: list[Spot]
    source: str
    provider_status: Literal["live", "fallback"]
    fetched_at: str
    warning: str | None = None


HOTELS = [
    Hotel(id="seoul-1", name="을지 스테이", location="서울", district="중구", price_per_night=98_000, rating=4.3, lat=37.5660, lng=126.9910, kakao_map_url="https://map.kakao.com/link/search/을지%20스테이"),
    Hotel(id="seoul-2", name="한강 시티 호텔", location="서울", district="마포구", price_per_night=132_000, rating=4.5, lat=37.5504, lng=126.9142, kakao_map_url="https://map.kakao.com/link/search/한강%20시티%20호텔"),
    Hotel(id="seoul-3", name="북촌 부티크", location="서울", district="종로구", price_per_night=149_000, rating=4.7, lat=37.5826, lng=126.9830, kakao_map_url="https://map.kakao.com/link/search/북촌%20부티크"),
    Hotel(id="seoul-4", name="남산 프리미어", location="서울", district="용산구", price_per_night=218_000, rating=4.8, lat=37.5512, lng=126.9882, kakao_map_url="https://map.kakao.com/link/search/남산%20프리미어"),
    Hotel(id="busan-1", name="광안 오션 스테이", location="부산", district="수영구", price_per_night=89_000, rating=4.4, lat=35.1532, lng=129.1187, kakao_map_url="https://map.kakao.com/link/search/광안%20오션%20스테이"),
    Hotel(id="busan-2", name="해운대 블루 호텔", location="부산", district="해운대구", price_per_night=119_000, rating=4.6, lat=35.1601, lng=129.1603, kakao_map_url="https://map.kakao.com/link/search/해운대%20블루%20호텔"),
    Hotel(id="busan-3", name="부산역 시티 스테이", location="부산", district="동구", price_per_night=145_000, rating=4.5, lat=35.1161, lng=129.0402, kakao_map_url="https://map.kakao.com/link/search/부산역%20시티%20스테이"),
    Hotel(id="busan-4", name="센텀 프리미어", location="부산", district="해운대구", price_per_night=209_000, rating=4.8, lat=35.1696, lng=129.1312, kakao_map_url="https://map.kakao.com/link/search/센텀%20프리미어"),
    Hotel(id="jeju-1", name="제주 돌담 스테이", location="제주", district="제주시", price_per_night=92_000, rating=4.4, lat=33.5104, lng=126.5220, kakao_map_url="https://map.kakao.com/link/search/제주%20돌담%20스테이"),
    Hotel(id="jeju-2", name="애월 바다 호텔", location="제주", district="애월읍", price_per_night=138_000, rating=4.6, lat=33.4622, lng=126.3115, kakao_map_url="https://map.kakao.com/link/search/애월%20바다%20호텔"),
    Hotel(id="jeju-3", name="서귀포 가든", location="제주", district="서귀포시", price_per_night=150_000, rating=4.7, lat=33.2477, lng=126.5627, kakao_map_url="https://map.kakao.com/link/search/서귀포%20가든"),
]


SPOTS = [
    Spot(id="seoul-palace", name="경복궁", location="서울", category="history", description="도심에서 만나는 조선 왕궁과 넓은 산책 동선", address="서울 종로구 사직로 161", lat=37.5796, lng=126.9770, kakao_map_url="https://map.kakao.com/link/map/경복궁,37.5796,126.9770"),
    Spot(id="seoul-forest", name="서울숲", location="서울", category="nature", description="가볍게 걷기 좋은 도심 숲과 잔디 공간", address="서울 성동구 뚝섬로 273", lat=37.5444, lng=127.0374, kakao_map_url="https://map.kakao.com/link/map/서울숲,37.5444,127.0374"),
    Spot(id="seoul-ddp", name="동대문디자인플라자", location="서울", category="culture", description="전시와 건축, 야간 조명이 이어지는 문화 공간", address="서울 중구 을지로 281", lat=37.5665, lng=127.0092, kakao_map_url="https://map.kakao.com/link/map/DDP,37.5665,127.0092"),
    Spot(id="seoul-namsan", name="남산서울타워", location="서울", category="night_view", description="서울 도심을 한눈에 보는 대표 야경 명소", address="서울 용산구 남산공원길 105", lat=37.5512, lng=126.9882, kakao_map_url="https://map.kakao.com/link/map/남산서울타워,37.5512,126.9882"),
    Spot(id="busan-haeundae", name="해운대해수욕장", location="부산", category="nature", description="바다 산책과 일몰을 함께 즐기는 부산 대표 해변", address="부산 해운대구 우동", lat=35.1587, lng=129.1604, kakao_map_url="https://map.kakao.com/link/map/해운대해수욕장,35.1587,129.1604"),
    Spot(id="busan-gamcheon", name="감천문화마을", location="부산", category="culture", description="언덕길을 따라 색채와 골목 풍경을 보는 문화 마을", address="부산 사하구 감내2로 203", lat=35.0975, lng=129.0106, kakao_map_url="https://map.kakao.com/link/map/감천문화마을,35.0975,129.0106"),
    Spot(id="busan-yongdusan", name="용두산공원", location="부산", category="history", description="원도심 역사와 부산타워 전망을 함께 보는 공원", address="부산 중구 용두산길 37-55", lat=35.1007, lng=129.0325, kakao_map_url="https://map.kakao.com/link/map/용두산공원,35.1007,129.0325"),
    Spot(id="busan-gwangalli", name="광안리해수욕장", location="부산", category="night_view", description="광안대교 조명이 펼쳐지는 해변 야경 명소", address="부산 수영구 광안해변로 219", lat=35.1532, lng=129.1187, kakao_map_url="https://map.kakao.com/link/map/광안리해수욕장,35.1532,129.1187"),
    Spot(id="jeju-seongsan", name="성산일출봉", location="제주", category="nature", description="제주 동쪽 바다와 분화구를 조망하는 세계자연유산", address="제주 서귀포시 성산읍 일출로 284-12", lat=33.4581, lng=126.9425, kakao_map_url="https://map.kakao.com/link/map/성산일출봉,33.4581,126.9425"),
    Spot(id="jeju-museum", name="제주도립미술관", location="제주", category="culture", description="제주 자연과 현대미술을 차분히 보는 실내 공간", address="제주 제주시 1100로 2894-78", lat=33.4528, lng=126.4897, kakao_map_url="https://map.kakao.com/link/map/제주도립미술관,33.4528,126.4897"),
    Spot(id="jeju-mokgwana", name="제주목 관아", location="제주", category="history", description="제주 행정과 생활사의 흔적을 보는 역사 유적", address="제주 제주시 관덕로 25", lat=33.5138, lng=126.5213, kakao_map_url="https://map.kakao.com/link/map/제주목관아,33.5138,126.5213"),
    Spot(id="jeju-sae", name="새연교", location="제주", category="night_view", description="서귀포항과 새섬을 잇는 야간 산책 명소", address="제주 서귀포시 서홍동", lat=33.2377, lng=126.5590, kakao_map_url="https://map.kakao.com/link/map/새연교,33.2377,126.5590"),
]


def _now() -> datetime:
    return datetime.now(KST)


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace("강수없음", "0"))
    except (TypeError, ValueError):
        return default


def _kma_items(endpoint: str, params: dict[str, object]) -> list[dict]:
    key = os.getenv("KMA_SERVICE_KEY", "").strip()
    if not key:
        raise RuntimeError("KMA_SERVICE_KEY가 설정되지 않았습니다.")
    response = httpx.get(
        f"{KMA_BASE_URL}/{endpoint}",
        params={"serviceKey": key, "dataType": "JSON", **params},
        timeout=8.0,
    )
    response.raise_for_status()
    payload = response.json()["response"]
    code = str(payload["header"].get("resultCode"))
    if code not in {"00", "0000"}:
        raise RuntimeError(payload["header"].get("resultMsg", "기상청 API 오류"))
    items = payload.get("body", {}).get("items", {}).get("item", [])
    return items if isinstance(items, list) else []


def _condition(sky: str | None, pty: str | None) -> str:
    precipitation = {"1": "비", "2": "비/눈", "3": "눈", "4": "소나기", "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림"}
    if pty and pty != "0":
        return precipitation.get(pty, "강수")
    return {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(sky or "", "맑음")


def _weather_code(code: int) -> str:
    if code == 0:
        return "맑음"
    if code in {1, 2}:
        return "구름조금"
    if code == 3:
        return "흐림"
    if code in {45, 48}:
        return "안개"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "비"
    if code in {71, 73, 75, 77, 85, 86}:
        return "눈"
    if code in {95, 96, 99}:
        return "뇌우"
    return "구름많음"


def _open_meteo_current(location: SupportedCity, kma_error: Exception) -> WeatherCurrent:
    meta = CITY_META[location]
    response = httpx.get(
        OPEN_METEO_URL,
        params={
            "latitude": meta["lat"],
            "longitude": meta["lng"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "wind_speed_unit": "ms",
            "timezone": "Asia/Seoul",
        },
        timeout=5.0,
    )
    response.raise_for_status()
    current = response.json()["current"]
    return WeatherCurrent(
        location=location,
        observed_at=str(current["time"]),
        condition=_weather_code(int(current["weather_code"])),
        temperature_c=float(current["temperature_2m"]),
        humidity_percent=int(current["relative_humidity_2m"]),
        precipitation_mm=float(current["precipitation"]),
        wind_speed_ms=float(current["wind_speed_10m"]),
        source="Open-Meteo Forecast API",
        provider_status="live",
        fetched_at=_now().isoformat(timespec="seconds"),
        warning=f"기상청 API를 사용할 수 없어 무료 무키 Provider로 전환했습니다: {type(kma_error).__name__}",
    )


def _open_meteo_forecast(
    location: SupportedCity,
    target_date: str,
    kma_error: Exception,
) -> WeatherForecast:
    meta = CITY_META[location]
    response = httpx.get(
        OPEN_METEO_URL,
        params={
            "latitude": meta["lat"],
            "longitude": meta["lng"],
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Asia/Seoul",
            "start_date": target_date,
            "end_date": target_date,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    daily = response.json()["daily"]
    low = float(daily["temperature_2m_min"][0])
    high = float(daily["temperature_2m_max"][0])
    return WeatherForecast(
        location=location,
        date=target_date,
        condition=_weather_code(int(daily["weather_code"][0])),
        temperature_c=round((low + high) / 2, 1),
        min_temperature_c=low,
        max_temperature_c=high,
        rain_probability_percent=int(daily["precipitation_probability_max"][0]),
        source="Open-Meteo Forecast API",
        provider_status="live",
        fetched_at=_now().isoformat(timespec="seconds"),
        warning=f"기상청 API를 사용할 수 없어 무료 무키 Provider로 전환했습니다: {type(kma_error).__name__}",
    )


def get_current_weather(location: SupportedCity) -> WeatherCurrent:
    now = _now()
    meta = CITY_META[location]
    base = now if now.minute >= 45 else now - timedelta(hours=1)
    try:
        items = _kma_items(
            "getUltraSrtNcst",
            {
                "pageNo": 1,
                "numOfRows": 20,
                "base_date": base.strftime("%Y%m%d"),
                "base_time": base.strftime("%H00"),
                "nx": meta["nx"],
                "ny": meta["ny"],
            },
        )
        values = {str(item["category"]): item.get("obsrValue") for item in items}
        if "T1H" not in values:
            raise RuntimeError("기온 관측값이 없습니다.")
        return WeatherCurrent(
            location=location,
            observed_at=base.isoformat(timespec="minutes"),
            condition=_condition(None, str(values.get("PTY", "0"))),
            temperature_c=_float(values["T1H"]),
            humidity_percent=int(_float(values.get("REH"))) if values.get("REH") is not None else None,
            precipitation_mm=_float(values.get("RN1")) if values.get("RN1") is not None else None,
            wind_speed_ms=_float(values.get("WSD")) if values.get("WSD") is not None else None,
            source="기상청 단기예보 조회서비스 · 초단기실황",
            provider_status="live",
            fetched_at=now.isoformat(timespec="seconds"),
        )
    except Exception as exc:
        try:
            return _open_meteo_current(location, exc)
        except Exception as open_meteo_error:
            fallback_error = open_meteo_error
        defaults = {"서울": (24.0, "구름많음"), "부산": (25.0, "맑음"), "제주": (26.0, "구름많음")}
        temperature, condition = defaults[location]
        return WeatherCurrent(
            location=location,
            observed_at=now.isoformat(timespec="minutes"),
            condition=condition,
            temperature_c=temperature,
            humidity_percent=62,
            precipitation_mm=0.0,
            wind_speed_ms=2.1,
            source="local-weather-fallback",
            provider_status="fallback",
            fetched_at=now.isoformat(timespec="seconds"),
            warning=f"기상청과 Open-Meteo 실황을 불러오지 못해 예시값을 표시합니다: {type(fallback_error).__name__}",
        )


def _latest_forecast_base(now: datetime) -> datetime:
    available = [2, 5, 8, 11, 14, 17, 20, 23]
    safe_now = now - timedelta(minutes=15)
    candidates = [safe_now.replace(hour=hour, minute=0, second=0, microsecond=0) for hour in available]
    candidates = [item for item in candidates if item <= safe_now]
    if candidates:
        return max(candidates)
    yesterday = safe_now - timedelta(days=1)
    return yesterday.replace(hour=23, minute=0, second=0, microsecond=0)


def get_weather_forecast(location: SupportedCity, target_date: str) -> WeatherForecast:
    parsed_date = date.fromisoformat(target_date)
    now = _now()
    meta = CITY_META[location]
    try:
        if parsed_date < now.date() or parsed_date > now.date() + timedelta(days=5):
            raise ValueError("기상청 단기예보 제공 범위(오늘부터 5일)를 벗어났습니다.")
        base = _latest_forecast_base(now)
        items = _kma_items(
            "getVilageFcst",
            {
                "pageNo": 1,
                "numOfRows": 1000,
                "base_date": base.strftime("%Y%m%d"),
                "base_time": base.strftime("%H00"),
                "nx": meta["nx"],
                "ny": meta["ny"],
            },
        )
        day_items = [item for item in items if str(item.get("fcstDate")) == parsed_date.strftime("%Y%m%d")]
        if not day_items:
            raise RuntimeError("선택 날짜의 단기예보가 없습니다.")
        by_time: dict[str, dict[str, str]] = {}
        temperatures: list[float] = []
        for item in day_items:
            value = str(item.get("fcstValue", ""))
            category = str(item.get("category", ""))
            by_time.setdefault(str(item.get("fcstTime", "")), {})[category] = value
            if category == "TMP":
                temperatures.append(_float(value))
        selected_time = min(by_time, key=lambda value: abs(int(value or "0") - 1200))
        values = by_time[selected_time]
        temperature = _float(values.get("TMP"), sum(temperatures) / max(1, len(temperatures)))
        return WeatherForecast(
            location=location,
            date=target_date,
            condition=_condition(values.get("SKY"), values.get("PTY")),
            temperature_c=temperature,
            min_temperature_c=min(temperatures) if temperatures else None,
            max_temperature_c=max(temperatures) if temperatures else None,
            rain_probability_percent=int(_float(values.get("POP"))) if values.get("POP") else None,
            source="기상청 단기예보 조회서비스 · 단기예보",
            provider_status="live",
            fetched_at=now.isoformat(timespec="seconds"),
        )
    except Exception as exc:
        try:
            return _open_meteo_forecast(location, target_date, exc)
        except Exception as open_meteo_error:
            fallback_error = open_meteo_error
        defaults = {"서울": (23.0, 29.0, "구름많음", 30), "부산": (24.0, 28.0, "맑음", 20), "제주": (25.0, 29.0, "구름많음", 40)}
        low, high, condition, rain = defaults[location]
        return WeatherForecast(
            location=location,
            date=target_date,
            condition=condition,
            temperature_c=round((low + high) / 2, 1),
            min_temperature_c=low,
            max_temperature_c=high,
            rain_probability_percent=rain,
            source="local-weather-fallback",
            provider_status="fallback",
            fetched_at=now.isoformat(timespec="seconds"),
            warning=f"기상청과 Open-Meteo 예보를 불러오지 못해 예시값을 표시합니다: {type(fallback_error).__name__}",
        )


def search_hotels(location: SupportedCity, max_price_per_night: int = 150_000, limit: int = 5) -> HotelSearch:
    if max_price_per_night < 1:
        raise ValueError("1박 최대 가격은 1원 이상이어야 합니다.")
    if not 1 <= limit <= 10:
        raise ValueError("limit은 1~10이어야 합니다.")
    matches = sorted(
        (hotel for hotel in HOTELS if hotel.location == location and hotel.price_per_night <= max_price_per_night),
        key=lambda hotel: (hotel.price_per_night, -hotel.rating),
    )[:limit]
    return HotelSearch(
        location=location,
        max_price_per_night=max_price_per_night,
        count=len(matches),
        hotels=matches,
        source="curated-demo-hotel-catalog",
        fetched_at=_now().isoformat(timespec="seconds"),
        notice="가격은 실시간 예약가가 아닌 데모 카탈로그 기준입니다. 예약 전 숙소 페이지에서 다시 확인하세요.",
    )


def _kakao_spots(location: SupportedCity, category: SpotCategory, limit: int) -> list[Spot]:
    key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if not key:
        raise RuntimeError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")
    query_label = {"all": "관광명소", "nature": "자연 관광지", "culture": "문화 관광지", "history": "역사 명소", "night_view": "야경 명소"}[category]
    response = httpx.get(
        KAKAO_LOCAL_URL,
        params={"query": f"{location} {query_label}", "size": min(limit, 15)},
        headers={"Authorization": f"KakaoAK {key}"},
        timeout=8.0,
    )
    response.raise_for_status()
    documents = response.json().get("documents", [])
    return [
        Spot(
            id=f"kakao-{item['id']}",
            name=item["place_name"],
            location=location,
            category=category,
            description=item.get("category_name") or "Kakao Local 검색 결과",
            address=item.get("road_address_name") or item.get("address_name") or "주소 미제공",
            lat=float(item["y"]),
            lng=float(item["x"]),
            kakao_map_url=item.get("place_url") or f"https://map.kakao.com/link/search/{quote(item['place_name'])}",
        )
        for item in documents[:limit]
    ]


def search_spots(location: SupportedCity, category: SpotCategory = "all", limit: int = 6) -> SpotSearch:
    if not 1 <= limit <= 10:
        raise ValueError("limit은 1~10이어야 합니다.")
    now = _now().isoformat(timespec="seconds")
    try:
        live = _kakao_spots(location, category, limit)
        if not live:
            raise RuntimeError("Kakao Local 검색 결과가 없습니다.")
        return SpotSearch(location=location, category=category, count=len(live), spots=live, source="Kakao Local API", provider_status="live", fetched_at=now)
    except Exception as exc:
        local = [spot for spot in SPOTS if spot.location == location and (category == "all" or spot.category == category)][:limit]
        return SpotSearch(
            location=location,
            category=category,
            count=len(local),
            spots=local,
            source="curated-demo-spot-catalog",
            provider_status="fallback",
            fetched_at=now,
            warning=f"Kakao Local API 대신 검증된 데모 명소를 표시합니다: {type(exc).__name__}",
        )


__all__ = [
    "CITY_META",
    "HotelSearch",
    "SpotCategory",
    "SpotSearch",
    "SupportedCity",
    "WeatherCurrent",
    "WeatherForecast",
    "get_current_weather",
    "get_weather_forecast",
    "search_hotels",
    "search_spots",
]
