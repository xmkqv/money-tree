"use strict";

/* ══ formatting ══════════════════════════════════════════ */

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const money = v => usd.format(v);
const signedMoney = v => (v > 0 ? "+" : v < 0 ? "−" : "") + usd.format(Math.abs(v));
const signedPct = (v, d = 2) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d) + "%";
const plainNum = v => new Intl.NumberFormat("en-US").format(v);
const tone = v => (v > 0 ? "pos" : v < 0 ? "neg" : "flat");
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/* the chart paints into SVG, so it re-reads its colours from the tokens on
   every draw — that's what makes it follow a theme change */
let GAIN = "#21AD71", LOSS = "#CB3B45", C = {};

function readTheme() {
  GAIN = token("--gain-mark");
  LOSS = token("--loss-mark");
  C = {
    grid: token("--grid"),
    gridZero: token("--grid-zero"),
    axis: token("--axis-ink"),
    crosshair: token("--crosshair"),
    ring: token("--ring"),
    tintMin: parseFloat(token("--tint-min")) || 0.09,
    tintMax: parseFloat(token("--tint-max")) || 0.30,
  };
}

const MONTHS = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"];
const MON3 = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DAY3 = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

/* ══ live state ══════════════════════════════════════════
   Everything below is derived from /api/ledger, which the server
   assembles from Alpaca on each poll. Nothing is generated here. */

const REFRESH_MS = 30000;

const STRATEGY_COLOURS = {
  orb: "var(--s-orb5)",
  orb_momentum: "var(--s-orb10)",
  sma: "var(--s-momentum)",
  tfb_50: "var(--s-tfb50)",
  unattributed: "var(--ink-3)",
};

const clockLabel = m => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const dparts = d => d.split("-").map(Number);
const dateOf = d => { const [y, m, day] = dparts(d); return new Date(y, m - 1, day); };

let LIVE, ACCOUNT, STRATEGIES, STRAT_BY_ID, OPEN_POSITIONS, ALL_TRADES, tradesByDate;
let LEDGER, SESSIONS, LAST_SESSION, DAY_PNL, WEEK_PNL, SPX, DAILY, INTRADAY, LATEST;
let FIRST_MONTH, LAST_MONTH, FIRST_IX, LAST_IX;
let STRATEGY_PERIODS = {};
let monthCache = new Map();
let todaySel = null;
let unit = "pct";
let stratRange = "D";

const monthIndex = (y, m) => y * 12 + m;

function statsFor(trades) {
  const wins = trades.filter(t => t.pnl > 0);
  const losses = trades.filter(t => t.pnl <= 0);
  const gross = wins.reduce((a, t) => a + t.pnl, 0);
  const bleed = Math.abs(losses.reduce((a, t) => a + t.pnl, 0));
  const net = trades.reduce((a, t) => a + t.pnl, 0);
  return {
    n: trades.length, wins: wins.length, losses: losses.length,
    winRate: trades.length ? (wins.length / trades.length) * 100 : 0,
    net, gross, bleed,
    profitFactor: bleed ? gross / bleed : Infinity,
    expectancy: trades.length ? net / trades.length : 0,
    avgWin: wins.length ? gross / wins.length : 0,
    avgLoss: losses.length ? bleed / losses.length : 0,
    best: trades.length ? Math.max(...trades.map(t => t.pnl)) : 0,
    worst: trades.length ? Math.min(...trades.map(t => t.pnl)) : 0,
  };
}

function periodFromTrades(key, base, trades) {
  const rows = {};
  for (const st of STRATEGIES) rows[st.id] = [0, 0];
  for (const t of trades) {
    if (!rows[t.strategy]) rows[t.strategy] = [0, 0];
    rows[t.strategy][0] += 1;
    rows[t.strategy][1] += t.pnl;
  }
  for (const id of Object.keys(rows)) rows[id][1] = Math.round(rows[id][1] * 100) / 100;
  STRATEGY_PERIODS[key] = { base, rows };
}

