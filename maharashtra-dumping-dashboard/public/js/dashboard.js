const state = { district: "", risk: "", query: "", page: 1, pageSize: 25, recordsMode: "villages", charts: {}, map: null, markers: null, predictionOptions: null };

const numberFormat = new Intl.NumberFormat("en-IN");
const riskColors = { High: "#c75d43", Medium: "#c78c26", Low: "#458267" };
const viewCopy = {
  overview: ["Overview", "A clearer picture<br><em>of the ground.</em>", "Explore reported waste observations across Kolhapur, Sangli and Satara."],
  map: ["Hotspot map", "A place to<br><em>look closer.</em>", "Browse generated sample coordinates by district and risk label."],
  prediction: ["Predict risk", "Explore a scenario<br><em>for a locality.</em>", "Get a model estimate for any village in Kolhapur, Sangli, or Satara."],
  patterns: ["Patterns", "Find the shape<br><em>of the sample.</em>", "Compare generated observations by material, time and district."],
  records: ["Incident records", "Every row has<br><em>a story.</em>", "Search, inspect and export the sample records."],
};

function filters() {
  return new URLSearchParams({ district: state.district, risk: state.risk, q: state.query });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function riskBadge(level) {
  const safeLevel = ["High", "Medium", "Low"].includes(level) ? level : "Low";
  return `<span class="risk-badge risk-${safeLevel.toLowerCase()}">${safeLevel}</span>`;
}

function createChart(id, config) {
  if (!window.Chart) return;
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const wrapper = canvas.parentElement;
  let emptyState = wrapper.querySelector(".chart-empty");
  if (!emptyState) {
    emptyState = document.createElement("div");
    emptyState.className = "chart-empty";
    emptyState.textContent = "No records match these filters. Change or clear a filter to see this chart.";
    emptyState.hidden = true;
    wrapper.append(emptyState);
  }
  const hasData = config.data.datasets.some((dataset) => dataset.data.some((value) => Number(value) > 0));
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = null;
  canvas.hidden = !hasData;
  emptyState.hidden = hasData;
  if (hasData) state.charts[id] = new Chart(canvas, config);
}

const chartScales = {
  x: { grid: { display: false }, border: { display: false }, ticks: { color: "#89978e", font: { family: "DM Sans", size: 9 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
  y: { beginAtZero: true, grid: { color: "#edf0eb" }, border: { display: false }, ticks: { color: "#89978e", font: { family: "DM Sans", size: 9 }, precision: 0 } },
};

function renderOverview(data) {
  document.getElementById("metric-total").textContent = numberFormat.format(data.total);
  document.getElementById("metric-high").textContent = numberFormat.format(data.risk_counts.High || 0);
  document.getElementById("metric-average").textContent = data.average_risk.toFixed(2);
  document.getElementById("metric-districts").textContent = Object.keys(data.district_counts).length;
  document.getElementById("risk-total").textContent = numberFormat.format(data.total);

  createChart("monthly-chart", {
    type: "line",
    data: { labels: Object.keys(data.monthly_counts), datasets: [{ data: Object.values(data.monthly_counts), borderColor: "#438265", backgroundColor: "#4382651a", fill: true, tension: 0.3, pointRadius: 2, pointHoverRadius: 4, borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { intersect: false, mode: "index" } }, scales: chartScales },
  });

  const levels = ["High", "Medium", "Low"];
  createChart("risk-chart", {
    type: "doughnut",
    data: { labels: levels, datasets: [{ data: levels.map((level) => data.risk_counts[level] || 0), backgroundColor: levels.map((level) => riskColors[level]), borderWidth: 0, hoverOffset: 3 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: "76%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (context) => `${context.label}: ${numberFormat.format(context.raw)}` } } } },
  });
  document.getElementById("risk-legend").innerHTML = levels.map((level) => `<span class="legend-item"><i class="legend-swatch" style="background:${riskColors[level]}"></i>${level} <b>${numberFormat.format(data.risk_counts[level] || 0)}</b></span>`).join("");

  const locationRows = data.locations.map((location) => `<tr><td><span class="location-name">${escapeHtml(location.village_name)}</span><span class="location-sub">${escapeHtml(location.taluka)}</span></td><td>${escapeHtml(location.district)}</td><td>${numberFormat.format(location.incidents)}</td><td>${location.risk_score.toFixed(2)}</td><td>${riskBadge(location.hotspot_risk)}</td></tr>`).join("");
  document.getElementById("locations-body").innerHTML = locationRows || '<tr><td colspan="5" class="empty-row">No locations match these filters.</td></tr>';
}

function renderPatterns(data) {
  const wasteEntries = Object.entries(data.waste_counts).sort((a, b) => b[1] - a[1]);
  createChart("waste-chart", {
    type: "bar",
    data: { labels: wasteEntries.map(([label]) => label), datasets: [{ data: wasteEntries.map(([, count]) => count), backgroundColor: ["#438265", "#d09a3e", "#749c82", "#cf7658", "#9dbb8c", "#668e9b"], borderRadius: 3, maxBarThickness: 26 }] },
    options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: chartScales.y, y: { grid: { display: false }, border: { display: false }, ticks: { color: "#738178", font: { family: "DM Sans", size: 9 }, autoSkip: false } } } },
  });
  const hours = Array.from({ length: 24 }, (_, hour) => data.hour_counts[hour] || 0);
  createChart("hour-chart", {
    type: "bar",
    data: { labels: Array.from({ length: 24 }, (_, hour) => `${String(hour).padStart(2, "0")}:00`), datasets: [{ data: hours, backgroundColor: "#79a78a", borderRadius: 2, maxBarThickness: 15 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: chartScales },
  });
  const districtEntries = Object.entries(data.district_counts);
  createChart("district-chart", {
    type: "bar",
    data: { labels: districtEntries.map(([label]) => label), datasets: [{ data: districtEntries.map(([, count]) => count), backgroundColor: ["#438265", "#c78c26", "#c75d43"], borderRadius: 3, maxBarThickness: 52 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: chartScales },
  });
}

async function renderVillagePatterns() {
  const data = await getJson(`/api/village-results?${filters()}&page=1`);
  document.getElementById("village-pattern-total").textContent = `${numberFormat.format(data.total)} VILLAGES`;
  document.getElementById("village-pattern-with-rows").textContent = numberFormat.format(data.with_incident_rows);
  document.getElementById("village-pattern-without-rows").textContent = numberFormat.format(data.without_incident_rows);
  createChart("village-risk-chart", {
    type: "bar",
    data: {
      labels: ["High", "Medium", "Low"],
      datasets: [{
        data: ["High", "Medium", "Low"].map((level) => data.risk_counts[level] || 0),
        backgroundColor: [riskColors.High, riskColors.Medium, riskColors.Low],
        borderRadius: 3,
        maxBarThickness: 34,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: chartScales,
    },
  });
}

function renderMap(data) {
  document.getElementById("map-count").textContent = `${numberFormat.format(data.total)} filtered records · ${numberFormat.format(data.map_points.length)} villages shown`;
  const mapElement = document.getElementById("hotspot-map");
  document.getElementById("map-empty-state").hidden = data.map_points.length > 0;
  if (!window.L) {
    mapElement.innerHTML = '<div class="map-context">Map tiles could not be loaded. The records view is still available.</div>';
    return;
  }
  if (!state.map) {
    state.map = L.map(mapElement, {
      scrollWheelZoom: true,
      doubleClickZoom: true,
      touchZoom: true,
      keyboard: true,
      keyboardPanDelta: 120,
      zoomSnap: 0.5,
      zoomDelta: 0.5,
      wheelPxPerZoomLevel: 80,
    }).setView([17.1, 74.1], 8);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; OpenStreetMap contributors" }).addTo(state.map);
    state.markers = L.layerGroup().addTo(state.map);
  }
  state.markers.clearLayers();
  const bounds = [];
  data.map_points.forEach((point) => {
    if (!point.latitude || !point.longitude) return;
    const color = riskColors[point.hotspot_risk] || riskColors.Low;
    const marker = L.circleMarker([point.latitude, point.longitude], { radius: 5, color, weight: 1, fillColor: color, fillOpacity: 0.65 });
    marker.bindPopup(`<div class="map-popup"><strong>${escapeHtml(point.village_name)}</strong><br>${escapeHtml(point.taluka)}, ${escapeHtml(point.district)}<br>${numberFormat.format(point.incidents)} sample records · ${escapeHtml(point.hotspot_risk)} most-common label<br>Average sample score: ${point.risk_score.toFixed(2)}</div>`);
    marker.addTo(state.markers);
    bounds.push([point.latitude, point.longitude]);
  });
  if (bounds.length) state.map.fitBounds(bounds, { padding: [24, 24], maxZoom: 10 });
  setTimeout(() => state.map.invalidateSize(), 100);
}

async function renderRecords() {
  const params = filters();
  params.set("page", state.page);
  const villageMode = state.recordsMode === "villages";
  const data = await getJson(`${villageMode ? "/api/village-results" : "/api/records"}?${params}`);
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  document.getElementById("records-count").textContent = villageMode
    ? `${numberFormat.format(data.total)} matching villages`
    : `${numberFormat.format(data.total)} matching incident rows`;
  document.getElementById("records-sort-hint").textContent = villageMode
    ? "All villages · highest High-risk score first"
    : "Sample rows · newest date first";
  document.getElementById("page-indicator").textContent = `Page ${data.page} of ${totalPages}`;
  document.getElementById("previous-page").disabled = data.page <= 1;
  document.getElementById("next-page").disabled = data.page >= totalPages;
  document.getElementById("records-head").innerHTML = villageMode
    ? "<tr><th>VILLAGE</th><th>TALUKA</th><th>DISTRICT</th><th>SAMPLE ROWS</th><th>PROFILE BASIS</th><th>PREDICTED LABEL</th><th>HIGH-RISK SCORE</th></tr>"
    : "<tr><th>DATE</th><th>LOCATION</th><th>DISTRICT</th><th>WASTE TYPE</th><th>RISK SCORE</th><th>LABEL</th></tr>";
  const rows = villageMode
    ? data.villages.map((row) => `<tr><td><span class="location-name">${escapeHtml(row.village_name)}</span></td><td>${escapeHtml(row.taluka)}</td><td>${escapeHtml(row.district)}</td><td>${numberFormat.format(row.incident_rows)}</td><td><span class="profile-basis">${escapeHtml(row.profile_level)} · ${numberFormat.format(row.profile_sample_size)} rows</span></td><td>${riskBadge(row.risk_level)}</td><td>${row.high_risk_score.toFixed(1)}%</td></tr>`).join("")
    : data.records.map((row) => `<tr><td>${escapeHtml(row.date)}</td><td><span class="location-name">${escapeHtml(row.village_name)}</span><span class="location-sub">${escapeHtml(row.taluka)}</span></td><td>${escapeHtml(row.district)}</td><td>${escapeHtml(row.waste_type)}</td><td>${row.risk_score.toFixed(2)}</td><td>${riskBadge(row.hotspot_risk)}</td></tr>`).join("");
  const columnCount = villageMode ? 7 : 6;
  document.getElementById("records-body").innerHTML = rows || `<tr><td colspan="${columnCount}" class="empty-row">No ${villageMode ? "villages" : "incident rows"} match these filters.</td></tr>`;
  document.getElementById("export-link").hidden = villageMode;
  if (!villageMode) document.getElementById("export-link").href = `/api/export?${filters()}`;
}

function fillSelect(select, values, selectedValue) {
  select.innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  if (values.includes(String(selectedValue))) select.value = String(selectedValue);
}

function setLocalityOptions(select, values, placeholder, selectedValue = "") {
  select.innerHTML = [
    `<option value="">${escapeHtml(placeholder)}</option>`,
    ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`),
  ].join("");
  if (values.includes(selectedValue)) select.value = selectedValue;
}

function updatePredictionVillages(selectedVillage = "") {
  if (!state.predictionOptions) return;
  const places = state.predictionOptions.localities;
  const district = document.getElementById("prediction-district").value;
  const taluka = document.getElementById("prediction-taluka").value;
  const villageSelect = document.getElementById("prediction-village");
  const villages = [...new Set(
    places
      .filter((place) => place.district === district && place.taluka === taluka)
      .map((place) => place.village_name),
  )].sort();
  setLocalityOptions(villageSelect, villages, villages.length ? "Select a village" : "No villages available", selectedVillage);
}

function updatePredictionTalukas(selectedTaluka = "", selectedVillage = "") {
  if (!state.predictionOptions) return;
  const district = document.getElementById("prediction-district").value;
  const talukas = state.predictionOptions.talukas_by_district[district] || [];
  const talukaSelect = document.getElementById("prediction-taluka");
  setLocalityOptions(talukaSelect, talukas, "Select a taluka", selectedTaluka);
  updatePredictionVillages(selectedVillage);
}

async function loadPredictionOptions() {
  if (state.predictionOptions) return;
  const options = await getJson("/api/prediction-options");
  state.predictionOptions = options;

  const districtSelect = document.getElementById("prediction-district");
  fillSelect(districtSelect, options.districts, options.districts[0]);
  const firstPlace = options.localities.find((place) => place.district === districtSelect.value);
  updatePredictionTalukas(firstPlace?.taluka || "", firstPlace?.village_name || "");

  fillSelect(document.getElementById("prediction-waste"), options.categories.waste_type, options.categories.waste_type[0]);
  fillSelect(document.getElementById("prediction-land"), options.categories.land_type, options.categories.land_type[0]);
  fillSelect(document.getElementById("prediction-weather"), options.categories.weather, options.categories.weather[0]);
  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  fillSelect(document.getElementById("prediction-month"), monthNames.map((name, index) => `${index + 1}|${name}`), `${options.defaults.month}|${monthNames[options.defaults.month - 1]}`);

  const inputs = {
    hour: "prediction-hour",
    is_weekend: "prediction-weekend",
    month: "prediction-month",
    previous_incidents_30d: "prediction-previous",
    complaints_30d: "prediction-complaints",
    distance_to_main_road_km: "prediction-distance",
    nearby_road_density_km: "prediction-road-density",
    night_indicator: "prediction-night",
  };
  for (const [name, id] of Object.entries(inputs)) {
    const input = document.getElementById(id);
    const [minimum, maximum] = options.ranges[name];
    input.min = minimum;
    input.max = maximum;
    if (name === "month") continue;
    input.value = options.defaults[name];
  }
  applyPredictionProfile();
}

function applyPredictionProfile() {
  const options = state.predictionOptions;
  if (!options) return;

  const district = document.getElementById("prediction-district").value;
  const talukaSelect = document.getElementById("prediction-taluka");
  const villageSelect = document.getElementById("prediction-village");
  const taluka = talukaSelect.value;
  const village = villageSelect.value;

  const localityProfile = options.profiles.localities.find((profile) =>
    profile.district === district && profile.taluka === taluka && profile.village_name === village,
  );
  const talukaProfile = options.profiles.talukas.find((profile) =>
    profile.district === district && profile.taluka === taluka,
  );
  const districtProfile = options.profiles.districts.find((profile) => profile.district === district);
  const profile = localityProfile || talukaProfile || districtProfile;
  if (!profile) return;

  const defaults = profile.defaults;
  const categoryControls = {
    waste_type: "prediction-waste",
    land_type: "prediction-land",
    weather: "prediction-weather",
  };
  for (const [name, id] of Object.entries(categoryControls)) {
    document.getElementById(id).value = defaults[name];
  }

  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  document.getElementById("prediction-month").value = `${defaults.month}|${monthNames[defaults.month - 1]}`;
  const numericControls = {
    hour: "prediction-hour",
    is_weekend: "prediction-weekend",
    previous_incidents_30d: "prediction-previous",
    complaints_30d: "prediction-complaints",
    distance_to_main_road_km: "prediction-distance",
    nearby_road_density_km: "prediction-road-density",
    night_indicator: "prediction-night",
  };
  for (const [name, id] of Object.entries(numericControls)) {
    document.getElementById(id).value = defaults[name];
  }

  const profileSource = localityProfile ? `${village} village` : talukaProfile ? `${taluka} taluka` : `${district} district`;
  document.getElementById("prediction-profile-status").textContent =
    `Typical conditions loaded from ${profileSource} (${profile.sample_size} sample records). The selected village's mapped centroid is also used; adjust conditions to test another scenario.`;
}

function showPrediction(result) {
  const badge = document.getElementById("prediction-risk-badge");
  badge.textContent = result.risk_level;
  badge.className = `prediction-risk-badge risk-${result.risk_level.toLowerCase()}`;
  document.getElementById("prediction-high-score").textContent = `High-risk class score: ${((result.probabilities.High || 0) * 100).toFixed(1)}%`;
  document.getElementById("prediction-probabilities").innerHTML = ["High", "Medium", "Low"].map((level) => {
    const probability = result.probabilities[level] || 0;
    return `<div class="probability-row"><span>${level}</span><div class="probability-track"><span class="risk-fill-${level.toLowerCase()}" style="width:${(probability * 100).toFixed(1)}%"></span></div><b>${(probability * 100).toFixed(1)}%</b></div>`;
  }).join("");
  document.getElementById("prediction-disclaimer").textContent = result.disclaimer;
  const localityNote = document.getElementById("prediction-locality-note");
  localityNote.textContent = result.locality_note;
  localityNote.classList.toggle("unseen-locality", !result.locality_known);
  localityNote.hidden = false;
  document.getElementById("prediction-result").hidden = false;
}

async function submitPrediction(event) {
  event.preventDefault();
  const form = document.getElementById("prediction-form");
  const button = document.getElementById("predict-button");
  const error = document.getElementById("prediction-error");
  const result = document.getElementById("prediction-result");
  error.hidden = true;
  result.hidden = true;
  button.disabled = true;
  button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Training and predicting…';
  const payload = Object.fromEntries(new FormData(form));
  payload.month = Number(payload.month.split("|")[0]);
  for (const name of ["hour", "is_weekend", "previous_incidents_30d", "complaints_30d", "distance_to_main_road_km", "nearby_road_density_km", "night_indicator"]) {
    payload[name] = Number(payload[name]);
  }
  try {
    const response = await fetch("/api/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Prediction could not be generated.");
    showPrediction(data);
  } catch (predictionError) {
    error.textContent = predictionError.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = '<i class="bi bi-stars"></i> Predict sample risk';
  }
}

async function refresh() {
  try {
    const data = await getJson(`/api/dashboard?${filters()}`);
    renderOverview(data);
    renderPatterns(data);
    if (document.querySelector('[data-panel="map"]').classList.contains("active")) renderMap(data);
    if (document.querySelector('[data-panel="patterns"]').classList.contains("active")) await renderVillagePatterns();
    if (document.querySelector('[data-panel="records"]').classList.contains("active")) await renderRecords();
  } catch (error) {
    document.getElementById("metric-total").textContent = "Unavailable";
    console.error("Unable to load dashboard data", error);
  }
}

function setView(view) {
  if (!viewCopy[view]) return;
  document.querySelector(".filters").hidden = view === "prediction";
  document.querySelectorAll(".view-button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  document.querySelectorAll(".view-panel").forEach((panel) => {
    const active = panel.dataset.panel === view;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
  const [label, title, description] = viewCopy[view];
  document.getElementById("view-breadcrumb").textContent = label;
  document.getElementById("view-title").innerHTML = title;
  document.getElementById("view-description").textContent = description;
  if (view === "map") refresh();
  if (view === "patterns") renderVillagePatterns().catch(console.error);
  if (view === "records") renderRecords().catch(console.error);
  if (view === "prediction") loadPredictionOptions().catch((error) => {
    const message = document.getElementById("prediction-error");
    message.textContent = error.message;
    message.hidden = false;
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".view-button").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll("[data-open-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.openView)));
document.getElementById("district-filter").addEventListener("change", (event) => { state.district = event.target.value; state.page = 1; refresh(); });
document.getElementById("risk-filter").addEventListener("change", (event) => { state.risk = event.target.value; state.page = 1; refresh(); });
let searchTimer;
document.getElementById("search-filter").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = event.target.value.trim(); state.page = 1; refresh(); }, 250);
});
document.getElementById("clear-filters").addEventListener("click", () => {
  state.district = ""; state.risk = ""; state.query = ""; state.page = 1;
  document.getElementById("district-filter").value = "";
  document.getElementById("risk-filter").value = "";
  document.getElementById("search-filter").value = "";
  refresh();
});
document.getElementById("previous-page").addEventListener("click", () => { state.page = Math.max(1, state.page - 1); renderRecords().catch(console.error); });
document.getElementById("next-page").addEventListener("click", () => { state.page += 1; renderRecords().catch(console.error); });
document.querySelectorAll("[data-record-mode]").forEach((button) => button.addEventListener("click", () => {
  state.recordsMode = button.dataset.recordMode;
  state.page = 1;
  document.querySelectorAll("[data-record-mode]").forEach((modeButton) => {
    const active = modeButton === button;
    modeButton.classList.toggle("active", active);
    modeButton.setAttribute("aria-pressed", String(active));
  });
  renderRecords().catch(console.error);
}));
document.getElementById("prediction-district").addEventListener("change", () => {
  updatePredictionTalukas();
  applyPredictionProfile();
});
document.getElementById("prediction-taluka").addEventListener("change", () => {
  updatePredictionVillages();
  applyPredictionProfile();
});
document.getElementById("prediction-village").addEventListener("change", applyPredictionProfile);
document.getElementById("prediction-form").addEventListener("submit", submitPrediction);

refresh();