const pages = {
  orders: { urls: ["/api/orders?limit=100"], cursors: [null], index: 0, rows: [], full: 0 },
  fills: { urls: ["/api/fills?limit=100"], cursors: [null], index: 0, rows: [], full: 0 },
};
let csrfToken = "", brokerResumeAt = 0;

const money = value => value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
const number = value => value == null ? "—" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(Number(value));
const text = value => value ?? "—";
const timeText = value => value ? new Date(value).toLocaleString() : "—";
const createTable = (selector, fields) => new Tabulator(selector, { data: [], layout: "fitColumns", responsiveLayout: "collapse", columnDefaults: { minWidth: 80 }, placeholder: "No records", columns: fields.map(([title, field]) => ({ title, field, headerFilter: "input" })) });

function showReadStatus(panelId, payload, error) {
  const panel = document.getElementById(panelId);
  const label = panel.querySelector(".freshness");
  if (error) {
    panel.dataset.state = "stale";
    label.textContent = `${error} · ${panel.dataset.readAt ? timeText(panel.dataset.readAt) : "no successful read"}`;
    return;
  }
  panel.dataset.readAt = payload.read_at;
  panel.dataset.state = payload.stale ? "stale" : "fresh";
  label.textContent = `${payload.stale ? "stale" : "updated"} · ${timeText(payload.read_at)}`;
}

async function readPanel(url, panelId, show) {
  const isBrokerRead = !["/api/run", "/api/events"].some(path => url.startsWith(path));
  if (isBrokerRead && Date.now() < brokerResumeAt) { showReadStatus(panelId, {}, "rate limited"); return; }
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
    show(payload.data, payload);
    showReadStatus(panelId, payload);
  } catch (error) {
    showReadStatus(panelId, {}, error instanceof Error ? error.message : "read failed");
  }
}

function showAccount(data) {
  const fields = [["Portfolio value", "portfolio_value", money], ["Cash", "cash", money], ["Buying power", "buying_power", money], ["Equity", "equity", money], ["Last equity", "last_equity", money], ["Day trades", "daytrade_count", number], ["Status", "status", text], ["Currency", "currency", text]];
  const metrics = fields.map(([label, key, format]) => {
    const metric = document.createElement("div");
    const name = document.createElement("span");
    const value = document.createElement("strong");
    metric.className = "metric";
    name.textContent = label;
    value.textContent = format(data[key]);
    metric.append(name, value);
    return metric;
  });
  document.getElementById("account").replaceChildren(...metrics);
}

function showRun(data, payload) {
  const element = document.getElementById("run");
  if (!data) { element.textContent = "No runtime snapshot"; return; }
  const status = document.createElement("strong");
  const strategy = document.createElement("span");
  const heartbeat = document.createElement("span");
  status.textContent = `${data.status}${payload.stale ? " · stale" : ""}`;
  strategy.textContent = data.strategy;
  heartbeat.textContent = `Heartbeat ${timeText(data.heartbeat_at)}`;
  element.replaceChildren(status, strategy, heartbeat);
}

const positionTable = createTable("#positions", [["Symbol", "symbol"], ["Side", "side"], ["Quantity", "qty"], ["Entry", "avg_entry_price"], ["Price", "current_price"], ["Market value", "market_value"], ["Unrealized P&L", "unrealized_pl"]]);
const openOrderTable = createTable("#open-orders", [["Submitted", "submitted_at"], ["Symbol", "symbol"], ["Side", "side"], ["Type", "type"], ["Quantity", "qty"], ["Filled", "filled_qty"], ["Status", "status"]]);
const orderTable = createTable("#orders", [["Submitted", "submitted_at"], ["Symbol", "symbol"], ["Side", "side"], ["Type", "type"], ["Quantity", "qty"], ["Filled", "filled_qty"], ["Status", "status"]]);
const fillTable = createTable("#fills", [["Time", "transaction_time"], ["Symbol", "symbol"], ["Side", "side"], ["Quantity", "qty"], ["Price", "price"], ["Order", "order_id"]]);
const eventTable = createTable("#events", [["Time", "occurred_at"], ["Level", "level"], ["Kind", "kind"], ["Message", "message"]]);

