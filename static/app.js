const form = document.querySelector("#trip-form");
const statusLine = document.querySelector("#form-status");
const resultSection = document.querySelector("#result");
const submitButton = form.querySelector("button[type='submit']");
let publicConfig = { kakao_map_enabled: false, kakao_javascript_key: "" };
let kakaoReady = null;

const won = new Intl.NumberFormat("ko-KR");
const qs = (selector) => document.querySelector(selector);
const text = (selector, value) => { qs(selector).textContent = value ?? "-"; };

function dateOffset(days) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

form.elements.date.value = dateOffset(1);
form.elements.date.min = dateOffset(0);
form.elements.date.max = dateOffset(15);

async function loadPublicConfig() {
  try {
    const response = await fetch("/api/v1/public-config");
    publicConfig = await response.json();
  } catch (_) {
    publicConfig = { kakao_map_enabled: false, kakao_javascript_key: "" };
  }
}

function loadKakaoSdk() {
  if (!publicConfig.kakao_map_enabled) return Promise.resolve(false);
  if (window.kakao?.maps) return Promise.resolve(true);
  if (kakaoReady) return kakaoReady;
  kakaoReady = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=${encodeURIComponent(publicConfig.kakao_javascript_key)}`;
    script.onload = () => window.kakao.maps.load(() => resolve(true));
    script.onerror = () => resolve(false);
    document.head.appendChild(script);
  });
  return kakaoReady;
}

function providerBadge(item) {
  const live = item.provider_status === "live";
  return `<span class="provider ${live ? "live" : "fallback"}">${live ? "LIVE DATA" : "FALLBACK"}</span>`;
}

function renderWeather(data) {
  const current = data.weather.current;
  const forecast = data.weather.forecast;
  text("#current-condition", current.condition);
  text("#current-temperature", `${current.temperature_c}°`);
  qs("#current-details").innerHTML = `
    <div><dt>습도</dt><dd>${current.humidity_percent ?? "-"}%</dd></div>
    <div><dt>바람</dt><dd>${current.wind_speed_ms ?? "-"} m/s</dd></div>
    <div><dt>데이터</dt><dd>${providerBadge(current)}</dd></div>`;
  text("#forecast-date", forecast.date);
  text("#forecast-condition", `${forecast.condition} · ${forecast.temperature_c}°`);
  qs("#forecast-details").innerHTML = `
    <div><dt>최저 / 최고</dt><dd>${forecast.min_temperature_c ?? "-"}° / ${forecast.max_temperature_c ?? "-"}°</dd></div>
    <div><dt>강수확률</dt><dd>${forecast.rain_probability_percent ?? "-"}%</dd></div>
    <div><dt>데이터</dt><dd>${providerBadge(forecast)}</dd></div>`;
}

function renderHotels(data) {
  text("#hotel-count", `${data.hotels.count}곳 · 1박 ${won.format(data.hotels.max_price_per_night)}원 이하`);
  qs("#hotel-list").innerHTML = data.hotels.hotels.length
    ? data.hotels.hotels.map((hotel, index) => `
      <article class="hotel-card">
        <span class="hotel-index">${String(index + 1).padStart(2, "0")}</span>
        <div><small>${hotel.district}</small><h4>${hotel.name}</h4><p>평점 ${hotel.rating.toFixed(1)} · 데모 카탈로그</p></div>
        <div class="hotel-price"><strong>${won.format(hotel.price_per_night)}원</strong><span>/ 1박</span><a href="${hotel.kakao_map_url}" target="_blank" rel="noreferrer">지도 보기 ↗</a></div>
      </article>`).join("")
    : `<div class="empty">이 가격 이하의 데모 호텔이 없습니다. 상한을 조금 높여 보세요.</div>`;
}

function renderSpots(data) {
  text("#spot-source", data.spots.provider_status === "live" ? "Kakao Local API" : "검증된 데모 카탈로그");
  qs("#spot-list").innerHTML = data.spots.spots.map((spot, index) => `
    <a class="spot-card" href="${spot.kakao_map_url}" target="_blank" rel="noreferrer">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <div><small>${spot.category}</small><h4>${spot.name}</h4><p>${spot.description}</p><address>${spot.address}</address></div>
      <b aria-hidden="true">↗</b>
    </a>`).join("");
}

async function renderMap(spots) {
  const mapNode = qs("#kakao-map");
  const setup = qs("#map-setup");
  const loaded = await loadKakaoSdk();
  if (!loaded || !spots.length) {
    mapNode.hidden = true;
    setup.hidden = false;
    return;
  }
  mapNode.hidden = false;
  setup.hidden = true;
  const bounds = new kakao.maps.LatLngBounds();
  const map = new kakao.maps.Map(mapNode, {
    center: new kakao.maps.LatLng(spots[0].lat, spots[0].lng),
    level: 7,
  });
  spots.forEach((spot) => {
    const position = new kakao.maps.LatLng(spot.lat, spot.lng);
    bounds.extend(position);
    const marker = new kakao.maps.Marker({ map, position, title: spot.name });
    const info = new kakao.maps.InfoWindow({ content: `<div class="map-label">${spot.name}</div>` });
    kakao.maps.event.addListener(marker, "click", () => info.open(map, marker));
  });
  map.setBounds(bounds, 50, 50, 50, 50);
}

function renderTrace(execution) {
  qs("#trace-list").innerHTML = execution.trace.map((item) => `
    <article>
      <div><span>${item.server.toUpperCase()} MCP</span><b>${item.duration_ms} ms</b></div>
      <strong>${item.tool}</strong>
      <code>${JSON.stringify(item.arguments)}</code>
      <small>${item.transport} · ${item.provider_status || "catalog"}</small>
    </article>`).join("");
}

function renderWarnings(warnings) {
  const node = qs("#warnings");
  node.innerHTML = warnings.map((warning) => `<p><strong>확인</strong>${warning}</p>`).join("");
  node.hidden = warnings.length === 0;
}

function renderResult(data) {
  text("#result-location", data.intent_summary.location);
  qs("#result-meta").innerHTML = `<strong>${data.intent_summary.date}</strong><span>${data.mcp_execution.total_duration_ms} ms · 서버 2대 병렬 호출</span>`;
  renderWeather(data);
  renderHotels(data);
  renderSpots(data);
  renderTrace(data.mcp_execution);
  renderWarnings(data.warnings);
  renderMap(data.spots.spots);
  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "두 서버 연결 중";
  statusLine.textContent = "Weather 8101과 Tour 8102에 Streamable HTTP로 요청하고 있습니다…";
  const values = new FormData(form);
  const payload = {
    location: values.get("location"),
    date: values.get("date"),
    max_hotel_price: Number(values.get("max_hotel_price")),
  };
  try {
    const response = await fetch("/api/v1/trip-briefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "조회에 실패했습니다.");
    renderResult(body);
    statusLine.textContent = `완료 · ${body.mcp_execution.trace.length}개 Tool을 실제 호출했습니다.`;
  } catch (error) {
    statusLine.textContent = `오류 · ${error.message}`;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "두 서버로 찾기";
  }
});

loadPublicConfig();