function monthData(y, m) {
  const key = y + "-" + m;
  if (monthCache.has(key)) return monthCache.get(key);

  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const days = [];
  let running = ACCOUNT.invested;

  for (let d = 1; d <= daysInMonth; d++) {
    const weekday = new Date(y, m, d).getDay();
    const iso = y + "-" + String(m + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
    const hit = LIVE.days.find(x => x.date === iso);
    const entry = {
      day: d, weekday, weekend: weekday === 0 || weekday === 6,
      pnl: null, trades: 0, wins: 0, closed: null,
      before: hit ? hit.before : running, iso,
    };
    if (hit) {
      entry.pnl = hit.pnl;
      entry.trades = hit.trades;
      entry.wins = hit.wins;
      running = hit.before + hit.pnl;
    }
    entry.pct = entry.pnl === null ? null : (entry.pnl / entry.before) * 100;
    days.push(entry);
  }

  const traded = days.filter(d => d.pnl !== null);
  const result = {
    y, m, days, opening: ACCOUNT.invested,
    pnl: Math.round(traded.reduce((s, d) => s + d.pnl, 0) * 100) / 100,
    trades: traded.reduce((s, d) => s + d.trades, 0),
    wins: traded.reduce((s, d) => s + d.wins, 0),
  };
  result.pct = result.opening ? (result.pnl / result.opening) * 100 : 0;
  monthCache.set(key, result);
  return result;
}

/* Monday-led weekday rows — markets don't trade weekends */
function weekRows(md) {
  const groups = new Map();
  for (const d of md.days) {
    if (d.weekend) continue;
    const monday = new Date(md.y, md.m, d.day - (d.weekday - 1));
    const key = monday.getFullYear() + "-" + monday.getMonth() + "-" + monday.getDate();
    if (!groups.has(key)) groups.set(key, new Array(5).fill(null));
    groups.get(key)[d.weekday - 1] = d;
  }
  return [...groups.values()].map(cells => {
    const traded = cells.filter(c => c && c.pnl !== null);
    const pnl = Math.round(traded.reduce((s, c) => s + c.pnl, 0) * 100) / 100;
    const base = traded.length ? traded[0].before : null;
    return { cells, pnl, pct: base ? (pnl / base) * 100 : null, any: traded.length > 0 };
  });
}

function tradesFor(y, m, cell) {
  if (!cell || cell.pnl === null) return [];
  return tradesByDate.get(cell.iso) || [];
}

function derive(live) {
  LIVE = live;
  monthCache = new Map();
  STRATEGY_PERIODS = {};

  STRATEGIES = live.strategies.map(s => ({
    id: s.id, label: s.short, sub: s.label, color: STRATEGY_COLOURS[s.id] || "var(--ink-3)",
  }));
  STRAT_BY_ID = Object.fromEntries(STRATEGIES.map(x => [x.id, x]));

  ACCOUNT = {
    invested: live.invested,
    portfolio: live.equity,
    cash: live.cash,
    deployed: live.marketValue,
    unrealised: live.unrealised,
    buyingPower: live.buyingPower,
    openPositions: live.positions.length,
    positionCapPct: live.positionCapPct,
    dailyLossLimitPct: live.dailyLossLimitPct,
  };
  ACCOUNT.totalReturn = Math.round((ACCOUNT.portfolio - ACCOUNT.invested) * 100) / 100;
  ACCOUNT.rateOfReturn = ACCOUNT.invested ? (ACCOUNT.totalReturn / ACCOUNT.invested) * 100 : 0;
  ACCOUNT.exposurePct = ACCOUNT.portfolio ? (ACCOUNT.deployed / ACCOUNT.portfolio) * 100 : 0;
  ACCOUNT.largestPositionPct = live.positions.length
    ? Math.max(...live.positions.map(p => p.weight)) : 0;

  OPEN_POSITIONS = live.positions;

  ALL_TRADES = live.trades.map(t => {
    const [y, m, day] = dparts(t.date);
    return { ...t, y, m: m - 1, day, weekday: dateOf(t.date).getDay() };
  }).reverse();

  tradesByDate = new Map();
  for (const t of live.trades) {
    if (!tradesByDate.has(t.date)) tradesByDate.set(t.date, []);
    tradesByDate.get(t.date).push(t);
  }

  LEDGER = statsFor(ALL_TRADES);
  ACCOUNT.closed = LEDGER.n;
  ACCOUNT.wins = LEDGER.wins;
  ACCOUNT.losses = LEDGER.losses;
  ACCOUNT.winRate = LEDGER.winRate;

  SESSIONS = live.days.map(d => ({
    ...d,
    pct: d.before ? (d.pnl / d.before) * 100 : 0,
    label: dateOf(d.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
    long: dateOf(d.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" }),
  }));

  LAST_SESSION = SESSIONS[SESSIONS.length - 1] || { date: live.equityDaily.at(-1).date, pnl: 0, before: live.equity, pct: 0, trades: 0, wins: 0 };
  DAY_PNL = LAST_SESSION.pnl;

  const weekCut = live.days.length > 3 ? live.days[live.days.length - 3].date : (live.days[0] || LAST_SESSION).date;
  const weekTrades = live.trades.filter(t => t.date >= weekCut);
  WEEK_PNL = Math.round(weekTrades.reduce((a, t) => a + t.pnl, 0) * 100) / 100;

  const monthKey = LAST_SESSION.date.slice(0, 7);
  periodFromTrades("D", LAST_SESSION.before, tradesByDate.get(LAST_SESSION.date) || []);
  periodFromTrades("W", (live.days.find(d => d.date === weekCut) || LAST_SESSION).before, weekTrades);
  periodFromTrades("M", ACCOUNT.invested, live.trades.filter(t => t.date.startsWith(monthKey)));
  periodFromTrades("ALL", ACCOUNT.invested, live.trades);

  const spy = live.spy;
  const at = i => spy[i].close;
  const since = from => {
    const i = spy.findIndex(b => b.date >= from);
    return i < 0 || spy.length < 2 ? 0 : (at(spy.length - 1) / at(Math.max(0, i - 1)) - 1) * 100;
  };
  SPX = spy.length > 1
    ? { D: (at(spy.length - 1) / at(spy.length - 2) - 1) * 100, W: since(weekCut),
        M: since(monthKey + "-01"), ALL: (at(spy.length - 1) / at(0) - 1) * 100 }
    : { D: 0, W: 0, M: 0, ALL: 0 };

  const [ly, lm, lday] = dparts(LAST_SESSION.date);
  LATEST = { y: ly, m: lm - 1, day: lday };
  FIRST_MONTH = { y: ly, m: lm - 1 };
  LAST_MONTH = { y: ly, m: lm - 1 };
  FIRST_IX = monthIndex(FIRST_MONTH.y, FIRST_MONTH.m);
  LAST_IX = monthIndex(LAST_MONTH.y, LAST_MONTH.m);

  DAILY = live.equityDaily.map((r, i) => ({
    label: dateOf(r.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
    long: dateOf(r.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }),
    value: Math.round((r.equity - live.invested) * 100) / 100,
    before: i ? Math.round((live.equityDaily[i - 1].equity - live.invested) * 100) / 100 : 0,
  }));
  DAILY.equityBase = live.invested;

  const opening = live.intraday.length ? live.intraday[0].equity : live.equity;
  INTRADAY = live.intraday.map((r, i) => ({
    label: r.t,
    long: (live.intradayDate ? dateOf(live.intradayDate).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) + ", " : "") + r.t,
    value: Math.round((r.equity - live.invested) * 100) / 100,
    before: Math.round(((i ? live.intraday[i - 1].equity : opening) - live.invested) * 100) / 100,
  }));
  INTRADAY.equityBase = live.invested;
  if (!INTRADAY.length) INTRADAY = DAILY;

  ACCOUNT.dayDrawdownPct = live.intraday.length
    ? Math.abs(Math.min(0, Math.min(...live.intraday.map(r => r.equity)) - opening)) / opening * 100
    : 0;
}

/* ══ today panel ═════════════════════════════════════════ */

let todayTab = "closed";

const isLatest = () => todaySel.y === LATEST.y && todaySel.m === LATEST.m && todaySel.day === LATEST.day;

function selectedCell() {
  const md = monthData(todaySel.y, todaySel.m);
  return md.days.find(d => d.day === todaySel.day) || null;
}

function renderToday() {
  const cell = selectedCell();
  const trades = tradesFor(todaySel.y, todaySel.m, cell);
  const weekday = new Date(todaySel.y, todaySel.m, todaySel.day).getDay();

  const iso = todaySel.y + "-" + String(todaySel.m + 1).padStart(2, "0") + "-" + String(todaySel.day).padStart(2, "0");
  document.getElementById("today-heading").textContent =
    iso === LIVE.today ? "Today" : isLatest() ? "Last session" : "Session";
  document.getElementById("today-date").textContent =
    DAY3[weekday] + " " + todaySel.day + " " + MON3[todaySel.m] + " " + todaySel.y;
  document.getElementById("today-reset").classList.toggle("hidden", isLatest());

  document.getElementById("n-closed").textContent = trades.length;
  document.getElementById("n-open").textContent = OPEN_POSITIONS.length;

  const sum = document.getElementById("today-sum");
  const table = document.getElementById("today-table");
  sum.replaceChildren();
  table.replaceChildren();

  if (todayTab === "open") {
    sum.innerHTML =
      "Unrealised <b class='" + tone(ACCOUNT.unrealised) + "'>" + signedMoney(ACCOUNT.unrealised) + "</b>" +
      "<span>Deployed <b>" + money(ACCOUNT.deployed) + "</b></span>" +
      "<span>Exposure <b>" + ACCOUNT.exposurePct.toFixed(1) + "%</b></span>" +
      "<span>Largest <b>" + ACCOUNT.largestPositionPct.toFixed(1) + "%</b> of " + ACCOUNT.positionCapPct.toFixed(1) + "% cap</span>";
    buildTable(table,
      ["Symbol", "Strategy", "Entry", "Last", "Value", "Unreal."],
      OPEN_POSITIONS.map(pos => [
        symbolCell(pos.symbol, pos.side),
        stratCell(pos.strategy),
        { t: money(pos.entry), r: true },
        { t: money(pos.last), r: true },
        { t: money(pos.value), r: true, dim: true },
        { t: signedMoney(pos.unreal), r: true, cls: tone(pos.unreal) },
      ]), 2);
    return;
  }

  if (!cell || cell.closed) {
    sum.innerHTML = "<span>" + (cell && cell.closed ? cell.closed + " — market closed" : "No session") + "</span>";
    table.innerHTML = "<tbody><tr><td class='empty'>" +
      (cell && cell.closed ? "Market closed. No trades placed." : "No session on this date.") + "</td></tr></tbody>";
    return;
  }

  if (!trades.length) {
    sum.innerHTML = "<span>No entries triggered</span>";
    table.innerHTML = "<tbody><tr><td class='empty'>No trades — no strategy signalled an entry.</td></tr></tbody>";
    return;
  }

  const realised = trades.reduce((a, t) => a + t.pnl, 0);
  const wins = trades.filter(t => t.pnl > 0).length;
  sum.innerHTML =
    "Realised <b class='" + tone(realised) + "'>" + signedMoney(realised) + "</b>" +
    "<span><b>" + wins + "</b> of <b>" + trades.length + "</b> won</span>" +
    "<span>Return <b class='" + tone(cell.pct) + "'>" + signedPct(cell.pct) + "</b></span>";

  buildTable(table,
    ["Time", "Symbol", "Strategy", "In", "Out", "P&L"],
    trades.map(t => [
      { t: clockLabel(t.minute), dim: true },
      symbolCell(t.symbol, t.side),
      stratCell(t.strategy),
      { t: money(t.entry), r: true },
      { t: money(t.exit), r: true },
      { t: signedMoney(t.pnl), r: true, cls: tone(t.pnl) },
    ]), 3);
}

function symbolCell(symbol, side) {
  const wrap = document.createElement("span");
  const sym = document.createElement("span");
  sym.className = "sym";
  sym.textContent = symbol;
  const tag = document.createElement("span");
  tag.className = "side" + (side === "short" ? " short" : "");
  tag.textContent = side === "short" ? "S" : "L";
  tag.title = side === "short" ? "Short" : "Long";
  wrap.append(sym, tag);
  return { node: wrap };
}

function stratCell(id) {
  const s = STRAT_BY_ID[id];
  const wrap = document.createElement("span");
  wrap.className = "tstrat";
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.style.background = s.color;
  const name = document.createElement("span");
  name.textContent = s.label;
  wrap.append(chip, name);
  wrap.title = s.sub;
  return { node: wrap };
}

function buildTable(table, headers, rows, rightFrom, rowClass) {
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  headers.forEach((h, i) => {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = h;
    if (i >= rightFrom) th.className = "r";
    hr.append(th);
  });
  thead.append(hr);

  const tbody = document.createElement("tbody");
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    if (rowClass) {
      const extra = rowClass(row, index);
      if (extra) tr.className = extra;
    }
    for (const c of row) {
      const td = document.createElement("td");
      if (c.node) td.append(c.node);
      else td.textContent = c.t;
      if (c.r) td.classList.add("r");
      if (c.cls) td.classList.add(c.cls);
      if (c.dim) td.classList.add("flat");
      tr.append(td);
    }
    tbody.append(tr);
  });
  /* Rebuilt in place on every poll, so clear first: appending would stack a
     fresh header and body under the previous ones on each refresh. */
  table.replaceChildren(thead, tbody);
}

