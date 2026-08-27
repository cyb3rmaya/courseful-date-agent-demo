const form = document.querySelector("#trip-form");
const statusLine = document.querySelector("#form-status");
const resultSection = document.querySelector("#result");
const submitButton = form.querySelector("button[type='submit']");
let publicConfig = { kakao_map_enabled: false, kakao_javascript_key: "" };
let kakaoReady = null;
const publicConfigReady = loadPublicConfig();

const qs = (selector) => document.querySelector(selector);
const text = (selector, value) => { qs(selector).textContent = value ?? "-"; };
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function safeKakaoUrl(value) {
  try {
    const url = new URL(String(value));
    const allowedHost = url.hostname === "map.kakao.com" || url.hostname === "place.map.kakao.com";
    return allowedHost && ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch (_) {
    return "#";
  }
}

function dateOffset(days) {
  const kst = new Date(Date.now() + (9 * 60 * 60 * 1000) + (days * 24 * 60 * 60 * 1000));
  return kst.toISOString().slice(0, 10);
}

form.elements.date.value = dateOffset(1);
form.elements.date.min = dateOffset(0);
form.elements.date.max = dateOffset(15);

async function loadPublicConfig() {
  try {
    const response = await fetch("/api/v1/public-config");
    if (!response.ok) throw new Error("공개 설정을 불러오지 못했습니다.");
    publicConfig = await response.json();
  } catch (_) {
    publicConfig = { kakao_map_enabled: false, kakao_javascript_key: "" };
  }
}

function loadKakaoSdk() {
  if (!publicConfig.kakao_map_enabled) return Promise.resolve(false);
  if (window.kakao?.maps?.Map) return Promise.resolve(true);
  if (kakaoReady) return kakaoReady;
  kakaoReady = new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey=${encodeURIComponent(publicConfig.kakao_javascript_key)}`;
    const timeout = window.setTimeout(() => resolve(false), 12_000);
    script.onload = () => {
      if (typeof window.kakao?.maps?.load !== "function") {
        window.clearTimeout(timeout);
        resolve(false);
        return;
      }
      window.kakao.maps.load(() => {
        window.clearTimeout(timeout);
        resolve(typeof window.kakao?.maps?.Map === "function");
      });
    };
    script.onerror = () => {
      window.clearTimeout(timeout);
      resolve(false);
    };
    document.head.appendChild(script);
  });
  return kakaoReady;
}

function renderCourse(course) {
  text("#result-title", course.title);
  const companionPhrase = {
    friend: "친구와 함께",
    family: "가족과 함께",
    couple: "연인과 함께",
  }[course.companion] || `${course.companion_label}과 함께`;
  text("#companion-badge", companionPhrase);
  text("#course-headline", course.headline);
  text("#course-description", course.description);
  text("#course-source", course.provider_status === "live" ? "Kakao Local 실시간 명소" : "검증된 지역 명소");
  qs("#spot-list").innerHTML = course.stops.map((stop) => `
    <li class="spot-card">
      <span class="spot-number">${String(stop.sequence).padStart(2, "0")}</span>
      <div>
        <small>${escapeHtml(stop.guide)}</small>
        <h4>${escapeHtml(stop.name)}</h4>
        <p>${escapeHtml(stop.description)}</p>
        <address>${escapeHtml(stop.address)}</address>
      </div>
      <a href="${safeKakaoUrl(stop.kakao_map_url)}" target="_blank" rel="noreferrer" aria-label="${escapeHtml(stop.name)} Kakao 지도에서 열기">↗</a>
    </li>`).join("");
}

function renderWeather(data) {
  const current = data.weather.current;
  const forecast = data.weather.forecast;
  text("#current-weather", current.condition);
  text("#current-temperature", `${current.temperature_c}°`);
  text("#forecast-date", forecast.date);
  text("#forecast-weather", forecast.condition);
  text("#forecast-temperature", `${forecast.min_temperature_c}° / ${forecast.max_temperature_c}° · 비 ${forecast.rain_probability_percent}%`);
}

function showMapFallback(label, title, description) {
  const mapNode = qs("#kakao-map");
  const setup = qs("#map-setup");
  mapNode.hidden = true;
  setup.hidden = false;
  setup.querySelector("span").textContent = label;
  setup.querySelector("strong").textContent = title;
  setup.querySelector("p").textContent = description;
}

async function renderMap(stops) {
  const mapNode = qs("#kakao-map");
  const setup = qs("#map-setup");
  const loaded = await loadKakaoSdk();
  if (!loaded || !stops.length) {
    showMapFallback(
      loaded ? "NO COURSE STOPS" : "MAP LOAD FAILED",
      loaded ? "표시할 코스가 없습니다." : "Kakao 지도를 불러오지 못했습니다.",
      "명소별 지도 링크는 계속 사용할 수 있습니다.",
    );
    return;
  }
  try {
    mapNode.hidden = false;
    setup.hidden = true;
    mapNode.replaceChildren();
    const positions = stops.map((stop) => new kakao.maps.LatLng(stop.lat, stop.lng));
    const bounds = new kakao.maps.LatLngBounds();
    positions.forEach((position) => bounds.extend(position));
    const map = new kakao.maps.Map(mapNode, { center: positions[0], level: 7 });

    new kakao.maps.Polyline({
      map,
      path: positions,
      strokeWeight: 5,
      strokeColor: "#171714",
      strokeOpacity: 0.85,
      strokeStyle: "solid",
    });

    stops.forEach((stop, index) => {
      const position = positions[index];
      const marker = new kakao.maps.Marker({ map, position, title: stop.name });
      const number = new kakao.maps.CustomOverlay({
        map,
        position,
        content: `<div class="map-sequence" title="${escapeHtml(stop.name)}">${index + 1}</div>`,
        xAnchor: 0.5,
        yAnchor: 1.7,
      });
      const info = new kakao.maps.InfoWindow({
        content: `<div class="map-label"><b>${index + 1}</b> ${escapeHtml(stop.name)}</div>`,
      });
      kakao.maps.event.addListener(marker, "click", () => info.open(map, marker));
      number.setMap(map);
    });
    map.setBounds(bounds, 70, 70, 70, 70);
  } catch (error) {
    console.warn("Kakao map render failed", error);
    showMapFallback("MAP RENDER FAILED", "Kakao 지도 렌더링에 실패했습니다.", "명소별 지도 링크는 계속 사용할 수 있습니다.");
  }
}

function renderTrace(execution) {
  qs("#trace-list").innerHTML = execution.trace.map((item) => `
    <article>
      <div><span>${escapeHtml(item.server).toUpperCase()} MCP</span><b>${item.duration_ms} ms</b></div>
      <strong>${escapeHtml(item.tool)}</strong>
      <code>${escapeHtml(JSON.stringify(item.arguments))}</code>
      <small>${escapeHtml(item.transport)} · ${escapeHtml(item.provider_status || "catalog")}</small>
    </article>`).join("");
}

function renderWarnings(warnings) {
  const node = qs("#warnings");
  node.innerHTML = warnings.map((warning) => `<p><strong>알림</strong><span>${escapeHtml(warning)}</span></p>`).join("");
  node.hidden = warnings.length === 0;
}

async function renderResult(data) {
  const course = data.course;
  qs("#result-meta").innerHTML = `<strong>${escapeHtml(data.intent_summary.date)}</strong><span>${course.stop_count}곳 · ${escapeHtml(course.companion_label)} 코스</span>`;
  renderCourse(course);
  renderWeather(data);
  renderTrace(data.mcp_execution);
  renderWarnings(data.warnings);
  resultSection.hidden = false;
  await renderMap(course.stops);
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "코스 연결 중";
  statusLine.textContent = "Weather와 Tour MCP에서 날씨와 명소를 확인하고 있습니다…";
  const values = new FormData(form);
  const payload = {
    location: values.get("location"),
    date: values.get("date"),
    companion: values.get("companion"),
  };
  try {
    await publicConfigReady;
    const response = await fetch("/api/v1/trip-briefs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "코스를 만들지 못했습니다.");
    await renderResult(body);
    statusLine.textContent = `완료 · ${body.course.stop_count}곳을 한 코스로 연결했습니다.`;
  } catch (error) {
    statusLine.textContent = `오류 · ${error.message}`;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "코스로 묶기";
  }
});
