const form = document.querySelector("#planner-form");
const resultShell = document.querySelector("#planner-result");
const submitButton = form.querySelector("button[type='submit']");

const won = new Intl.NumberFormat("ko-KR");
const categoryLabels = {
  cafe: "CAFE",
  restaurant: "DINING",
  museum: "CULTURE",
  activity: "ACTIVITY",
  night_view: "NIGHT VIEW",
  walk: "WALK",
};

function checkedValues(group) {
  return [...document.querySelectorAll(`[data-choice-group='${group}'] input:checked`)]
    .map((input) => input.value);
}

function todayString() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now - offset).toISOString().slice(0, 10);
}

form.elements.date.value = todayString();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderTimeline(stops) {
  const timeline = document.querySelector("#timeline");
  timeline.replaceChildren();
  stops.forEach((stop) => {
    const item = element("li", "timeline-item");
    item.append(element("div", "timeline-time", stop.start_time));

    const line = element("div", "timeline-line");
    line.append(element("span", "timeline-dot"));
    item.append(line);

    const card = element("article", "stop-card");
    const top = element("div", "stop-top");
    const titleWrap = element("div");
    titleWrap.append(element("div", "stop-category", categoryLabels[stop.category] || "PLACE"));
    titleWrap.append(element("h3", "", stop.name || stop.place_id));
    titleWrap.append(element("p", "", `${stop.start_time}–${stop.end_time}`));
    top.append(titleWrap);
    const price = stop.expected_cost === null
      ? "가격 미확인"
      : `1인 ${won.format(stop.expected_cost)}원`;
    top.append(element("span", "stop-price", price));
    card.append(top);
    card.append(element("p", "", stop.recommendation_rationale || "조건에 맞는 후보입니다."));
    if (stop.route_from_previous) {
      card.append(element(
        "p",
        "route-note",
        `↳ 이전 장소에서 ${stop.route_from_previous.duration_min}분 · 도보 ${won.format(stop.route_from_previous.walking_distance_m)}m`,
      ));
    }
    item.append(card);
    timeline.append(item);
  });
}

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function renderMap(stops) {
  const svg = document.querySelector("#route-map");
  svg.replaceChildren();
  if (!stops.length) return;

  const points = stops.map((stop, index) => ({
    x: 100 + (index % 2) * 390 + index * 18,
    y: 92 + index * 120,
    name: stop.name || stop.place_id,
  }));
  const pathData = points.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
  svg.append(svgElement("path", { d: pathData, class: "route-path" }));

  points.forEach((point, index) => {
    svg.append(svgElement("circle", { cx: point.x, cy: point.y, r: 20, class: "map-point" }));
    const number = svgElement("text", { x: point.x, y: point.y, class: "map-number" });
    number.textContent = String(index + 1);
    svg.append(number);
    const label = svgElement("text", {
      x: point.x + (point.x > 300 ? -30 : 30),
      y: point.y + 5,
      class: "map-label",
      "text-anchor": point.x > 300 ? "end" : "start",
    });
    label.textContent = point.name;
    svg.append(label);
  });
}

function renderResult(data) {
  const stops = data.course?.stops || [];
  const status = data.validation?.status || "fail";
  const badge = document.querySelector("#validation-badge");
  badge.textContent = status === "pass" ? "검증 통과" : "조건 확인 필요";
  badge.classList.toggle("fail", status !== "pass");

  const summary = document.querySelector("#summary-strip");
  const weather = data.intent_summary?.weather || {};
  summary.replaceChildren(
    element("span", "", `${data.intent_summary?.location || "-"} · ${data.intent_summary?.date || "-"}`),
    element("span", "", weather.condition === "rain" ? `비 ${weather.rain_probability}%` : "맑음"),
    element("span", "", `확인 비용 ${won.format(data.known_total_cost || 0)}원`),
    element("span", "", `이동 ${data.course?.total_route_time || 0}분`),
  );

  renderTimeline(stops);
  renderMap(stops);

  const warnings = document.querySelector("#warnings");
  warnings.replaceChildren();
  const messages = data.warnings || [];
  warnings.hidden = messages.length === 0;
  messages.forEach((message) => warnings.append(element("p", "", `• ${message}`)));

  const trace = document.querySelector("#trace");
  trace.replaceChildren();
  const list = element("div", "trace-list");
  (data.agent_execution?.tools || []).forEach((tool) => list.append(element("span", "", tool)));
  trace.append(list);
  trace.append(element(
    "p",
    "",
    `검증 ${data.agent_execution?.validation_attempts || 0}회 · 부분 재계획 ${data.agent_execution?.replan_count || 0}회`,
  ));

  resultShell.hidden = false;
  resultShell.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderError(message) {
  resultShell.hidden = false;
  document.querySelector("#validation-badge").textContent = "생성 실패";
  document.querySelector("#validation-badge").classList.add("fail");
  document.querySelector("#timeline").replaceChildren();
  document.querySelector("#route-map").replaceChildren();
  const warnings = document.querySelector("#warnings");
  warnings.hidden = false;
  warnings.replaceChildren(element("p", "", message));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.firstElementChild.textContent = "도구로 확인하는 중…";
  const formData = new FormData(form);
  const payload = {
    request: String(formData.get("request") || ""),
    location: formData.get("location"),
    companion_type: formData.get("companion_type"),
    date: formData.get("date"),
    start_time: formData.get("start_time"),
    end_time: formData.get("end_time"),
    party_size: Number(formData.get("party_size")),
    budget: Number(formData.get("budget")),
    transportation: formData.get("transportation"),
    hard_constraints: checkedValues("hard_constraints"),
    soft_preferences: checkedValues("soft_preferences"),
  };

  try {
    const response = await fetch("/api/v1/course-plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "코스를 만들지 못했습니다.");
    renderResult(data);
  } catch (error) {
    renderError(error.message || "요청 중 오류가 발생했습니다.");
  } finally {
    submitButton.disabled = false;
    submitButton.firstElementChild.textContent = "검증된 코스 만들기";
  }
});
