"use strict";

const form = document.querySelector("#planner-form");
const resultShell = document.querySelector("#planner-result");
const validationBadge = document.querySelector("#validation-badge");
const summaryStrip = document.querySelector("#summary-strip");
const timeline = document.querySelector("#timeline");
const tourList = document.querySelector("#tour-list");
const tourCount = document.querySelector("#tour-count");
const schematicMap = document.querySelector("#schematic-map");
const warningsBox = document.querySelector("#warnings");
const traceList = document.querySelector("#trace-list");
const mcpPipeline = document.querySelector("#mcp-pipeline");
const mcpProofDescription = document.querySelector("#mcp-proof-description");
const selectionSummaryList = document.querySelector("#selection-summary-list");
const presetButtons = [...document.querySelectorAll("[data-preset]")];
const bookingConsent = document.querySelector("#booking-consent");
const bookingButton = document.querySelector("#booking-button");
const bookingStatus = document.querySelector("#booking-status");
const submitButton = form.querySelector("button[type='submit']");
const buttonLabel = submitButton.querySelector(".button-label");
const submitProgress = document.querySelector("#submit-progress");
const dateInput = form.elements.date;
let latestCourse = null;

const presetOptions = {
  "rainy-date": {
    request: "부산에서 비가 와도 편하게 즐길 수 있는 조용한 커플 코스",
    location: "부산", companion_type: "couple", party_size: 2,
    start_time: "14:00", end_time: "21:00", budget: 100000, transportation: "public_transport",
    tourism_categories: ["문화관광", "도시명소"], soft_preferences: ["카페", "문화", "대화"], hard_constraints: ["비 오면 실내"],
  },
  parents: {
    request: "부모님과 많이 걷지 않고 역사와 식사를 즐기는 편안한 서울 코스",
    location: "서울", companion_type: "family", party_size: 3,
    start_time: "10:00", end_time: "18:00", budget: 150000, transportation: "public_transport",
    tourism_categories: ["역사관광", "문화관광"], soft_preferences: ["역사", "식사", "문화"], hard_constraints: ["걷기 어려움"],
  },
  family: {
    request: "아이와 이동 부담 없이 체험하고 식사할 수 있는 부산 반나절 코스",
    location: "부산", companion_type: "family", party_size: 3,
    start_time: "10:00", end_time: "16:00", budget: 120000, transportation: "car",
    tourism_categories: ["문화관광", "도시명소"], soft_preferences: ["문화", "식사", "사진"], hard_constraints: ["항상 실내"],
  },
  friends: {
    request: "친구들과 사진을 찍고 저녁과 야경을 즐기는 서울 코스",
    location: "서울", companion_type: "friends", party_size: 4,
    start_time: "16:00", end_time: "22:00", budget: 180000, transportation: "public_transport",
    tourism_categories: ["도시명소", "문화관광"], soft_preferences: ["식사", "야경", "사진", "대화"], hard_constraints: [],
  },
  anniversary: {
    request: "연인과 카페와 전망, 저녁 식사를 여유롭게 즐기는 부산 기념일 코스",
    location: "부산", companion_type: "couple", party_size: 2,
    start_time: "15:00", end_time: "21:00", budget: 200000, transportation: "car",
    tourism_categories: ["자연관광", "도시명소"], soft_preferences: ["카페", "식사", "야경", "대화"], hard_constraints: [],
  },
  culture: {
    request: "대중교통으로 미술과 역사를 둘러보는 가성비 서울 문화 산책",
    location: "서울", companion_type: "friends", party_size: 2,
    start_time: "11:00", end_time: "18:00", budget: 70000, transportation: "public_transport",
    tourism_categories: ["문화관광", "역사관광"], soft_preferences: ["문화", "역사", "사진"], hard_constraints: [],
  },
};

const categoryLabels = {
  cafe: "카페",
  restaurant: "식사",
  museum: "문화",
  activity: "체험",
  night_view: "야경",
  walk: "산책",
  nature: "자연",
  heritage: "역사",
  landmark: "명소",
};

const tourismInitials = {
  자연관광: "자연",
  문화관광: "문화",
  역사관광: "역사",
  도시명소: "도시",
};

const companionLabels = { couple: "커플", family: "가족", friends: "친구" };
const transportationLabels = { walking: "도보", public_transport: "대중교통", car: "자동차" };