function selectDay(y, m, day) {
  todaySel = { y, m, day };
  renderToday();
  renderCalendar();
}

/* ══ left rail ═══════════════════════════════════════════ */

function renderAccount() {
  document.getElementById("chart-funded").textContent =
    "Funded " + money(ACCOUNT.invested) + " · " + LIVE.funded;
  document.getElementById("v-portfolio").textContent = money(ACCOUNT.portfolio);
  document.getElementById("v-cash").textContent = money(ACCOUNT.cash);

  const tr = document.getElementById("v-tr");
  tr.className = "v " + tone(ACCOUNT.totalReturn);
  tr.innerHTML = signedMoney(ACCOUNT.totalReturn) +
    '<span class="u">' + signedPct(ACCOUNT.rateOfReturn) + "</span>";

  const dayPct = (DAY_PNL / STRATEGY_PERIODS.D.base) * 100;
  const d24 = document.getElementById("v-d24");
  d24.className = "v " + tone(DAY_PNL);
  d24.innerHTML = signedMoney(DAY_PNL) + '<span class="u">' + signedPct(dayPct) + "</span>";

  document.getElementById("v-open").textContent = ACCOUNT.openPositions;
  document.getElementById("v-exposure").textContent = ACCOUNT.exposurePct.toFixed(1) + "%";

  document.getElementById("v-dll").innerHTML =
    "<b>" + ACCOUNT.dayDrawdownPct.toFixed(2) + "%</b> of " + ACCOUNT.dailyLossLimitPct.toFixed(2) + "%";
  const dllUsed = clamp(ACCOUNT.dayDrawdownPct / ACCOUNT.dailyLossLimitPct, 0, 1) * 100;
  const dll = document.getElementById("m-dll");
  dll.style.width = Math.max(dllUsed, 1.5) + "%";
  dll.style.background = "var(--loss-mark)";

  document.getElementById("v-cap").innerHTML =
    "<b>" + ACCOUNT.largestPositionPct.toFixed(1) + "%</b> of " + ACCOUNT.positionCapPct.toFixed(1) + "%";
  const cap = document.getElementById("m-cap");
  cap.style.width = clamp(ACCOUNT.largestPositionPct / ACCOUNT.positionCapPct, 0, 1) * 100 + "%";
  cap.style.background = "var(--ink-3)";

  document.getElementById("v-winrate").textContent = ACCOUNT.winRate.toFixed(1) + "%";
  document.getElementById("bar-w").style.flex = String(ACCOUNT.wins);
  document.getElementById("bar-l").style.flex = String(ACCOUNT.losses);
  document.getElementById("lg-w").textContent = ACCOUNT.wins + " wins";
  document.getElementById("lg-l").textContent = ACCOUNT.losses + " losses";
  document.getElementById("winrate-bar").setAttribute("aria-label",
    "Win rate " + ACCOUNT.winRate.toFixed(1) + " percent: " + ACCOUNT.wins + " wins and " +
    ACCOUNT.losses + " losses across " + ACCOUNT.closed + " closed trades");

  const bar = document.getElementById("status");
  bar.classList.toggle("closed", !LIVE.marketOpen);
  document.getElementById("st-word").textContent = LIVE.marketOpen ? "Market open" : "Market closed";
  document.getElementById("st-session").textContent =
    LIVE.marketOpen ? "closes 16:00 ET" : "opens " + LIVE.nextOpen;
  document.getElementById("st-strats").textContent =
    "Paper " + LIVE.accountNumber + " · " + LIVE.positions.length + " positions";
  document.getElementById("st-asof").textContent = LIVE.asOf;
}



function renderPeriodReturns() {
  const host = document.getElementById("period-cells");
  host.replaceChildren();

  for (const [label, key] of [["Session", "D"], ["Week", "W"], ["Month", "M"], ["Inception", "ALL"]]) {
    const p = STRATEGY_PERIODS[key];
    const pnl = Object.values(p.rows).reduce((s, r) => s + r[1], 0);
    host.append(periodCell(label, pnl, (pnl / p.base) * 100, SPX[key]));
  }
}

function periodCell(label, pnl, pct, spx) {
  const cell = document.createElement("div");
  cell.className = "period-cell";

  const k = document.createElement("span");
  k.className = "k";
  k.textContent = label;

  const v = document.createElement("span");
  v.className = "v " + tone(pct);
  v.textContent = unit === "pct" ? signedPct(pct) : signedMoney(pnl);

  const bench = document.createElement("span");
  bench.className = "bench";
  bench.textContent = "SPX " + signedPct(spx);

  cell.append(k, v, bench);
  return cell;
}



/* Two separate questions, deliberately kept apart.

   Switch  — have we left this engine enabled, or paused it? That is the
             roster the bot publishes, and it does not change with the clock.
   Session — can it start a trade right now? The market must be open and the
             clock inside this engine's own entry window. Positions already
             open are still managed outside it; this is about new trades. */

const SWITCH_STATE = {
  online:  { label: "Online",  hint: "Enabled — this engine is allowed to trade" },
  offline: { label: "Offline", hint: "Paused by us — this engine will not open a trade" },
  unknown: { label: "Unknown", hint: "The bot has not reported, so its roster is unknown" },
};

const SESSION_STATE = {
  open:   { label: "Open",   hint: "Inside its entry window — it can open a trade now" },
  closed: { label: "Closed", hint: "Outside its entry window — no new trade will start" },
};

function switchState(id) {
  const bot = LIVE.bot || {};
  if (!bot.reported) return "unknown";
  return (bot.strategies || []).includes(id) ? "online" : "offline";
}

/* The viewer's own clock may be set to any zone, so read the exchange's. */
function tradingMinutes() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date());
  const at = type => Number(parts.find(p => p.type === type).value);
  return at("hour") * 60 + at("minute");
}

function toMinutes(clock) {
  const [h, m] = String(clock).split(":");
  return Number(h) * 60 + Number(m);
}

function sessionState(id) {
  const window = (LIVE.windows || {})[id];
  if (!LIVE.marketOpen || !window) return "closed";
  const now = tradingMinutes();
  return now >= toMinutes(window.from) && now <= toMinutes(window.to) ? "open" : "closed";
}

function windowLabel(id) {
  const window = (LIVE.windows || {})[id];
  return window ? window.from + "–" + window.to + " ET" : "";
}

function stateBadge(kind, key, table, extra) {
  const pill = document.createElement("span");
  pill.className = "run-state " + kind + " is-" + key;
  pill.textContent = table[key].label;
  pill.title = extra ? table[key].hint + " (" + extra + ")" : table[key].hint;
  return pill;
}

function stateBadges(id) {
  const wrap = document.createElement("span");
  wrap.className = "states";
  wrap.append(
    stateBadge("switch", switchState(id), SWITCH_STATE),
    stateBadge("session", sessionState(id), SESSION_STATE, windowLabel(id)),
  );
  return wrap;
}

function renderStrategies(period) {
  const body = document.getElementById("strat-body");
  const p = STRATEGY_PERIODS[period];
  body.replaceChildren();

  for (const s of STRATEGIES) {
    const [trades, pnl] = p.rows[s.id];
    /* the catch-all bucket only earns a row when something landed in it */
    if (s.id === "unattributed" && trades === 0) continue;
    const tr = document.createElement("tr");

    const nameCell = document.createElement("td");
    const strat = document.createElement("div");
    strat.className = "strat";
    strat.title = s.sub;
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = s.color;
    const nm = document.createElement("span");
    nm.className = "name";
    nm.textContent = s.label;
    strat.append(chip, nm);
    /* the catch-all bucket is a place trades land, not an engine that runs */
    if (s.id !== "unattributed") strat.append(stateBadges(s.id));
    nameCell.append(strat);

    const tradeCell = document.createElement("td");
    tradeCell.className = "r num";
    tradeCell.textContent = trades === 0 ? "—" : plainNum(trades);
    if (trades === 0) tradeCell.classList.add("flat");

    const pnlCell = document.createElement("td");
    pnlCell.className = "r pnl-cell";
    const big = document.createElement("span");
    big.className = "num " + tone(pnl);
    big.textContent = trades === 0 ? "—" : signedMoney(pnl);
    const small = document.createElement("span");
    small.className = "sub";
    small.textContent = trades === 0 ? "" : signedPct((pnl / p.base) * 100);
    pnlCell.append(big, small);

    tr.append(nameCell, tradeCell, pnlCell);
    body.append(tr);
  }
}