const chart = LightweightCharts.createChart(document.getElementById("equity-chart"), { autoSize: true, layout: { attributionLogo: true, background: { color: "transparent" }, textColor: "#8fa69a" }, grid: { vertLines: { color: "#172a21" }, horzLines: { color: "#172a21" } } });
const equitySeries = chart.addSeries(LightweightCharts.AreaSeries, { lineColor: "#6ee7a5", topColor: "#245f42aa", bottomColor: "#245f4200", title: "Equity" });
const profitSeries = chart.addSeries(LightweightCharts.LineSeries, { color: "#f4c66d", priceScaleId: "pnl", title: "P&L" });

function showEquity(data) {
  const points = data.points.filter(point => point.equity != null && point.profit_loss != null);
  equitySeries.setData(points.map(point => ({ time: point.timestamp, value: Number(point.equity) })));
  profitSeries.setData(points.map(point => ({ time: point.timestamp, value: Number(point.profit_loss) })));
  chart.timeScale().fitContent();
}

function readPage(name) {
  const state = pages[name];
  const target = name === "orders" ? orderTable : fillTable;
  const previous = document.querySelector(`[data-page="${name}-prev"]`);
  const next = document.querySelector(`[data-page="${name}-next"]`);
  state.rows = [];
  state.full = 0;
  previous.disabled = next.disabled = true;
  return readPanel(state.urls[state.index], `${name}-panel`, rows => {
    state.full = rows.length;
    state.rows = rows[0]?.id === state.cursors[state.index] ? rows.slice(1) : rows;
    target.replaceData(state.rows);
    document.getElementById(`${name}-page`).textContent = `Page ${state.index + 1}`;
  }).finally(() => {
    previous.disabled = state.index === 0;
    next.disabled = state.full < 100;
  });
}

function changePage(name, direction) {
  const state = pages[name];
  if (direction === "prev") state.index = Math.max(0, state.index - 1);
  if (direction === "next" && state.full === 100) {
    const last = state.rows.at(-1);
    const key = name === "orders" ? "until" : "page_token";
    const cursor = name === "orders" ? last.submitted_at : last.id;
    state.urls.splice(state.index + 1, 1, `/api/${name}?limit=100&${key}=${encodeURIComponent(cursor)}`);
    state.cursors.splice(state.index + 1, 1, last.id);
    state.index += 1;
  }
  readPage(name);
}

const jobs = [
  [5000, () => readPanel("/api/account", "account-panel", showAccount)],
  [5000, () => readPanel("/api/positions", "positions-panel", rows => positionTable.replaceData(rows))],
  [5000, () => readPanel("/api/orders/open", "open-orders-panel", rows => openOrderTable.replaceData(rows))],
  [5000, () => readPanel("/api/run", "run-panel", showRun)],
  [5000, () => readPanel("/api/events?limit=50", "events-panel", rows => eventTable.replaceData(rows))],
  [15000, () => readPage("orders")], [15000, () => readPage("fills")],
  [60000, () => readPanel(`/api/equity?period=${document.querySelector("#periods [aria-pressed=true]").dataset.period}`, "equity-panel", showEquity)],
].map(([delay, run]) => ({ delay, run, next: 0 }));

function refresh() {
  if (document.hidden) return;
  const now = Date.now();
  jobs.forEach(job => { if (job.next <= now) { job.next = now + job.delay; job.run(); } });
}

async function readSession() {
  const response = await fetch("/api/session", { cache: "no-store" });
  if (!response.ok) { location.replace("/login"); return; }
  csrfToken = (await response.json()).csrf_token;
}

document.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => changePage(...button.dataset.page.split("-"))));
document.getElementById("periods").addEventListener("click", event => {
  const selected = event.target.closest("button[data-period]");
  if (!selected) return;
  event.currentTarget.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", button === selected));
  jobs.at(-1).next = 0;
  refresh();
});
document.addEventListener("visibilitychange", () => { if (document.hidden) return; jobs.forEach(job => job.next = 0); refresh(); });
window.addEventListener("pageshow", event => { if (event.persisted) readSession(); });
document.getElementById("logout").addEventListener("click", async () => {
  const response = await fetch("/logout", { method: "POST", headers: { "X-CSRF-Token": csrfToken } });
  if (response.ok) location.replace("/login");
});

readSession().then(refresh);
setInterval(refresh, 1000);