const createElement = (tag, className, text) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
};

const formatWon = (value) => {
  if (value === null || value === undefined) return "가격 미확인";
  return `${Number(value).toLocaleString("ko-KR")}원`;
};

const checkedValues = (groupName) =>
  [...document.querySelectorAll(`[data-choice-group='${groupName}'] input:checked`)]
    .map((input) => input.value);

const setCheckedValues = (groupName, values) => {
  const selected = new Set(values);
  document.querySelectorAll(`[data-choice-group='${groupName}'] input`).forEach((input) => {
    input.checked = selected.has(input.value);
  });
};

function updateSelectionSummary() {
  const values = new FormData(form);
  const preferences = checkedValues("soft_preferences");
  const constraints = checkedValues("hard_constraints");
  const items = [
    ["일정", `${values.get("location")} · ${values.get("date") || "날짜 선택"}`],
    ["동행", `${companionLabels[values.get("companion_type")] || "동행"} ${values.get("party_size") || 2}명`],
    ["시간", `${values.get("start_time")}–${values.get("end_time")}`],
    ["예산", formatWon(Number(values.get("budget") || 0))],
    ["이동", transportationLabels[values.get("transportation")] || "미정"],
    ["우선순위", [...constraints, ...preferences].slice(0, 3).join(" · ") || "자동 추천"],
  ];
  selectionSummaryList.replaceChildren();
  items.forEach(([label, value]) => {
    const wrapper = createElement("div");
    wrapper.append(createElement("dt", "", label), createElement("dd", "", value));
    selectionSummaryList.append(wrapper);
  });
}