/* ══ balance chart — pannable, zoomable viewport ═════════ */

const PAD = { t: 12, r: 58, b: 22, l: 16 };

const chart = {
  series: null,
  i0: 0, i1: 1,          /* fractional index window */
  yManual: null,         /* {min,max} once the price axis is dragged */
  preset: "ALL",
  custom: false,
};

let geo = null;          /* geometry of the last draw, for hit-testing */

function presetWindow(range) {
  if (range === "D") return { series: INTRADAY, i0: 0, i1: INTRADAY.length - 1 };
  const n = DAILY.length;
  const span = range === "W" ? Math.min(6, n - 1) : n - 1;
  return { series: DAILY, i0: Math.max(0, n - 1 - span), i1: n - 1 };
}

function setRange(range) {
  const w = presetWindow(range);
  chart.series = w.series;
  chart.i0 = w.i0;
  chart.i1 = w.i1;
  chart.yManual = null;
  chart.preset = range;
  chart.custom = false;
  syncRangeButtons();
  drawChart();
}

function syncRangeButtons() {
  for (const b of document.querySelectorAll("#chart-range button")) {
    b.setAttribute("aria-pressed", String(!chart.custom && b.dataset.range === chart.preset));
  }
}

function markCustom() {
  if (chart.custom) return;
  chart.custom = true;
  syncRangeButtons();
}

function niceStep(raw) {
  const mag = Math.pow(10, Math.floor(Math.log10(Math.abs(raw) || 1)));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
}

function drawChart() {
  const host = document.getElementById("chart-host");
  const width = host.clientWidth;
  const height = host.clientHeight;
  if (width < 60 || height < 60) return;
  if (!chart.series || !chart.series.length) return;   /* nothing fetched yet */
  readTheme();

  const s = chart.series;
  const N = s.length;
  const plotW = width - PAD.l - PAD.r;
  const plotH = height - PAD.t - PAD.b;

  const i0 = chart.i0, i1 = chart.i1;
  const lo = clamp(Math.floor(i0), 0, N - 1);
  const hi = clamp(Math.ceil(i1), 0, N - 1);

  const baseline = s[lo].before;
  const visible = [];
  for (let i = lo; i <= hi; i++) visible.push({ i, p: s[i], y: s[i].value - baseline });

  let yMin, yMax;
  if (chart.yManual) {
    yMin = chart.yManual.min; yMax = chart.yManual.max;
  } else {
    const ys = visible.map(v => v.y).concat([0]);
    const a = Math.min(...ys), b = Math.max(...ys);
    const pad = ((b - a) || 1) * 0.14;
    yMin = a - pad; yMax = b + pad;
  }

  const px = i => PAD.l + ((i - i0) / (i1 - i0)) * plotW;
  const py = v => PAD.t + (1 - (v - yMin) / (yMax - yMin)) * plotH;
  geo = { width, height, plotW, plotH, N, px, py, yMin, yMax, baseline, lo, hi };

  const zeroY = clamp(py(0), PAD.t, PAD.t + plotH);
  const line = visible.map((v, k) => (k ? "L" : "M") + px(v.i).toFixed(2) + " " + py(v.y).toFixed(2)).join(" ");
  const area = line +
    " L" + px(visible[visible.length - 1].i).toFixed(2) + " " + zeroY.toFixed(2) +
    " L" + px(visible[0].i).toFixed(2) + " " + zeroY.toFixed(2) + " Z";

  /* y grid in rebased units */
  const ticks = [];
  const step = niceStep((yMax - yMin) / 3.2);
  for (let t = Math.ceil(yMin / step) * step; t <= yMax; t += step) ticks.push(t);

  const gridSvg = ticks.map(t =>
    '<line x1="' + PAD.l + '" y1="' + py(t).toFixed(2) + '" x2="' + (width - PAD.r) + '" y2="' + py(t).toFixed(2) +
    '" stroke="' + (Math.abs(t) < 1e-9 ? C.gridZero : C.grid) + '" stroke-width="1"' +
    (Math.abs(t) < 1e-9 ? ' stroke-dasharray="3 3"' : "") + "/>" +
    '<text x="' + (width - PAD.r + 8) + '" y="' + (py(t) + 3.5).toFixed(2) + '" fill="' + C.axis + '" font-size="10" ' +
    'font-family="Roboto Mono, monospace">' + (t >= 0 ? "" : "−") + usd0.format(Math.abs(t)) + "</text>"
  ).join("");

  /* x labels: about six, evenly spaced across the visible window */
  const count = visible.length;
  const every = Math.max(1, Math.ceil(count / 6));
  const xSvg = visible.map((v, k) =>
    (k % every === 0 || k === count - 1)
      ? '<text x="' + clamp(px(v.i), PAD.l + 14, width - PAD.r - 14).toFixed(2) + '" y="' + (height - 6) +
        '" fill="' + C.axis + '" font-size="10" text-anchor="middle" ' +
        'font-family="Roboto Mono, monospace">' + v.p.label + "</text>"
      : ""
  ).join("");

  const last = visible[visible.length - 1];
  const lastTone = last.y >= 0 ? GAIN : LOSS;

  host.querySelectorAll("svg").forEach(n => n.remove());
  host.insertAdjacentHTML("afterbegin",
    '<svg viewBox="0 0 ' + width + " " + height + '" preserveAspectRatio="none" ' +
    'role="img" aria-label="Cumulative profit and loss across the visible window">' +
      "<defs>" +
        '<linearGradient id="gPos" x1="0" x2="0" y1="' + PAD.t + '" y2="' + zeroY + '" gradientUnits="userSpaceOnUse">' +
          '<stop offset="0" stop-color="' + GAIN + '" stop-opacity="0.36"/>' +
          '<stop offset="1" stop-color="' + GAIN + '" stop-opacity="0.02"/></linearGradient>' +
        '<linearGradient id="gNeg" x1="0" x2="0" y1="' + zeroY + '" y2="' + (height - PAD.b) + '" gradientUnits="userSpaceOnUse">' +
          '<stop offset="0" stop-color="' + LOSS + '" stop-opacity="0.03"/>' +
          '<stop offset="1" stop-color="' + LOSS + '" stop-opacity="0.34"/></linearGradient>' +
        '<clipPath id="cPlot"><rect x="' + PAD.l + '" y="' + PAD.t + '" width="' + plotW + '" height="' + plotH + '"/></clipPath>' +
        '<clipPath id="cPos"><rect x="0" y="0" width="' + width + '" height="' + Math.max(0, zeroY) + '"/></clipPath>' +
        '<clipPath id="cNeg"><rect x="0" y="' + zeroY + '" width="' + width + '" height="' + Math.max(0, height - zeroY) + '"/></clipPath>' +
      "</defs>" +
      gridSvg +
      '<g clip-path="url(#cPlot)">' +
        '<path d="' + area + '" fill="url(#gPos)" clip-path="url(#cPos)"/>' +
        '<path d="' + area + '" fill="url(#gNeg)" clip-path="url(#cNeg)"/>' +
        '<path d="' + line + '" fill="none" stroke="' + GAIN + '" stroke-width="2" stroke-linejoin="round" ' +
          'vector-effect="non-scaling-stroke" clip-path="url(#cPos)"/>' +
        '<path d="' + line + '" fill="none" stroke="' + LOSS + '" stroke-width="2" stroke-linejoin="round" ' +
          'vector-effect="non-scaling-stroke" clip-path="url(#cNeg)"/>' +
        '<line id="cross" x1="0" y1="' + PAD.t + '" x2="0" y2="' + (PAD.t + plotH) + '" stroke="' + C.crosshair + '" ' +
          'stroke-width="1" vector-effect="non-scaling-stroke" opacity="0"/>' +
        '<circle id="crossDot" r="4.5" fill="' + lastTone + '" stroke="' + C.ring + '" stroke-width="2" opacity="0"/>' +
        '<circle cx="' + px(last.i).toFixed(2) + '" cy="' + py(last.y).toFixed(2) + '" r="4.5" ' +
          'fill="' + lastTone + '" stroke="' + C.ring + '" stroke-width="2"/>' +
      "</g>" +
      xSvg +
    "</svg>"
  );

  /* hit areas track the plot geometry exactly (SVG units are CSS px here) */
  Object.assign(document.getElementById("plot-hit").style, {
    left: PAD.l + "px", top: PAD.t + "px", width: plotW + "px", height: plotH + "px",
  });
  Object.assign(document.getElementById("axis-hit").style, {
    left: (width - PAD.r) + "px", top: PAD.t + "px", width: PAD.r + "px", height: plotH + "px",
  });

  /* hero reads the visible window, because that's what the chart is showing */
  const delta = last.y;
  const equityAtStart = s.equityBase + baseline;

  const big = document.getElementById("chart-big");
  big.textContent = signedMoney(delta);
  big.className = "big num " + tone(delta);

  const d = document.getElementById("chart-delta");
  d.textContent = signedPct((delta / equityAtStart) * 100) + " over view";
  d.className = "delta " + tone(delta);

  document.getElementById("chart-note").textContent =
    visible[0].p.label + " – " + last.p.label + (chart.series === INTRADAY ? " · Fri 30 Jan" : "");

  document.getElementById("chart-table").innerHTML =
    "<table><caption>Cumulative profit and loss across the visible window</caption><tbody>" +
    visible.map(v => "<tr><th scope='row'>" + v.p.long + "</th><td>" + signedMoney(v.y) + "</td></tr>").join("") +
    "</tbody></table>";
}

