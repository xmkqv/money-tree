const pages = {
  orders: { history: [{ url: "/api/orders?limit=100", cursor: null }], cursorKey: "until", cursorField: "submitted_at", index: 0, rows: [], rowCount: 0 },
  fills: { history: [{ url: "/api/fills?limit=100", cursor: null }], cursorKey: "page_token", cursorField: "id", index: 0, rows: [], rowCount: 0 },
};
let csrfToken = "", brokerResumeAt = 0;
const currencyFormatter = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 });
const percentFormatter = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 2 });
const formatMoney = value => value == null ? "—" : currencyFormatter.format(Number(value));
const formatNumber = value => value == null ? "—" : numberFormatter.format(Number(value));
const formatPercent = value => value == null ? "—" : percentFormatter.format(Number(value));
const formatText = value => value ?? "—";
const formatTime = value => value ? new Date(value).toLocaleString() : "—";
const formatToggle = value => value == null ? "—" : value ? "Enabled" : "Disabled";
const createTextElement = (tag, text) => Object.assign(document.createElement(tag), { textContent: text });
const createTable = (selector, fields) => new Tabulator(selector, { data: [], layout: "fitColumns", responsiveLayout: "collapse", columnDefaults: { minWidth: 80 }, placeholder: "No records", columns: fields.map(([title, field]) => ({ title, field, headerFilter: "input" })) });
function renderPanelStatus(panelIds, payload, error) {
  for (const panelId of [panelIds].flat()) {
    const panel = document.getElementById(panelId);
    panel.dataset.state = error || payload.stale ? "stale" : "fresh";
    if (!error) panel.dataset.readAt = payload.read_at;
    panel.querySelector(".freshness").textContent = error
      ? `${error} · ${panel.dataset.readAt ? formatTime(panel.dataset.readAt) : "no successful read"}`
      : `${payload.stale ? "stale" : "updated"} · ${formatTime(payload.read_at)}`;
  }
}
async function refreshPanel(url, panelId, render) {
  const isBrokerRead = !["/api/run", "/api/events"].some(path => url.startsWith(path));
  if (isBrokerRead && Date.now() < brokerResumeAt) { renderPanelStatus(panelId, {}, "rate limited"); return; }
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (response.status === 401) { location.replace("/login"); return; }
    if (response.status === 503) {
      const retryAfter = response.headers.get("Retry-After") || "";
      const resumeAt = /^\d+$/.test(retryAfter) ? Date.now() + Number(retryAfter) * 1000 : Date.parse(retryAfter);
      brokerResumeAt = Number.isFinite(resumeAt) ? resumeAt : Date.now() + 60000;
    }
    if (!response.ok) throw new Error(`read failed (${response.status})`);
    const payload = await response.json();
    render(payload.data, payload);
    renderPanelStatus(panelId, payload);
  } catch (error) { renderPanelStatus(panelId, {}, error instanceof Error ? error.message : "read failed"); }
}
function renderMetrics(target, data, fields) {
  target.replaceChildren(...fields.map(([label, key, format]) => {
    const metric = Object.assign(createTextElement("div", ""), { className: "metric" });
    metric.append(createTextElement("span", label), createTextElement("strong", format(data[key])));
    return metric;
  }));
}
function renderRun(data, payload) {
  const element = document.getElementById("run");
  if (!data) { element.textContent = "No runtime snapshot"; return; }
  element.replaceChildren(
    createTextElement("strong", `${data.status}${payload.stale ? " · stale" : ""}`),
    createTextElement("span", `Strategies: ${data.strategies.join(", ")}`),
    createTextElement("span", `Heartbeat ${formatTime(data.heartbeat_at)}`),
  );
}
function renderConfiguration(data) {
  if (!data) { document.getElementById("configuration").textContent = "No runtime snapshot"; return; }
  renderMetrics(document.getElementById("configuration"), data.configuration, [["Trade risk", "risk_per_trade_max", formatPercent], ["Daily loss limit", "risk_per_day_max", formatPercent], ["Fractional orders", "fractional_orders", formatToggle], ["Position cap", "position_fraction_max", formatPercent]]);
}
const positionTable = createTable("#positions", [["Symbol", "symbol"], ["Side", "side"], ["Quantity", "qty"], ["Entry", "avg_entry_price"], ["Price", "current_price"], ["Market value", "market_value"], ["Unrealized P&L", "unrealized_pl"]]);
const openOrderTable = createTable("#open-orders", [["Submitted", "submitted_at"], ["Symbol", "symbol"], ["Side", "side"], ["Type", "type"], ["Quantity", "qty"], ["Filled", "filled_qty"], ["Status", "status"]]);
const orderTable = createTable("#orders", [["Submitted", "submitted_at"], ["Symbol", "symbol"], ["Side", "side"], ["Type", "type"], ["Quantity", "qty"], ["Filled", "filled_qty"], ["Status", "status"]]);
const fillTable = createTable("#fills", [["Time", "transaction_time"], ["Symbol", "symbol"], ["Side", "side"], ["Quantity", "qty"], ["Price", "price"], ["Order", "order_id"]]);
const eventTable = createTable("#events", [["Time", "occurred_at"], ["Level", "level"], ["Kind", "kind"], ["Message", "message"]]);
const chart = LightweightCharts.createChart(document.getElementById("equity-chart"), { autoSize: true, layout: { attributionLogo: true, background: { color: "transparent" }, textColor: "#8fa69a" }, grid: { vertLines: { color: "#172a21" }, horzLines: { color: "#172a21" } } });
const equitySeries = chart.addSeries(LightweightCharts.AreaSeries, { lineColor: "#6ee7a5", topColor: "#245f42aa", bottomColor: "#245f4200", title: "Equity" });
const profitSeries = chart.addSeries(LightweightCharts.LineSeries, { color: "#f4c66d", priceScaleId: "pnl", title: "P&L" });
function renderEquity(data) {
  const points = data.points.filter(point => point.equity != null && point.profit_loss != null);
  equitySeries.setData(points.map(point => ({ time: point.timestamp, value: Number(point.equity) })));
  profitSeries.setData(points.map(point => ({ time: point.timestamp, value: Number(point.profit_loss) })));
  chart.timeScale().fitContent();
}
function refreshPage(name) {
  const state = pages[name];
  const page = state.history[state.index];
  const target = name === "orders" ? orderTable : fillTable;
  const previous = document.querySelector(`[data-page="${name}-prev"]`);
  const next = document.querySelector(`[data-page="${name}-next"]`);
  state.rowCount = 0; previous.disabled = next.disabled = true;
  return refreshPanel(page.url, `${name}-panel`, rows => {
    state.rowCount = rows.length;
    state.rows = rows[0]?.id === page.cursor ? rows.slice(1) : rows;
    target.replaceData(state.rows);
    document.getElementById(`${name}-page`).textContent = `Page ${state.index + 1}`;
  }).finally(() => { previous.disabled = state.index === 0; next.disabled = state.rowCount < 100; });
}
function changePage(name, direction) {
  const state = pages[name];
  if (direction === "prev") state.index = Math.max(0, state.index - 1);
  if (direction === "next" && state.rowCount === 100) {
    const last = state.rows.at(-1);
    state.history.splice(state.index + 1, 1, { url: `/api/${name}?limit=100&${state.cursorKey}=${encodeURIComponent(last[state.cursorField])}`, cursor: last.id });
    state.index += 1;
  }
  refreshPage(name);
}
const jobs = [
  [5000, () => refreshPanel("/api/account", "account-panel", data => renderMetrics(document.getElementById("account"), data, [["Account ID", "id", formatText], ["Portfolio value", "portfolio_value", formatMoney], ["Cash", "cash", formatMoney], ["Buying power", "buying_power", formatMoney], ["Equity", "equity", formatMoney], ["Last equity", "last_equity", formatMoney], ["Day trades", "daytrade_count", formatNumber], ["Status", "status", formatText], ["Currency", "currency", formatText]]))],
  [5000, () => refreshPanel("/api/positions", "positions-panel", rows => positionTable.replaceData(rows))],
  [5000, () => refreshPanel("/api/orders/open", "open-orders-panel", rows => openOrderTable.replaceData(rows))],
  [5000, () => refreshPanel("/api/run", ["run-panel", "configuration-panel"], (data, payload) => { renderRun(data, payload); renderConfiguration(data); })],
  [5000, () => refreshPanel("/api/events?limit=50", "events-panel", rows => eventTable.replaceData(rows))],
  [15000, () => refreshPage("orders")], [15000, () => refreshPage("fills")],
  [60000, () => refreshPanel(`/api/equity?period=${document.querySelector("#periods [aria-pressed=true]").dataset.period}`, "equity-panel", renderEquity)],
].map(([delayMs, run]) => ({ delayMs, run, nextAt: 0 }));
function refresh() {
  if (document.hidden) return;
  const now = Date.now();
  jobs.forEach(job => { if (job.nextAt <= now) { job.nextAt = now + job.delayMs; job.run(); } });
}
async function readSession() {
  const response = await fetch("/api/session", { cache: "no-store" });
  if (!response.ok) { location.replace("/login"); return; }
  csrfToken = (await response.json()).csrf_token;
}
document.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => changePage(...button.dataset.page.split("-"))));
document.getElementById("periods").addEventListener("click", event => {
  const selected = event.target.closest("button[data-period]"); if (!selected) return;
  event.currentTarget.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", button === selected));
  jobs.at(-1).nextAt = 0; refresh();
});
document.addEventListener("visibilitychange", () => { if (document.hidden) return; jobs.forEach(job => job.nextAt = 0); refresh(); });
window.addEventListener("pageshow", event => { if (event.persisted) readSession(); });
document.getElementById("logout").addEventListener("click", async () => {
  const response = await fetch("/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
  if (response.ok) location.replace("/login"); });
readSession().then(refresh); setInterval(refresh, 1000);