function applyPreset(name) {
  const preset = presetOptions[name];
  if (!preset) return;
  ["request", "location", "companion_type", "party_size", "start_time", "end_time", "budget", "transportation"].forEach((key) => {
    form.elements[key].value = preset[key];
  });
  setCheckedValues("tourism_categories", preset.tourism_categories);
  setCheckedValues("soft_preferences", preset.soft_preferences);
  setCheckedValues("hard_constraints", preset.hard_constraints);
  presetButtons.forEach((button) => {
    const active = button.dataset.preset === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  updateSelectionSummary();
}

const weatherText = (weather = {}) => {
  const labels = { rain: "비", clear: "맑음", cloudy: "흐림" };
  const condition = labels[weather.condition] || "날씨 미확인";
  return weather.rain_probability === null || weather.rain_probability === undefined
    ? condition
    : `${condition} · 강수 ${weather.rain_probability}%`;
};

const addSummaryItem = (label, value) => {
  const item = createElement("div", "summary-item");
  item.append(createElement("span", "", label), createElement("strong", "", value));
  summaryStrip.append(item);
};

function renderSummary(data) {
  const intent = data.intent_summary || {};
  const course = data.course || {};
  summaryStrip.replaceChildren();
  addSummaryItem("지역과 날짜", `${intent.location || "-"} · ${intent.date || "-"}`);
  addSummaryItem("날씨", weatherText(intent.weather));
  addSummaryItem("확인된 비용", formatWon(data.known_total_cost || 0));
  addSummaryItem("총 이동시간", `${course.total_route_time || 0}분`);
}

function renderTimeline(stops = []) {
  timeline.replaceChildren();
  if (!stops.length) {
    const empty = createElement("li", "stop-card", "현재 조건으로 구성할 수 있는 일정이 없습니다.");
    timeline.append(empty);
    return;
  }

  stops.forEach((stop) => {
    const item = createElement("li", "timeline-item");
    const time = createElement("time", "timeline-time", stop.start_time || "--:--");
    const rail = createElement("div", "timeline-rail");
    rail.append(createElement("span", "timeline-dot"));

    const card = createElement("article", "stop-card");
    const topLine = createElement("div", "stop-topline");
    topLine.append(
      createElement("span", "category-tag", categoryLabels[stop.category] || stop.tourism_category || "장소"),
      createElement("span", "stop-duration", `${stop.start_time || "-"} — ${stop.end_time || "-"}`),
    );
    card.append(topLine, createElement("h4", "", stop.name || "이름 미확인 장소"));

    const description = stop.description || stop.recommendation_rationale;
    if (description) card.append(createElement("p", "stop-description", description));

    const meta = createElement("div", "stop-meta");
    meta.append(createElement("span", "", formatWon(stop.expected_cost)));
    if (stop.indoor === true) meta.append(createElement("span", "", "실내"));
    if (stop.indoor === false) meta.append(createElement("span", "", "야외"));
    if (stop.accessible === true) meta.append(createElement("span", "", "접근 가능"));
    if (stop.tourism_category) meta.append(createElement("span", "", stop.tourism_category));
    card.append(meta);

    if (stop.route_from_previous) {
      const route = stop.route_from_previous;
      card.append(
        createElement(
          "p",
          "route-note",
          `이전 장소에서 ${route.duration_min || 0}분 · 도보 ${Number(route.walking_distance_m || 0).toLocaleString("ko-KR")}m`,
        ),
      );
    }
    item.append(time, rail, card);
    timeline.append(item);
  });
}

function renderTourCatalog(tourism = {}) {
  const items = tourism.items || [];
  tourList.replaceChildren();
  tourCount.textContent = `${items.length}곳`;
  if (!items.length) {
    tourList.append(createElement("p", "stop-description", "선택한 관광 유형의 명소가 없습니다."));
    return;
  }

  items.forEach((item) => {
    const card = createElement("article", "tour-card");
    card.append(createElement("span", "tour-icon", tourismInitials[item.category] || "명소"));
    const copy = createElement("div");
    copy.append(
      createElement("b", "", item.category || "관광 명소"),
      createElement("strong", "", item.name || "이름 미확인"),
      createElement("p", "", item.description || "설명이 준비되지 않았습니다."),
    );
    card.append(copy);
    tourList.append(card);
  });
}

function renderMap(stops = []) {
  schematicMap.replaceChildren();
  if (!stops.length) return;
  schematicMap.append(createElement("span", "map-path"));
  const positions = [
    { left: 18, top: 17, labelLeft: 4, labelTop: 37 },
    { left: 66, top: 39, labelLeft: 48, labelTop: 60 },
    { left: 34, top: 70, labelLeft: 43, labelTop: 80 },
  ];
  stops.slice(0, 3).forEach((stop, index) => {
    const position = positions[index];
    const marker = createElement("span", "map-marker");
    marker.style.left = `${position.left}%`;
    marker.style.top = `${position.top}%`;
    marker.append(createElement("span", "", String(index + 1)));
    const label = createElement("span", "map-label", stop.name || `장소 ${index + 1}`);
    label.style.left = `${position.labelLeft}%`;
    label.style.top = `${position.labelTop}%`;
    schematicMap.append(marker, label);
  });
}

function renderWarnings(warnings = []) {
  warningsBox.replaceChildren();
  warningsBox.hidden = warnings.length === 0;
  if (!warnings.length) return;
  warningsBox.append(createElement("strong", "", "확인해 주세요"));
  const list = createElement("ul");
  warnings.forEach((warning) => list.append(createElement("li", "", String(warning))));
  warningsBox.append(list);
}

function renderTrace(execution = {}) {
  traceList.replaceChildren();
  const trace = Array.isArray(execution.trace) && execution.trace.length
    ? execution.trace
    : (execution.domain_steps || []).map((tool, index) => ({ turn: index + 1, tool, arguments: {}, is_error: false }));
  trace.forEach((entry) => {
    const row = createElement("div", "trace-item");
    const server = entry.server ? `${entry.server} / ` : "";
    row.append(createElement("strong", "", `${entry.turn || "·"}. ${server}${entry.tool || "도구"}`));
    const args = createElement("code", "", JSON.stringify(entry.arguments || {}));
    const timing = entry.duration_ms === undefined ? "완료" : `${entry.duration_ms}ms`;
    const state = createElement("span", `trace-state${entry.is_error ? " is-error" : ""}`, entry.is_error ? "오류" : timing);
    row.append(args, state);
    traceList.append(row);
  });
}

function renderMcpPipeline(execution = {}) {
  const registered = execution.registered_mcp_servers || ["weather", "tour", "route", "booking"];
  const called = new Set(execution.mcp_servers_called || []);
  const metadata = {
    weather: ["Weather MCP", "날씨 조건 조회"],
    tour: ["Tour MCP", "관광 후보 탐색"],
    route: ["Route MCP", "경로·코스 검증"],
    booking: ["Booking MCP", "사용자 확인 대기"],
  };
  mcpPipeline.replaceChildren();
  registered.forEach((server, index) => {
    const complete = called.has(server);
    const card = createElement("article", `mcp-node ${complete ? "is-complete" : "is-waiting"}`);
    card.dataset.server = server;
    const tools = (execution.trace || []).filter((item) => item.server === server);
    const duration = tools.reduce((total, item) => total + Number(item.duration_ms || 0), 0);
    card.append(
      createElement("span", "mcp-node-index", String(index + 1).padStart(2, "0")),
      createElement("strong", "", metadata[server]?.[0] || server),
      createElement("p", "", metadata[server]?.[1] || "MCP 서버"),
      createElement("small", "mcp-node-state", complete ? `stdio · ${tools.length}회 · ${duration}ms` : "아직 실행되지 않음"),
    );
    mcpPipeline.append(card);
  });
  const verified = execution.execution_path === "stdio_mcp_verified";
  mcpProofDescription.textContent = verified
    ? `Weather·Tour·Route 서버를 로컬 stdio 자식 프로세스로 실행해 이 결과를 재검증했습니다. 프로세스 시작 포함 ${execution.mcp_total_duration_ms || 0}ms.`
    : "MCP 프로세스 확인에 실패해 같은 결정론적 함수를 서버 내부에서 실행했습니다.";
  mcpPipeline.classList.toggle("is-fallback", !verified);
}

function renderResult(data) {
  const passed = data.validation?.status === "pass";
  const bookingReady = passed && (data.course?.stops || []).length > 0;
  validationBadge.textContent = passed ? "검증 통과" : "조건 확인 필요";
  validationBadge.className = `validation-badge ${passed ? "is-pass" : "is-fail"}`;
  renderSummary(data);
  renderTimeline(data.course?.stops || []);
  renderTourCatalog(data.tourism || {});
  renderMap(data.course?.stops || []);
  renderWarnings(data.warnings || []);
  renderMcpPipeline(data.agent_execution || {});
  renderTrace(data.agent_execution || {});
  latestCourse = bookingReady ? data : null;
  bookingConsent.disabled = !bookingReady;
  bookingConsent.checked = false;
  bookingButton.disabled = true;
  bookingStatus.textContent = bookingReady
    ? ""
    : "검증을 통과한 일정이 있어야 모의 예약을 실행할 수 있습니다.";
  bookingStatus.className = `booking-status${bookingReady ? "" : " is-error"}`;
  resultShell.hidden = false;
  resultShell.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderError(message) {
  validationBadge.textContent = "요청 실패";
  validationBadge.className = "validation-badge is-fail";
  summaryStrip.replaceChildren();
  timeline.replaceChildren(createElement("li", "stop-card", message));
  tourList.replaceChildren();
  tourCount.textContent = "";
  schematicMap.replaceChildren();
  renderWarnings(["입력값을 확인한 뒤 다시 시도해 주세요."]);
  traceList.replaceChildren();
  mcpPipeline.replaceChildren();
  latestCourse = null;
  bookingConsent.disabled = true;
  bookingConsent.checked = false;
  bookingButton.disabled = true;
  bookingStatus.textContent = "코스 검증을 통과한 뒤 모의 예약을 실행할 수 있습니다.";
  bookingStatus.className = "booking-status is-error";
  resultShell.hidden = false;
  resultShell.scrollIntoView({ behavior: "smooth", block: "start" });
}

function formPayload() {
  const values = new FormData(form);
  return {
    request: String(values.get("request") || ""),
    location: String(values.get("location") || "부산"),
    companion_type: String(values.get("companion_type") || "couple"),
    date: String(values.get("date") || ""),
    start_time: String(values.get("start_time") || "14:00"),
    end_time: String(values.get("end_time") || "21:00"),
    party_size: Number(values.get("party_size") || 2),
    budget: Number(values.get("budget") || 0),
    transportation: String(values.get("transportation") || "public_transport"),
    hard_constraints: checkedValues("hard_constraints"),
    soft_preferences: checkedValues("soft_preferences"),
    tourism_categories: checkedValues("tourism_categories"),
  };
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  buttonLabel.textContent = "코스를 확인하는 중…";
  submitProgress.textContent = "Weather MCP 서버를 시작하고 있습니다.";
  const progressMessages = [
    "Tour MCP에서 관광 후보를 조회하고 있습니다.",
    "Route MCP에서 이동과 예산을 검증하고 있습니다.",
    "마지막으로 결과 계약을 확인하고 있습니다.",
  ];
  let progressIndex = 0;
  const progressTimer = window.setInterval(() => {
    submitProgress.textContent = progressMessages[Math.min(progressIndex, progressMessages.length - 1)];
    progressIndex += 1;
  }, 900);
  const coldStartNotice = window.setTimeout(() => {
    buttonLabel.textContent = "무료 서버를 시작하는 중…";
  }, 2500);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60000);

  try {
    const response = await fetch("/api/v1/course-plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload()),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "코스를 만들지 못했습니다.");
    renderResult(data);
  } catch (error) {
    const message = error.name === "AbortError"
      ? "서버 응답이 늦어지고 있습니다. 잠시 후 다시 시도해 주세요."
      : (error.message || "요청 중 오류가 발생했습니다.");
    renderError(message);
  } finally {
    window.clearTimeout(coldStartNotice);
    window.clearTimeout(timeout);
    window.clearInterval(progressTimer);
    submitButton.disabled = false;
    buttonLabel.textContent = "검증된 코스 만들기";
    submitProgress.textContent = "Weather → Tour → Route 순서로 조회하고 검증합니다.";
  }
});

bookingConsent.addEventListener("change", () => {
  bookingButton.disabled = !bookingConsent.checked || !latestCourse;
  if (!bookingConsent.checked) bookingStatus.textContent = "";
});

bookingButton.addEventListener("click", async () => {
  if (!latestCourse || !bookingConsent.checked) return;
  bookingButton.disabled = true;
  bookingButton.textContent = "모의 예약 확인 중…";
  bookingStatus.textContent = "Booking MCP 액션 경계를 확인하고 있습니다.";
  bookingStatus.className = "booking-status";
  const bookingNode = mcpPipeline.querySelector("[data-server='booking']");
  if (bookingNode) {
    bookingNode.className = "mcp-node is-running";
    bookingNode.querySelector(".mcp-node-state").textContent = "stdio · 실행 중";
  }

  const stops = (latestCourse.course?.stops || []).map((stop) => ({
    place_id: stop.place_id,
    name: stop.name || stop.place_id,
    start_time: stop.start_time,
  }));
  try {
    const response = await fetch("/api/v1/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        course_id: latestCourse.course_id,
        date: latestCourse.intent_summary?.date,
        party_size: latestCourse.intent_summary?.party_size,
        stops,
        user_confirmed: true,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "모의 예약을 실행하지 못했습니다.");
    bookingStatus.textContent = `모의 예약 확인 완료 · ${data.booking.confirmation_id}`;
    bookingStatus.className = "booking-status is-success";
    bookingConsent.disabled = true;
    bookingButton.textContent = "모의 예약 확인 완료";
    if (bookingNode) {
      bookingNode.className = "mcp-node is-complete";
      bookingNode.querySelector("p").textContent = "명시적 확인 완료";
      bookingNode.querySelector(".mcp-node-state").textContent = `stdio · ${data.booking.confirmation_id}`;
    }
  } catch (error) {
    bookingStatus.textContent = error.message || "모의 예약 중 오류가 발생했습니다.";
    bookingStatus.className = "booking-status is-error";
    bookingButton.disabled = false;
    bookingButton.textContent = "모의 예약 다시 실행";
    if (bookingNode) {
      bookingNode.className = "mcp-node is-error";
      bookingNode.querySelector(".mcp-node-state").textContent = "실행 실패 · 다시 시도 가능";
    }
  }
});

if (!dateInput.value) {
  const today = new Date();
  const offset = today.getTimezoneOffset() * 60_000;
  dateInput.value = new Date(today.getTime() - offset).toISOString().slice(0, 10);
}
dateInput.min = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
form.addEventListener("input", updateSelectionSummary);
form.addEventListener("change", updateSelectionSummary);
presetButtons.forEach((button) => button.addEventListener("click", () => applyPreset(button.dataset.preset)));
applyPreset("rainy-date");