/* ── chart interaction ─────────────────────────────────── */

function indexAt(clientX) {
  const host = document.getElementById("chart-host").getBoundingClientRect();
  const x = clientX - host.left;
  return chart.i0 + ((x - PAD.l) / geo.plotW) * (chart.i1 - chart.i0);
}

function clampWindow() {
  const N = chart.series.length;
  let span = chart.i1 - chart.i0;
  span = clamp(span, 3, N - 1);
  if (chart.i0 < 0) chart.i0 = 0;
  if (chart.i0 + span > N - 1) chart.i0 = N - 1 - span;
  chart.i1 = chart.i0 + span;
}

function initChartInteraction() {
  const plot = document.getElementById("plot-hit");
  const axis = document.getElementById("axis-hit");
  const tip = document.getElementById("chart-tip");
  const host = document.getElementById("chart-host");

  let drag = null;

  /* zoom the time axis around the cursor */
  plot.addEventListener("wheel", ev => {
    ev.preventDefault();
    if (!geo) return;
    const anchor = indexAt(ev.clientX);
    const span = chart.i1 - chart.i0;
    const next = clamp(span * (ev.deltaY > 0 ? 1.14 : 1 / 1.14), 3, chart.series.length - 1);
    chart.i0 = anchor - (anchor - chart.i0) * (next / span);
    chart.i1 = chart.i0 + next;
    clampWindow();
    markCustom();
    drawChart();
  }, { passive: false });

  /* click-hold to drag the chart through time */
  plot.addEventListener("pointerdown", ev => {
    plot.setPointerCapture(ev.pointerId);
    plot.classList.add("dragging");
    drag = { x: ev.clientX, y: ev.clientY, mode: "pan" };
  });

  axis.addEventListener("pointerdown", ev => {
    axis.setPointerCapture(ev.pointerId);
    if (!chart.yManual && geo) chart.yManual = { min: geo.yMin, max: geo.yMax };
    drag = { x: ev.clientX, y: ev.clientY, mode: "scale" };
  });

  function endDrag(ev) {
    if (!drag) return;
    drag = null;
    plot.classList.remove("dragging");
    if (plot.hasPointerCapture?.(ev.pointerId)) plot.releasePointerCapture(ev.pointerId);
    if (axis.hasPointerCapture?.(ev.pointerId)) axis.releasePointerCapture(ev.pointerId);
  }

  for (const el of [plot, axis]) {
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
  }

  plot.addEventListener("pointermove", ev => {
    if (!geo) return;

    if (drag && drag.mode === "pan") {
      const dx = ev.clientX - drag.x;
      const dy = ev.clientY - drag.y;
      drag.x = ev.clientX; drag.y = ev.clientY;

      const span = chart.i1 - chart.i0;
      const di = -dx * (span / geo.plotW);
      chart.i0 += di; chart.i1 += di;
      clampWindow();

      if (chart.yManual) {                        /* only pan price when locked */
        const dv = dy * ((geo.yMax - geo.yMin) / geo.plotH);
        chart.yManual.min += dv; chart.yManual.max += dv;
      }
      markCustom();
      drawChart();
      tip.classList.remove("on");
      return;
    }

    /* crosshair */
    const i = clamp(Math.round(indexAt(ev.clientX)), geo.lo, geo.hi);
    const p = chart.series[i];
    const y = p.value - geo.baseline;
    const svg = host.querySelector("svg");
    if (!svg) return;
    const cross = svg.querySelector("#cross");
    const dot = svg.querySelector("#crossDot");

    cross.setAttribute("x1", geo.px(i)); cross.setAttribute("x2", geo.px(i));
    cross.setAttribute("opacity", "1");
    dot.setAttribute("cx", geo.px(i)); dot.setAttribute("cy", geo.py(y));
    dot.setAttribute("fill", y >= 0 ? GAIN : LOSS);
    dot.setAttribute("opacity", "1");

    const equityAtStart = chart.series.equityBase + geo.baseline;
    tip.innerHTML = "<span class='tt-k'>" + p.long + "</span>" +
      "<span class='tt-v " + tone(y) + "'>" + signedMoney(y) + "</span>" +
      "<span class='tt-row'><span>from view start</span><span>" + signedPct((y / equityAtStart) * 100) + "</span></span>";
    tip.classList.add("on");
    tip.style.left = clamp(geo.px(i), 80, geo.width - 80) + "px";
    tip.style.top = Math.max(52, geo.py(y)) + "px";
  });

  axis.addEventListener("pointermove", ev => {
    if (!drag || drag.mode !== "scale" || !geo) return;
    const dy = ev.clientY - drag.y;
    drag.y = ev.clientY;

    const mid = (chart.yManual.min + chart.yManual.max) / 2;
    const half = (chart.yManual.max - chart.yManual.min) / 2;
    const next = clamp(half * (1 + dy / 180), 1e-3, 1e9);
    chart.yManual = { min: mid - next, max: mid + next };
    markCustom();
    drawChart();
  });

  plot.addEventListener("pointerleave", () => {
    tip.classList.remove("on");
    const svg = host.querySelector("svg");
    if (!svg) return;
    svg.querySelector("#cross").setAttribute("opacity", "0");
    svg.querySelector("#crossDot").setAttribute("opacity", "0");
  });

  /* double-click anywhere on the chart returns to the selected preset */
  for (const el of [plot, axis]) {
    el.addEventListener("dblclick", () => setRange(chart.preset));
  }
}

/* ══ calendar ════════════════════════════════════════════ */



function renderCalendar() {
  const md = monthData(calY, calM);
  const rows = weekRows(md);
  const body = document.getElementById("cal-body");
  const tip = document.getElementById("cal-tip");
  body.replaceChildren();

  const peak = Math.max(1, ...md.days.filter(d => d.pnl !== null).map(d => Math.abs(d.pnl)));

  document.getElementById("cal-month").textContent = MONTHS[calM] + " " + calY;

  const ix = monthIndex(calY, calM);
  document.getElementById("cal-prev").disabled = ix <= FIRST_IX;
  document.getElementById("cal-next").disabled = ix >= LAST_IX;

  document.getElementById("sum-trades").textContent = md.trades ? plainNum(md.trades) : "—";
  document.getElementById("sum-wins").textContent = md.trades ? plainNum(md.wins) : "—";

  const sp = document.getElementById("sum-pnl");
  sp.textContent = md.trades ? signedMoney(md.pnl) : "—";
  sp.className = "v " + tone(md.trades ? md.pnl : 0);

  const sc = document.getElementById("sum-pct");
  sc.textContent = md.trades ? signedPct(md.pct) : "—";
  sc.className = "v " + tone(md.trades ? md.pnl : 0);

  for (const row of rows) {
    const tr = document.createElement("tr");

    for (const cell of row.cells) {
      const td = document.createElement("td");
      td.append(dayCell(cell, peak, tip));
      tr.append(td);
    }

    const totalTd = document.createElement("td");
    const total = document.createElement("div");
    total.className = "cell total " + (row.any ? (row.pnl >= 0 ? "gain" : "loss") : "");
    const dLabel = document.createElement("span");
    dLabel.className = "d";
    dLabel.textContent = "Week";
    const p = document.createElement("span");
    p.className = "p " + (row.any ? tone(row.pnl) : "flat");
    p.textContent = row.any ? signedMoney(row.pnl) : "—";
    const q = document.createElement("span");
    q.className = "q";
    q.textContent = row.any ? signedPct(row.pct) : "";
    total.append(dLabel, p, q);
    totalTd.append(total);
    tr.append(totalTd);

    body.append(tr);
  }
}

function dayCell(cell, peak, tip) {
  const el = document.createElement("div");

  if (!cell) { el.className = "cell out"; return el; }

  const d = document.createElement("span");
  d.className = "d";
  d.textContent = cell.day;
  el.append(d);

  if (cell.closed) {
    el.className = "cell idle";
    const tag = document.createElement("span");
    tag.className = "closed-tag";
    tag.textContent = "Closed";
    el.append(tag);
    el.title = cell.closed + " — market closed";
    return el;
  }

  if (cell.pnl === null) {
    el.className = "cell idle";
    const p = document.createElement("span");
    p.className = "p";
    p.textContent = "—";
    el.append(p);
    return el;
  }

  const positive = cell.pnl >= 0;
  el.className = "cell has " + (positive ? "gain" : "loss");
  if (calY === todaySel.y && calM === todaySel.m && cell.day === todaySel.day) el.classList.add("sel");
  el.tabIndex = 0;
  el.setAttribute("role", "button");

  el.addEventListener("click", () => selectDay(calY, calM, cell.day));
  el.addEventListener("keydown", ev => {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selectDay(calY, calM, cell.day); }
  });

  /* sequential tint within each polarity; the surface is the neutral midpoint */
  const depth = C.tintMin + (Math.abs(cell.pnl) / peak) * (C.tintMax - C.tintMin);
  el.style.background = "color-mix(in oklab, " +
    (positive ? "var(--gain-mark)" : "var(--loss-mark)") + " " +
    (depth * 100).toFixed(1) + "%, var(--surface-2))";

  const p = document.createElement("span");
  p.className = "p " + tone(cell.pnl);
  p.textContent = signedMoney(cell.pnl);

  const q = document.createElement("span");
  q.className = "q";
  q.textContent = signedPct(cell.pct);

  el.append(p, q);

  const show = target => {
    const box = target.getBoundingClientRect();
    const ref = tip.offsetParent.getBoundingClientRect();
    tip.innerHTML =
      "<span class='tt-k'>" + DAY3[cell.weekday] + " " + cell.day + " " + MON3[calM] + " " + calY + "</span>" +
      "<span class='tt-v " + tone(cell.pnl) + "'>" + signedMoney(cell.pnl) + "</span>" +
      "<span class='tt-row'><span>Return</span><span>" + signedPct(cell.pct) + "</span></span>" +
      "<span class='tt-row'><span>Trades</span><span>" + cell.trades + "</span></span>" +
      "<span class='tt-row'><span>Wins</span><span>" + cell.wins + " of " + cell.trades + "</span></span>";
    tip.classList.add("on");
    tip.style.left = clamp(box.left - ref.left + box.width / 2, 76, ref.width - 76) + "px";
    tip.style.top = Math.max(88, box.top - ref.top - 6) + "px";
  };

  const hide = () => {
    tip.classList.remove("on");
    tip.style.left = "0px";
    tip.style.top = "0px";
  };

  el.addEventListener("pointerenter", ev => show(ev.currentTarget));
  el.addEventListener("focus", ev => show(ev.currentTarget));
  el.addEventListener("pointerleave", hide);
  el.addEventListener("blur", hide);

  el.setAttribute("aria-label",
    DAY3[cell.weekday] + " " + cell.day + " " + MON3[calM] + ", " + signedMoney(cell.pnl) +
    ", " + signedPct(cell.pct) + ", " + cell.wins + " of " + cell.trades + " trades won");

  return el;
}

/* ══ portfolio ═══════════════════════════════════════════ */

function renderPortfolio() {
  document.getElementById("pf-value").textContent = money(ACCOUNT.deployed);
  document.getElementById("pf-cash").textContent = money(ACCOUNT.cash);

  const un = document.getElementById("pf-unreal");
  un.textContent = signedMoney(ACCOUNT.unrealised);
  un.className = "v " + tone(ACCOUNT.unrealised);

  document.getElementById("pf-count").textContent = OPEN_POSITIONS.length;
  document.getElementById("pf-exposure").textContent = ACCOUNT.exposurePct.toFixed(1) + "%";
  document.getElementById("pf-largest").textContent = ACCOUNT.largestPositionPct.toFixed(1) + "%";

  document.getElementById("pf-risk").textContent = money(ACCOUNT.buyingPower);

  document.getElementById("pf-cap").innerHTML =
    "<b>" + ACCOUNT.largestPositionPct.toFixed(1) + "%</b> of " + ACCOUNT.positionCapPct.toFixed(1) + "%";
  const cm = document.getElementById("pf-cap-meter");
  cm.style.width = clamp(ACCOUNT.largestPositionPct / ACCOUNT.positionCapPct, 0, 1) * 100 + "%";
  cm.style.background = "var(--ink-3)";

  /* allocation by strategy */
  const alloc = document.getElementById("pf-alloc");
  alloc.replaceChildren();
  for (const st of STRATEGIES) {
    const held = OPEN_POSITIONS.filter(x => x.strategy === st.id);
    if (!held.length) continue;
    const value = held.reduce((a, x) => a + x.value, 0);

    const row = document.createElement("div");
    row.className = "alloc-row";

    const nm = document.createElement("div");
    nm.className = "nm";
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = st.color;
    const label = document.createElement("span");
    label.textContent = st.label;
    const n = document.createElement("span");
    n.className = "eyebrow";
    n.textContent = held.length + (held.length === 1 ? " pos" : " pos");
    nm.append(chip, label, n);

    const amt = document.createElement("div");
    amt.className = "amt";
    amt.innerHTML = money(value) + "<span class='pc'>" + ((value / ACCOUNT.deployed) * 100).toFixed(0) + "%</span>";

    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("i");
    fill.style.width = (value / ACCOUNT.deployed) * 100 + "%";
    fill.style.background = st.color;
    track.append(fill);

    row.append(nm, amt, track);
    alloc.append(row);
  }

  /* every holding against the 10% position cap the bot sizes to */
  const stops = document.getElementById("pf-stops");
  stops.replaceChildren();
  for (const pos of OPEN_POSITIONS) {
    const row = document.createElement("div");
    row.className = "stop-row" + (pos.weight >= ACCOUNT.positionCapPct - 0.2 ? " near" : "");

    const nm = document.createElement("div");
    nm.className = "nm";
    nm.textContent = pos.symbol;

    const gap = document.createElement("div");
    gap.className = "gap";
    gap.textContent = pos.weight.toFixed(1) + "% · " + money(pos.value);

    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("i");
    fill.style.width = clamp(pos.weight / ACCOUNT.positionCapPct, 0.03, 1) * 100 + "%";
    track.append(fill);

    row.append(nm, gap, track);
    stops.append(row);
  }

  document.getElementById("pf-open-note").textContent =
    OPEN_POSITIONS.length + " held · " + money(ACCOUNT.deployed);

  buildTable(document.getElementById("pf-open-table"),
    ["Symbol", "Strategy", "Opened", "Qty", "Entry", "Last", "Value", "Weight", "Unrealised"],
    OPEN_POSITIONS.map(pos => [
      symbolCell(pos.symbol, pos.side),
      stratCell(pos.strategy),
      { t: pos.opened, dim: true },
      { t: String(pos.qty), r: true, dim: true },
      { t: money(pos.entry), r: true },
      { t: money(pos.last), r: true },
      { t: money(pos.value), r: true },
      { t: pos.weight.toFixed(1) + "%", r: true, dim: true },
      { t: signedMoney(pos.unreal) + "  " + signedPct(pos.unrealPct), r: true, cls: tone(pos.unreal) },
    ]), 3);

  /* the session before today */
  const prev = SESSIONS[SESSIONS.length - 2];
  const trades = prev ? tradesByDate.get(prev.date) || [] : [];
  const realised = trades.reduce((a, t) => a + t.pnl, 0);
  const wins = trades.filter(t => t.pnl > 0).length;

  document.getElementById("pf-prev-date").textContent = prev ? prev.long : "—";
  document.getElementById("pf-prev-sum").innerHTML = prev
    ? "Realised <b class='" + tone(realised) + "'>" + signedMoney(realised) + "</b>" +
      "<span><b>" + wins + "</b> of <b>" + trades.length + "</b> won</span>" +
      "<span>Return <b class='" + tone(prev.pct) + "'>" + signedPct(prev.pct) + "</b></span>"
    : "<span>No earlier session yet</span>";

  buildTable(document.getElementById("pf-prev-table"),
    ["Time", "Symbol", "Strategy", "In", "Out", "P&L"],
    trades.map(t => [
      { t: clockLabel(t.minute), dim: true },
      symbolCell(t.symbol, t.side),
      stratCell(t.strategy),
      { t: money(t.entry), r: true },
      { t: money(t.exit), r: true },
      { t: signedMoney(t.pnl), r: true, cls: tone(t.pnl) },
    ]), 3);
}

/* ══ history ═════════════════════════════════════════════ */

function tile(k, v, cls, sub) {
  const el = document.createElement("div");
  el.className = "tile";
  const kk = document.createElement("span");
  kk.className = "k";
  kk.textContent = k;
  const vv = document.createElement("span");
  vv.className = "v " + (cls || "");
  vv.textContent = v;
  el.append(kk, vv);
  if (sub) {
    const ss = document.createElement("span");
    ss.className = "sub";
    ss.textContent = sub;
    el.append(ss);
  }
  return el;
}

function renderHistory() {
  document.getElementById("hs-span").textContent =
    SESSIONS[0].long + " – " + SESSIONS[SESSIONS.length - 1].long;

  const L = LEDGER;
  const tiles = document.getElementById("hs-tiles");
  tiles.replaceChildren(
    tile("Realised P&L", signedMoney(L.net), tone(L.net), "closed round trips"),
    tile("Trades", plainNum(L.n), "", SESSIONS.length + " sessions"),
    tile("Win rate", L.winRate.toFixed(1) + "%", "", L.wins + "W / " + L.losses + "L"),
    tile("Profit factor", L.profitFactor.toFixed(2), L.profitFactor >= 1 ? "pos" : "neg", "gross won ÷ lost"),
    tile("Expectancy", signedMoney(L.expectancy), tone(L.expectancy), "per trade"),
    tile("Average win", signedMoney(L.avgWin), "pos", plainNum(L.wins) + " trades"),
    tile("Average loss", signedMoney(-L.avgLoss), "neg", plainNum(L.losses) + " trades"),
    tile("Payoff ratio", (L.avgWin / L.avgLoss).toFixed(2), "", "avg win ÷ avg loss"),
    tile("Best trade", signedMoney(L.best), "pos"),
    tile("Worst trade", signedMoney(L.worst), "neg"),
  );

  /* monthly bars */
  const peak = Math.max(...SESSIONS.map(m => Math.abs(m.pnl)));
  const strip = document.getElementById("hs-strip");
  strip.replaceChildren();
  for (const m of SESSIONS) {
    const bar = document.createElement("div");
    bar.className = "ybar";
    const track = document.createElement("div");
    track.className = "track";
    const up = document.createElement("div");
    up.className = "up";
    const down = document.createElement("div");
    down.className = "down";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.height = Math.max(2, (Math.abs(m.pnl) / peak) * 100) + "%";
    fill.title = m.long + " · " + signedMoney(m.pnl);
    (m.pnl >= 0 ? up : down).append(fill);
    track.append(up, down);
    const lab = document.createElement("div");
    lab.className = "lab";
    lab.textContent = m.label;
    bar.append(track, lab);
    strip.append(bar);
  }

  buildTable(document.getElementById("hs-months"),
    ["Session", "Trades", "Win rate", "P&L", "Return"],
    [...SESSIONS].reverse().map(m => [
      { t: m.long },
      { t: plainNum(m.trades), r: true, dim: true },
      { t: m.trades ? ((m.wins / m.trades) * 100).toFixed(1) + "%" : "—", r: true, dim: true },
      { t: signedMoney(m.pnl), r: true, cls: tone(m.pnl) },
      { t: signedPct(m.pct), r: true, cls: tone(m.pnl) },
    ]), 1);

  buildTable(document.getElementById("hs-strats"),
    ["Strategy", "Trades", "Win rate", "Factor", "P&L"],
    STRATEGIES.map(st => {
      const st2 = statsFor(ALL_TRADES.filter(t => t.strategy === st.id));
      return [
        stratCell(st.id),
        { t: plainNum(st2.n), r: true, dim: true },
        { t: st2.n ? st2.winRate.toFixed(1) + "%" : "—", r: true, dim: true },
        { t: st2.n ? st2.profitFactor.toFixed(2) : "—", r: true, cls: st2.profitFactor >= 1 ? "pos" : "neg" },
        { t: signedMoney(st2.net), r: true, cls: tone(st2.net) },
      ];
    }), 1);

  /* filter options */
  const fs = document.getElementById("f-strategy");
  if (fs.options.length === 1) {
    for (const st of STRATEGIES) fs.append(new Option(st.label, st.id));
    const fm = document.getElementById("f-month");
    for (const m of [...SESSIONS].reverse()) fm.append(new Option(m.long, m.date));
  }

  renderLog();
}

/* A daily engine can hold for days, so an entry time alone would read as if the
   trade opened and closed in the same session. Name the day when it did not. */
function openedCell(trade) {
  const wrap = document.createElement("span");
  wrap.className = "in-time";
  const clock = document.createElement("span");
  clock.textContent = clockLabel(trade.inMinute);
  wrap.append(clock);
  if (trade.inDate && trade.inDate !== trade.date) {
    const [, m, day] = dparts(trade.inDate);
    const tag = document.createElement("span");
    tag.className = "in-day";
    tag.textContent = day + " " + MON3[m - 1];
    wrap.append(tag);
    wrap.title = "Opened " + day + " " + MON3[m - 1] + ", held to the exit shown";
  }
  return { node: wrap, dim: true };
}

function renderLog() {
  const strategy = document.getElementById("f-strategy").value;
  const side = document.getElementById("f-side").value;
  const result = document.getElementById("f-result").value;
  const month = document.getElementById("f-month").value;
  const symbol = document.getElementById("f-symbol").value.trim().toUpperCase();

  const rows = ALL_TRADES.filter(t =>
    (!strategy || t.strategy === strategy) &&
    (!side || t.side === side) &&
    (!result || (result === "win" ? t.pnl > 0 : t.pnl <= 0)) &&
    (!month || month === t.date) &&
    (!symbol || t.symbol.includes(symbol))
  );

  const st = statsFor(rows);
  document.getElementById("hs-count").textContent = rows.length === ALL_TRADES.length
    ? plainNum(rows.length) + " trades"
    : plainNum(rows.length) + " of " + plainNum(ALL_TRADES.length) + " · " +
      signedMoney(st.net) + " · " + st.winRate.toFixed(1) + "% won";

  const table = document.getElementById("hs-log");
  table.replaceChildren();

  if (!rows.length) {
    table.innerHTML = "<tbody><tr><td class='empty'>No trades match these filters.</td></tr></tbody>";
    return;
  }

  /* Shade every other session so the eye can find where one day ends. Parity is
     counted from the earliest day on show, so the banding reads the same way
     chronologically however the list is filtered, and a day with no trades
     never leaves two shaded sessions touching. */
  const days = [...new Set(rows.map(t => t.date))].sort();
  const shade = rows.map(t => days.indexOf(t.date) % 2 === 1);

  buildTable(table,
    ["Date", "In time", "Out time", "Symbol", "Strategy", "Entry", "Exit", "P&L"],
    rows.map(t => [
      { t: DAY3[t.weekday] + " " + t.day + " " + MON3[t.m] + " " + String(t.y).slice(2), cls: "log-date" },
      openedCell(t),
      { t: clockLabel(t.minute), dim: true },
      symbolCell(t.symbol, t.side),
      stratCell(t.strategy),
      { t: money(t.entry), r: true },
      { t: money(t.exit), r: true },
      { t: signedMoney(t.pnl), r: true, cls: tone(t.pnl) },
    ]), 5, (_row, index) => shade[index] ? "band" : "");
}

/* ══ views ═══════════════════════════════════════════════ */

let currentView = "dashboard";
const viewReady = { dashboard: true, portfolio: false, history: false, strategies: false };

function switchView(name) {
  currentView = name;
  document.body.dataset.view = name;

  for (const b of document.querySelectorAll(".tabs button")) {
    if (b.dataset.view === name) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  for (const id of ["dashboard", "portfolio", "history", "strategies"]) {
    document.getElementById("view-" + id).classList.toggle("hidden", id !== name);
  }

  if (!viewReady[name]) {
    if (name === "portfolio") renderPortfolio();
    if (name === "history") renderHistory();
    if (name === "strategies") renderRules();
    viewReady[name] = true;
  }

  /* the chart measured zero while its panel was hidden */
  if (name === "dashboard") requestAnimationFrame(drawChart);
  window.scrollTo(0, 0);
}


/* ══ rule sheet ══════════════════════════════════════════

   Fetched once when the page is first opened rather than on every poll: the
   rules only change when the service is redeployed. The run-state badges come
   from the live feed, so they keep refreshing with everything else. */

let RULES = null;

function ruleRow(row) {
  const tr = document.createElement("tr");
  const head = document.createElement("th");
  head.scope = "row";
  head.textContent = row.field;
  const cell = document.createElement("td");
  cell.textContent = row.value;
  if (row.source) {
    const src = document.createElement("span");
    src.className = "rule-source";
    src.textContent = row.source;
    cell.append(src);
  }
  tr.append(head, cell);
  return tr;
}

function renderRuleStates() {
  const bot = LIVE.bot || {};
  const warning = document.getElementById("rules-bot");
  if (warning) {
    const down = bot.reported && !bot.running;
    warning.textContent = !bot.reported
      ? "The bot has not reported, so which engines are enabled is unknown."
      : down
        ? "The bot has stopped reporting — the switches below are from its last report."
        : "";
    warning.hidden = !warning.textContent;
  }
  for (const card of document.querySelectorAll("#rules-cards .rule-card")) {
    const id = card.dataset.strategy;
    const host = card.querySelector(".states");
    if (!host) continue;
    host.replaceWith(stateBadges(id));
    card.classList.toggle("is-idle", switchState(id) !== "online");
  }
}

function paintRules() {
  if (!RULES) return;

  const portfolio = document.getElementById("rules-portfolio");
  portfolio.replaceChildren();
  const caption = document.createElement("caption");
  caption.textContent = "Applies to every strategy at once";
  const pbody = document.createElement("tbody");
  for (const row of RULES.portfolio) pbody.append(ruleRow(row));
  portfolio.append(caption, pbody);

  document.getElementById("rules-config").textContent = RULES.configured
    ? "Risk limits as reported by the bot"
    : "Bot not reporting — risk limits shown are the defaults";

  const host = document.getElementById("rules-cards");
  host.replaceChildren();
  for (const strategy of RULES.strategies) {
    const card = document.createElement("section");
    card.className = "panel rule-card";
    card.dataset.strategy = strategy.id;

    const head = document.createElement("div");
    head.className = "panel-head";
    const title = document.createElement("h2");
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = STRATEGY_COLOURS[strategy.id] || "var(--ink-3)";
    const name = document.createElement("span");
    name.textContent = strategy.short;
    title.append(chip, name);
    head.append(title, stateBadges(strategy.id));

    const sub = document.createElement("div");
    sub.className = "rule-sub";
    sub.textContent = strategy.label + " · " + strategy.kind;

    const body = document.createElement("div");
    body.className = "panel-body";
    const table = document.createElement("table");
    table.className = "data rules-table";
    const tbody = document.createElement("tbody");
    for (const row of strategy.rows) tbody.append(ruleRow(row));
    table.append(tbody);
    body.append(table);

    card.append(head, sub, body);
    host.append(card);
  }
  renderRuleStates();
}

async function renderRules() {
  if (RULES) { paintRules(); return; }
  try {
    const response = await fetch("/api/strategies", { credentials: "same-origin" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    RULES = (await response.json()).data;
  } catch (error) {
    document.getElementById("rules-cards").textContent =
      "The rule sheet could not be loaded. Reload the page to try again.";
    return;
  }
  paintRules();
}

/* ══ live feed ═══════════════════════════════════════════ */

let calY = 0, calM = 0, booted = false;

function renderAll() {
  readTheme();
  renderAccount();
  renderPeriodReturns();
  renderStrategies(stratRange);
  renderCalendar();
  renderToday();
  if (viewReady.portfolio) renderPortfolio();
  if (viewReady.history) renderHistory();
  if (viewReady.strategies) renderRuleStates();
}

function markFeed(state, detail) {
  const bar = document.getElementById("status");
  bar.dataset.feed = state;
  if (detail) document.getElementById("st-asof").textContent = detail;
}

async function refresh() {
  try {
    const response = await fetch("/api/ledger", { headers: { Accept: "application/json" } });
    if (response.status === 401) { location.replace("/login"); return; }
    if (!response.ok) throw new Error("read failed (" + response.status + ")");

    const payload = await response.json();
    const first = !booted;
    const keepSelection = todaySel;
    const keepView = chart.custom ? { i0: chart.i0, i1: chart.i1, series: chart.series } : null;

    derive(payload.data);

    if (first || !keepSelection || !tradesByDate.has(
      keepSelection.y + "-" + String(keepSelection.m + 1).padStart(2, "0") + "-" + String(keepSelection.day).padStart(2, "0")
    )) {
      todaySel = { ...LATEST };
      calY = LATEST.y;
      calM = LATEST.m;
    }

    renderAll();

    if (keepView) {
      chart.series = keepView.series === INTRADAY || chart.preset === "D" ? INTRADAY : DAILY;
      chart.i0 = keepView.i0;
      chart.i1 = keepView.i1;
      drawChart();
    } else {
      setRange(chart.preset);
    }

    booted = true;
    markFeed("ok");
  } catch (error) {
    markFeed("error", "feed unavailable — retrying");
  }
}

/* ══ wiring ══════════════════════════════════════════════ */

document.querySelector(".tabs").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (btn && btn.dataset.view) switchView(btn.dataset.view);
});

document.getElementById("chart-range").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (btn) setRange(btn.dataset.range);
});

document.getElementById("strat-range").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  stratRange = btn.dataset.range;
  for (const b of document.querySelectorAll("#strat-range button")) {
    b.setAttribute("aria-pressed", String(b.dataset.range === stratRange));
  }
  renderStrategies(stratRange);
});

document.getElementById("unit-toggle").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  unit = btn.dataset.unit;
  for (const b of document.querySelectorAll("#unit-toggle button")) {
    b.setAttribute("aria-pressed", String(b.dataset.unit === unit));
  }
  renderPeriodReturns();
});

document.getElementById("today-tabs").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  todayTab = btn.dataset.tab;
  for (const b of document.querySelectorAll("#today-tabs button")) {
    b.setAttribute("aria-pressed", String(b.dataset.tab === todayTab));
  }
  renderToday();
});

document.getElementById("today-reset").addEventListener("click", () => {
  selectDay(LATEST.y, LATEST.m, LATEST.day);
  if (calY !== LATEST.y || calM !== LATEST.m) { calY = LATEST.y; calM = LATEST.m; renderCalendar(); }
});

document.getElementById("cal-prev").addEventListener("click", () => {
  if (calM === 0) { calM = 11; calY -= 1; } else calM -= 1;
  renderCalendar();
});

document.getElementById("cal-next").addEventListener("click", () => {
  if (calM === 11) { calM = 0; calY += 1; } else calM += 1;
  renderCalendar();
});

for (const id of ["f-strategy", "f-side", "f-result", "f-month"]) {
  document.getElementById(id).addEventListener("change", renderLog);
}
document.getElementById("f-symbol").addEventListener("input", renderLog);
document.getElementById("f-clear").addEventListener("click", () => {
  for (const id of ["f-strategy", "f-side", "f-result", "f-month"]) document.getElementById(id).value = "";
  document.getElementById("f-symbol").value = "";
  renderLog();
});

function resolvedTheme() {
  return document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function syncThemeButtons() {
  const now = resolvedTheme();
  for (const b of document.querySelectorAll("#theme-toggle button")) {
    b.setAttribute("aria-pressed", String(b.dataset.setTheme === now));
  }
}

function repaintForTheme() {
  readTheme();
  renderCalendar();
  if (currentView === "dashboard") drawChart();
}

document.getElementById("theme-toggle").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  document.documentElement.setAttribute("data-theme", btn.dataset.setTheme);
  try { localStorage.setItem("mt-theme", btn.dataset.setTheme); } catch (error) { /* no-op */ }
  syncThemeButtons();
  repaintForTheme();
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.getAttribute("data-theme")) { syncThemeButtons(); repaintForTheme(); }
});

document.getElementById("logout").addEventListener("click", async () => {
  const session = await fetch("/api/session", { cache: "no-store" });
  const token = session.ok ? (await session.json()).csrf_token : "";
  await fetch("/logout", { method: "POST", headers: { "X-CSRF-Token": token } });
  location.replace("/login");
});

let resizeTimer = 0, lastBox = "";
new ResizeObserver(entries => {
  const r = entries[0].contentRect;
  const key = Math.round(r.width) + "x" + Math.round(r.height);
  if (r.width === 0 || key === lastBox) return;
  lastBox = key;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(drawChart, 80);
}).observe(document.getElementById("chart-host"));

document.body.dataset.view = "dashboard";
syncThemeButtons();
initChartInteraction();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
