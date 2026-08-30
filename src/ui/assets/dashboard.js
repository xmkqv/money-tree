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
/* The Monday a date belongs to, so the log can rule off between trading weeks.
   Sunday is 0 in JS, so shift the index before taking the offset back. */
const mondayOf = d => {
  const at = dateOf(d);
  at.setDate(at.getDate() - ((at.getDay() + 6) % 7));
  return at.getFullYear() + "-" + (at.getMonth() + 1) + "-" + at.getDate();
};

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

  /* Index the same objects ALL_TRADES holds, not fresh copies of the payload:
     the chart identifies a trade by identity when walking the others in its
     stock, and a copy is never found among them. Walked oldest first so each
     day still reads in the order it happened. */
  tradesByDate = new Map();
  for (const t of [...ALL_TRADES].reverse()) {
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

function symbolCell(symbol, side, trade) {
  const wrap = document.createElement("span");
  const sym = document.createElement(trade ? "button" : "span");
  sym.className = "sym";
  sym.textContent = symbol;
  if (trade) {
    sym.type = "button";
    sym.classList.add("linked");
    sym.title = "Chart this trade";
    sym.addEventListener("click", () => openTradeChart(trade, currentView));
  }
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

  const openCharts = new Map(OPEN_POSITIONS.map(pos => [pos.symbol, positionTrade(pos)]));
  buildTable(document.getElementById("pf-open-table"),
    ["Symbol", "Strategy", "Opened", "Qty", "Entry", "Last", "Value", "Weight", "Unrealised"],
    OPEN_POSITIONS.map(pos => [
      symbolCell(pos.symbol, pos.side, openCharts.get(pos.symbol)),
      stratCell(pos.strategy),
      { t: pos.opened, dim: true },
      { t: String(pos.qty), r: true, dim: true },
      { t: money(pos.entry), r: true },
      { t: money(pos.last), r: true },
      { t: money(pos.value), r: true },
      { t: pos.weight.toFixed(1) + "%", r: true, dim: true },
      { t: signedMoney(pos.unreal) + "  " + signedPct(pos.unrealPct), r: true, cls: tone(pos.unreal) },
    ]), 3);

  /* The most recent session that is not today's. Taking the second-to-last
     entry assumed the last one was always today, which only holds while the bot
     has already traded today: on a weekend, a holiday, or before the first fill
     of the session, it left this panel a session behind the trades it was
     meant to be showing. */
  const prev = [...SESSIONS].reverse().find(session => session.date !== LIVE.today);
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
      symbolCell(t.symbol, t.side, t),
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

  /* A heavier rule wherever the list crosses from one trading week into the
     next, so a Friday and the Monday after it are never read as one stretch. */
  const weeks = rows.map(t => mondayOf(t.date));

  buildTable(table,
    ["Date", "In time", "Out time", "Symbol", "Strategy", "Entry", "Exit", "P&L"],
    rows.map(t => [
      { t: DAY3[t.weekday] + " " + t.day + " " + MON3[t.m] + " " + String(t.y).slice(2), cls: "log-date" },
      openedCell(t),
      { t: clockLabel(t.minute), dim: true },
      symbolCell(t.symbol, t.side, t),
      stratCell(t.strategy),
      { t: money(t.entry), r: true },
      { t: money(t.exit), r: true },
      { t: signedMoney(t.pnl), r: true, cls: tone(t.pnl) },
    ]), 5, (_row, index) => [
      shade[index] ? "band" : "",
      index && weeks[index] !== weeks[index - 1] ? "week-edge" : "",
    ].filter(Boolean).join(" "));
}


/* ══ trade chart ═════════════════════════════════════════

   Opened from a symbol in the trade log, so it always answers one question:
   what did this stock do around the trade the bot took? The trade is the
   subject — the candles are context, the entry and exit are the marks that
   matter, and the line between them carries the result. */

const TC_BARS = { "5Min": "5 min", "1Hour": "1 hour", "1Day": "Day" };
let TRADE = null, TC_STATE = { bar: "5Min", bars: null, hover: null };
let TC_LEVELS = null, TC_SIBLINGS = [];
/* i0/i1 index the drawn bars and may be fractional; yManual locks the price
   scale once it has been stretched by hand. custom means the reader has moved
   the view, after which the level lines no longer drag the scale open. */
let TC_VIEW = { i0: 0, i1: 0, yManual: null, custom: false };
let TC_ORIGIN = "history";

/* Three lengths of the same measure, so they read as one family; validated for
   colour-vision separation against both surfaces, and each line is labelled at
   its right end so the colour is never the only way to tell them apart. */
const SMA_SET = [
  { length: 20, token: "--s-orb5" },
  { length: 50, token: "--s-orb10" },
  { length: 200, token: "--s-tfb50" },
];
const TC_SHOW = { sma20: false, sma50: false, sma200: false, range: true, stop: true, targets: true };

function clockOf(iso) {
  const at = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(at);
}

function monthOf(iso) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", month: "short", year: "numeric",
  }).format(new Date(iso));
}

function weekdayOf(iso) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", weekday: "short",
  }).format(new Date(iso));
}

function dayOf(iso) {
  const at = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", day: "numeric", month: "short",
  }).formatToParts(at);
  return parts.filter(p => p.type !== "literal").map(p => p.value).join(" ");
}

/* Exchange-time minutes since the epoch, so a bar and a fill can be compared
   on one axis without either being read in the viewer's own timezone. */
function stampOf(dateISO, minute) {
  return Date.parse(dateISO + "T00:00:00Z") / 60000 + minute;
}

function barStamp(iso) {
  const at = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(at);
  const get = t => parts.find(p => p.type === t).value;
  return stampOf(`${get("year")}-${get("month")}-${get("day")}`,
    Number(get("hour")) * 60 + Number(get("minute")));
}

/* A held position charted like a closed one, with the current price standing in
   for an exit that has not happened. Marked open so the page says "Now" rather
   than "Exit" and reports the gain as unrealised. Positions the fill history
   does not reach back far enough to match have no entry to place, and stay
   unlinked rather than being charted from a guess. */
function positionTrade(position) {
  if (!position.inDate) return null;
  return {
    symbol: position.symbol,
    side: position.side,
    strategy: position.strategy,
    entry: position.entry,
    exit: position.last,
    pnl: position.unreal,
    qty: position.qty,
    inDate: position.inDate,
    inMinute: position.inMinute,
    date: LIVE.today,
    minute: tradingMinutes(),
    heldMin: Math.max(0,
      (Date.parse(LIVE.today + "T00:00:00Z") / 60000 + tradingMinutes()) -
      (Date.parse(position.inDate + "T00:00:00Z") / 60000 + position.inMinute)),
    fills: position.fills || [],
    open: true,
  };
}

async function openTradeChart(trade, from) {
  TRADE = trade;
  /* charts open from three tables now, so remember which one to go back to
     rather than always landing on History */
  if (from) TC_ORIGIN = from;
  TC_LEVELS = null;
  TC_STATE = { bar: "5Min", bars: null, hover: null };
  /* the bot's other trades in this stock, oldest first, for the stepper */
  TC_SIBLINGS = ALL_TRADES.filter(t => t.symbol === trade.symbol).slice().reverse();
  /* the held position is not in the closed-trade list, but it is the latest
     thing that happened in this stock, so it belongs at the end of the walk */
  if (trade.open) TC_SIBLINGS.push(trade);
  for (const b of document.querySelectorAll("#tc-range button"))
    b.setAttribute("aria-pressed", String(b.dataset.bar === "5Min"));
  document.getElementById("chart-back").textContent =
    TC_ORIGIN === "portfolio" ? "← Portfolio" : "← Trade log";
  switchView("chart");
  paintTradeFacts();
  paintRail();
  paintStepper();
  loadTradeLevels();
  await loadTradeBars();
}

/* Fetched once per trade rather than once per bar size, so switching between
   five minutes and a day costs nothing and the levels stay put. */
async function loadTradeLevels() {
  const t = TRADE;
  if (t.strategy === "unattributed") { TC_LEVELS = {}; paintRail(); return; }
  const query = new URLSearchParams({
    symbol: t.symbol, strategy: t.strategy, side: t.side, entry: String(t.entry), opened: t.inDate,
  });
  try {
    const response = await fetch("/api/levels?" + query, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("HTTP " + response.status);
    TC_LEVELS = (await response.json()).data;
  } catch {
    TC_LEVELS = {};
  }
  paintRail();
  if (TC_STATE.bars) drawTradeChart();
}

function paintStepper() {
  const index = TC_SIBLINGS.findIndex(t => t === TRADE);
  /* only worth showing when the bot traded this stock more than once */
  document.getElementById("tc-step").hidden = TC_SIBLINGS.length < 2;
  document.getElementById("tc-count").textContent = (index + 1) + " of " + TC_SIBLINGS.length;
  document.getElementById("tc-prev").disabled = index <= 0;
  document.getElementById("tc-next").disabled = index < 0 || index >= TC_SIBLINGS.length - 1;
}

function stepTrade(by) {
  const index = TC_SIBLINGS.findIndex(t => t === TRADE) + by;
  if (index < 0 || index >= TC_SIBLINGS.length) return;
  openTradeChart(TC_SIBLINGS[index]);
}

/* Averages are computed on the bars on screen, so a 200-period line needs 200
   bars behind the first one drawn — that is what the run-up in the window is
   for. Where the data still falls short the toggle says so rather than
   silently drawing nothing. */
function movingAverage(bars, length) {
  const out = new Array(bars.length).fill(null);
  let total = 0;
  for (let i = 0; i < bars.length; i++) {
    total += bars[i].c;
    if (i >= length) total -= bars[i - length].c;
    if (i >= length - 1) out[i] = total / length;
  }
  return out;
}

function paintRail() {
  const host = document.getElementById("tc-smas");
  host.replaceChildren();
  const bars = TC_STATE.bars || [];
  for (const { length, token } of SMA_SET) {
    const key = "sma" + length;
    const enough = bars.length >= length;
    host.append(railToggle(key, "SMA " + length, token, enough,
      enough ? "" : "Not enough bars at this size"));
  }

  const levels = document.getElementById("tc-overlays");
  levels.replaceChildren();
  const has = TC_LEVELS || {};
  levels.append(
    railToggle("range", "Opening range", null, Boolean(has.range), has.range ? "" : "ORB trades only"),
    railToggle("stop", "Stop", null, has.stop !== undefined, has.stop !== undefined ? "" : "Not reconstructable"),
    railToggle("targets", "Targets", null, Boolean(has.targets), has.targets ? "" : "ORB trades only"),
  );
  document.getElementById("tc-rail-note").textContent =
    has.reconstructed ? "Stop and targets are reconstructed from the rules." : "";
}

function railToggle(key, label, token, enabled, why) {
  const row = document.createElement("label");
  row.className = "tc-toggle" + (enabled ? "" : " off");
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = enabled && TC_SHOW[key];
  box.disabled = !enabled;
  box.addEventListener("change", () => { TC_SHOW[key] = box.checked; drawTradeChart(); });
  const swatch = document.createElement("span");
  swatch.className = "tc-swatch";
  if (token) swatch.style.background = tokenValue(token);
  else swatch.classList.add("plain");
  const text = document.createElement("span");
  text.textContent = label;
  row.append(box, swatch, text);
  if (why) row.title = why;
  return row;
}

function tokenValue(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function paintTradeFacts() {
  const t = TRADE;
  document.getElementById("tc-title").textContent = t.symbol;
  const strategy = STRAT_BY_ID[t.strategy];
  document.getElementById("tc-sub").textContent =
    (strategy ? strategy.label : t.strategy) + " · " + (t.side === "short" ? "Short" : "Long") +
    (t.open ? " · Open" : "");

  /* said as its own line, so the standing caveats below are not overwritten */
  const openNote = document.getElementById("tc-open-note");
  openNote.textContent = t.open
    ? "This position is still open. The second mark is the current price, not an exit, and "
      + "the figure beside it is unrealised."
    : "";
  openNote.hidden = !t.open;

  const held = t.heldMin >= 1440
    ? Math.round(t.heldMin / 1440) + "d"
    : t.heldMin >= 60 ? Math.floor(t.heldMin / 60) + "h " + (t.heldMin % 60) + "m" : t.heldMin + "m";

  const facts = [
    ["Entry", money(t.entry), dayOf2(t.inDate) + " " + clockLabel(t.inMinute)],
    [t.open ? "Last" : "Exit", money(t.exit),
      t.open ? "still open" : dayOf2(t.date) + " " + clockLabel(t.minute)],
    ["Quantity", plainNum(Math.round(t.qty * 100) / 100), ""],
    [t.open ? "Held so far" : "Held", held, ""],
    [t.open ? "Unrealised" : "P&L", signedMoney(t.pnl),
      signedPct(((t.exit - t.entry) / t.entry) * 100 * (t.side === "short" ? -1 : 1))],
  ];
  const host = document.getElementById("tc-facts");
  host.replaceChildren();
  for (const [label, value, sub] of facts) {
    const cell = document.createElement("div");
    cell.className = "fact";
    const k = document.createElement("span");
    k.className = "k";
    k.textContent = label;
    const v = document.createElement("span");
    v.className = "v num" + (label === "P&L" ? " " + tone(t.pnl) : "");
    v.textContent = value;
    cell.append(k, v);
    if (sub) {
      const s = document.createElement("span");
      s.className = "s";
      s.textContent = sub;
      cell.append(s);
    }
    host.append(cell);
  }
}

function dayOf2(iso) {
  const [, m, d] = dparts(iso);
  return d + " " + MON3[m - 1];
}

function tcState(message) {
  const el = document.getElementById("tc-state");
  el.textContent = message || "";
  el.hidden = !message;
}

async function loadTradeBars() {
  const t = TRADE;
  tcState("Loading " + TC_BARS[TC_STATE.bar].toLowerCase() + " bars…");
  document.getElementById("tc-host").querySelectorAll("svg").forEach(n => n.remove());
  const query = new URLSearchParams({
    symbol: t.symbol, timeframe: TC_STATE.bar, opened: t.inDate, closed: t.date,
  });
  try {
    const response = await fetch("/api/bars?" + query, { headers: { Accept: "application/json" } });
    if (response.status === 401) { location.replace("/login"); return; }
    if (!response.ok) throw new Error("HTTP " + response.status);
    const payload = await response.json();
    TC_STATE.bars = payload.data.bars.map(b => ({ ...b, x: barStamp(b.t) }));
    /* bars before this are run-up for the averages, not part of the picture */
    const from = barStamp(payload.data.displayFrom);
    TC_STATE.first = Math.max(0, TC_STATE.bars.findIndex(b => b.x >= from));
  } catch (error) {
    TC_STATE.bars = null;
    tcState("Market data could not be read. Try again in a moment.");
    return;
  }
  if (!TC_STATE.bars.length) {
    tcState("No bars for this window. The IEX feed may not have quoted this stock then.");
    return;
  }
  tcState("");
  TC_VIEW = { i0: 0, i1: Math.max(1, TC_STATE.bars.length - TC_STATE.first), yManual: null, custom: false };
  paintRail();
  drawTradeChart();
}

const TC_PAD = { l: 10, r: 62, t: 16, b: 40 };

function drawTradeChart() {
  const host = document.getElementById("tc-host");
  const bars = TC_STATE.bars;
  if (!bars || !bars.length) return;
  const width = host.clientWidth, height = host.clientHeight;
  if (width < 80 || height < 80) return;
  readTheme();

  const t = TRADE;
  const plotW = width - TC_PAD.l - TC_PAD.r, plotH = height - TC_PAD.t - TC_PAD.b;

  /* Averages need the run-up bars; everything else works on the drawn window. */
  const averages = {};
  for (const { length } of SMA_SET) {
    if (TC_SHOW["sma" + length] && bars.length >= length) {
      averages[length] = movingAverage(bars, length);
    }
  }
  const first = TC_STATE.first || 0;
  const all = bars.slice(first);
  if (!all.length) return;
  if (TC_VIEW.i1 <= TC_VIEW.i0) TC_VIEW = { i0: 0, i1: all.length, yManual: null, custom: false };

  /* Bars are drawn on their index, not their clock, so overnight gaps and the
     lunch lull do not open dead space across the plot. */
  const nearest = x => {
    let best = 0, gap = Infinity;
    all.forEach((b, i) => { const d = Math.abs(b.x - x); if (d < gap) { gap = d; best = i; } });
    return best;
  };
  const inIndex = nearest(stampOf(t.inDate, t.inMinute));
  const outIndex = nearest(stampOf(t.date, t.minute));

  const i0 = TC_VIEW.i0, i1 = TC_VIEW.i1;
  const lo = clamp(Math.floor(i0), 0, all.length - 1);
  const hi = clamp(Math.ceil(i1), 0, all.length - 1);
  const shown = all.slice(lo, hi + 1);

  const levels = TC_LEVELS || {};
  /* The levels open the scale far enough to see them, but only until the reader
     takes hold of it — after that the view is theirs and nothing widens it. */
  const extra = [];
  if (!TC_VIEW.custom) {
    extra.push(t.entry, t.exit);
    if (TC_SHOW.range && levels.range) extra.push(levels.range.high, levels.range.low);
    if (TC_SHOW.stop && levels.stop !== undefined) extra.push(levels.stop);
    if (TC_SHOW.targets && levels.targets) extra.push(...levels.targets);
  }
  for (const values of Object.values(averages)) {
    for (let i = lo; i <= hi; i++) {
      const v = values[i + first];
      if (v !== null && v !== undefined) extra.push(v);
    }
  }

  let yMin, yMax;
  if (TC_VIEW.yManual) {
    yMin = TC_VIEW.yManual.min; yMax = TC_VIEW.yManual.max;
  } else {
    yMin = Math.min(...shown.map(b => b.l), ...extra);
    yMax = Math.max(...shown.map(b => b.h), ...extra);
    const pad = ((yMax - yMin) || Math.max(yMax * 0.01, 0.01)) * 0.10;
    yMin -= pad; yMax += pad;
  }

  const step = plotW / (i1 - i0);
  const px = i => TC_PAD.l + (i - i0 + 0.5) * step;
  const py = v => TC_PAD.t + (1 - (v - yMin) / (yMax - yMin)) * plotH;
  const indexAt = clientX => {
    const rect = document.getElementById("tc-host").getBoundingClientRect();
    return i0 + (clientX - rect.left - TC_PAD.l) / step - 0.5;
  };
  TC_STATE.geo = {
    px, py, step, width, height, inIndex, outIndex, shown: all,
    lo, hi, yMin, yMax, plotW, plotH, indexAt, count: all.length,
  };

  const ticks = [];
  const gridStep = niceStep((yMax - yMin) / 4.2);
  for (let v = Math.ceil(yMin / gridStep) * gridStep; v <= yMax; v += gridStep) ticks.push(v);
  const grid = ticks.map(v =>
    '<line x1="' + TC_PAD.l + '" y1="' + py(v).toFixed(2) + '" x2="' + (width - TC_PAD.r) +
    '" y2="' + py(v).toFixed(2) + '" stroke="' + C.grid + '" stroke-width="1"/>' +
    '<text x="' + (width - TC_PAD.r + 8) + '" y="' + (py(v) + 3.5).toFixed(2) + '" fill="' + C.axis +
    '" font-size="10" font-family="Roboto Mono, monospace">' + money(v) + "</text>").join("");

  /* The axis carries as much date as it has room for and no more. On a daily
     chart zoomed out to a year, a label per session is thousands of characters
     in the space of a few hundred, so the grain steps back to the month; on an
     intraday chart the day is named where the date turns over and the rest
     carry the time. Either way the number of labels is decided by the width
     available, not by the number of bars, which is what let them pile up. */
  const LABEL_WIDTH = 78;
  const roomFor = Math.max(2, Math.floor(plotW / LABEL_WIDTH));

  const firstOf = key => {
    const seen = new Map();
    shown.forEach((b, k) => { const at = key(b.t); if (!seen.has(at)) seen.set(at, k + lo); });
    return seen;
  };
  const daily = TC_STATE.bar === "1Day";
  const byDay = firstOf(dayOf);
  const byMonth = firstOf(monthOf);
  /* on a daily chart every bar is its own day, so the month is the next grain up */
  const byMonths = daily && byDay.size > roomFor;
  const anchors = byMonths ? byMonth : byDay;

  /* still too many? keep every nth, so the ones that remain stay evenly spread */
  const keep = Math.max(1, Math.ceil(anchors.size / roomFor));
  const labelled = new Map();
  [...anchors.entries()].forEach(([text, index], n) => {
    if (n % keep === 0) labelled.set(index, text);
  });
  const boundary = new Set(anchors.values());

  /* Times are placed inside each day, never by one stride across the whole
     window: with seven bars to a session, a global stride walks backwards
     through the time of day and the axis reads 15:30, 14:30, 13:30, each from
     a different session and none of them saying so. Where there is not room
     for a few times within a day, the day markers carry the axis alone. */
  const dayIndexes = [...byDay.values()].sort((a, b) => a - b);
  const perDay = dayIndexes.length ? roomFor / dayIndexes.length : roomFor;
  const timesPerDay = daily ? 0 : Math.max(0, Math.floor(perDay) - 1);

  const candidates = [];
  const push = (i, named) => {
    const b = shown[i - lo];
    if (!b) return;
    candidates.push({
      i, named,
      lines: named
        ? (byMonths ? [monthOf(b.t)]
          : daily ? [weekdayOf(b.t) + " " + dayOf(b.t)]
          : [weekdayOf(b.t) + " " + dayOf(b.t), clockOf(b.t)])
        : [clockOf(b.t)],
    });
  };

  dayIndexes.forEach((from, n) => {
    const to = n + 1 < dayIndexes.length ? dayIndexes[n + 1] - 1 : hi;
    if (labelled.has(from)) push(from, true);
    if (timesPerDay < 2) return;
    const step = (to - from) / (timesPerDay + 1);
    if (step < 1) return;
    for (let slot = 1; slot <= timesPerDay; slot++) {
      const at = Math.round(from + step * slot);
      if (at > from && at <= to) push(at, false);
    }
  });
  candidates.sort((a, b) => a.i - b.i);

  const CHAR = 6.1, GAP = 10;          /* Roboto Mono advance at 10px, and air */
  const kept = [];
  for (const candidate of candidates) {
    const half = Math.max(...candidate.lines.map(line => line.length)) * CHAR / 2;
    const natural = px(candidate.i);
    candidate.x = clamp(natural, TC_PAD.l + half, width - TC_PAD.r - half);
    candidate.left = candidate.x - half;
    candidate.right = candidate.x + half;
    candidate.clamped = Math.abs(candidate.x - natural) > 0.5;
    const previous = kept[kept.length - 1];
    if (!previous || candidate.left >= previous.right + GAP) { kept.push(candidate); continue; }
    /* they collide: the one shoved onto the plot by the clamp is the one whose
       real position is off it, so it gives way to the one that belongs here */
    if (previous.clamped && !candidate.clamped) kept[kept.length - 1] = candidate;
    else if (previous.clamped && candidate.clamped) kept[kept.length - 1] = candidate;
  }

  const rules = shown.map((b, k) => {
    const i = k + lo;
    return boundary.has(i) && i > lo
      ? '<line x1="' + px(i - 0.5).toFixed(2) + '" y1="' + TC_PAD.t + '" x2="' + px(i - 0.5).toFixed(2) +
        '" y2="' + (TC_PAD.t + plotH) + '" stroke="' + C.grid + '" stroke-width="1"/>'
      : "";
  }).join("");

  const axis = rules + kept.map(candidate =>
    candidate.lines.map((line, row) =>
      '<text x="' + candidate.x.toFixed(2) + '" y="' + (height - 15 + row * 11) + '" fill="' + C.axis +
      '" font-size="10" text-anchor="middle" font-family="Roboto Mono, monospace"' +
      (candidate.named ? ' font-weight="600"' : "") + ">" + line + "</text>").join("")
  ).join("");

  /* One line per length, each labelled at its right end. */
  const smaEnds = [];
  const smaLines = SMA_SET.map(({ length, token }) => {
    const values = averages[length];
    if (!values) return "";
    const colour = tokenValue(token);
    let path = "", lastY = null;
    shown.forEach((_, k) => {
      const i = k + lo;
      const v = values[i + first];
      if (v === null || v === undefined) return;
      path += (path ? "L" : "M") + px(i).toFixed(2) + " " + py(v).toFixed(2) + " ";
      lastY = py(v);
    });
    if (!path) return "";
    if (lastY !== null) smaEnds.push({ y: lastY, colour, length });
    return '<path d="' + path.trim() + '" fill="none" stroke="' + colour +
      '" stroke-width="1.5" stroke-linejoin="round" opacity="0.95"/>';
  }).join("");

  /* three averages can converge; nudge their end labels apart so all read */
  smaEnds.sort((a, b) => a.y - b.y);
  smaEnds.forEach((end, i) => {
    if (i && end.y - smaEnds[i - 1].y < 12) end.y = smaEnds[i - 1].y + 12;
  });
  const smaLabels = smaEnds.map(end =>
    '<text x="' + (width - TC_PAD.r - 4) + '" y="' + (end.y - 3).toFixed(2) + '" fill="' + end.colour +
    '" font-size="10" text-anchor="end" font-weight="600" paint-order="stroke" stroke="' + C.ring +
    '" stroke-width="3" stroke-linejoin="round" font-family="Roboto Mono, monospace">' +
    end.length + "</text>").join("");

  /* The levels the strategy's rules put on this trade. */
  const band = (top, bottom, colour) =>
    '<rect x="' + TC_PAD.l + '" y="' + Math.min(top, bottom).toFixed(2) + '" width="' + plotW +
    '" height="' + Math.abs(bottom - top).toFixed(2) + '" fill="' + colour + '" opacity="0.07"/>';
  /* Lines go under the price action so the candles stay legible; their labels
     go over everything, with a plate behind, or a wick crosses out the text. */
  let overlays = "", overlayText = "";
  const named = (y, colour, text, dash) => {
    overlays +=
      '<line x1="' + TC_PAD.l + '" y1="' + y.toFixed(2) + '" x2="' + (width - TC_PAD.r) + '" y2="' + y.toFixed(2) +
      '" stroke="' + colour + '" stroke-width="1" stroke-dasharray="' + dash + '" opacity="0.72"/>';
    overlayText +=
      '<text x="' + (TC_PAD.l + 5) + '" y="' + (y - 4).toFixed(2) + '" fill="' + colour +
      '" font-size="9.5" font-family="Roboto Mono, monospace" letter-spacing="0.04em" ' +
      'paint-order="stroke" stroke="' + C.ring + '" stroke-width="3" stroke-linejoin="round">' +
      text + "</text>";
  };

  if (TC_SHOW.range && levels.range) {
    overlays += band(py(levels.range.high), py(levels.range.low), C.axis);
    named(py(levels.range.high), C.axis, "RANGE HIGH " + money(levels.range.high), "4 3");
    named(py(levels.range.low), C.axis, "RANGE LOW " + money(levels.range.low), "4 3");
  }
  if (TC_SHOW.stop && levels.stop !== undefined) {
    named(py(levels.stop), LOSS, "STOP " + money(levels.stop), "5 4");
  }
  if (TC_SHOW.targets && levels.targets) {
    levels.targets.forEach((value, i) => {
      named(py(value), GAIN, "TARGET " + (i + 1) + " " + money(value), "1 4");
    });
  }

  /* Candles carry direction by shape as well as hue: a body drawn from open to
     close is up or down whichever way the colour reads. */
  const bodyW = Math.max(1.5, Math.min(9, step * 0.62));
  const candles = shown.map((b, k) => {
    const i = k + lo;
    const up = b.c >= b.o;
    const colour = up ? GAIN : LOSS;
    const x = px(i);
    const top = py(Math.max(b.o, b.c)), bottom = py(Math.min(b.o, b.c));
    const h = Math.max(1, bottom - top);
    return '<line x1="' + x.toFixed(2) + '" y1="' + py(b.h).toFixed(2) + '" x2="' + x.toFixed(2) +
      '" y2="' + py(b.l).toFixed(2) + '" stroke="' + colour + '" stroke-width="1"/>' +
      '<rect x="' + (x - bodyW / 2).toFixed(2) + '" y="' + top.toFixed(2) + '" width="' + bodyW.toFixed(2) +
      '" height="' + h.toFixed(2) + '" fill="' + (up ? colour : colour) + '" opacity="' + (up ? 0.9 : 1) + '"/>';
  }).join("");

  /* The trend line is the trade's own result: entry to exit, coloured by which
     way it went, so the direction is readable before any number is. */
  const tone2 = t.pnl >= 0 ? GAIN : LOSS;
  const x1 = px(inIndex), y1 = py(t.entry), x2 = px(outIndex), y2 = py(t.exit);
  const trend =
    '<line x1="' + x1.toFixed(2) + '" y1="' + y1.toFixed(2) + '" x2="' + x2.toFixed(2) + '" y2="' + y2.toFixed(2) +
    '" stroke="' + tone2 + '" stroke-width="2" stroke-linecap="round" stroke-dasharray="6 4" opacity="0.95"/>';

  const level = (y, colour) =>
    '<line x1="' + TC_PAD.l + '" y1="' + y.toFixed(2) + '" x2="' + (width - TC_PAD.r) + '" y2="' + y.toFixed(2) +
    '" stroke="' + colour + '" stroke-width="1" stroke-dasharray="2 5" opacity="0.5"/>';

  /* Shape separates the two ends, colour reports the result: a hollow ring
     starts the trade, a filled dot closes it in the tone the line carries. So
     neither end depends on telling one colour from another to be identified. */
  const entryMark =
    '<circle cx="' + x1.toFixed(2) + '" cy="' + y1.toFixed(2) + '" r="5.5" fill="' + C.ring +
    '" stroke="' + C.axis + '" stroke-width="2.5"/>';
  const exitMark =
    '<circle cx="' + x2.toFixed(2) + '" cy="' + y2.toFixed(2) + '" r="6" fill="' + tone2 +
    '" stroke="' + C.ring + '" stroke-width="2"/>';

  /* Every execution, not just the two averages. A scaled-out ORB position left
     three exits at three prices; one averaged dot hides that entirely. The
     averages stay as the larger marks, these are the smaller ticks behind. */
  const fillMarks = (t.fills || []).map(f => {
    const i = nearest(stampOf(f.d, f.m));
    const x = px(i), y = py(f.p);
    return '<rect x="' + (x - 3.5).toFixed(2) + '" y="' + (y - 3.5).toFixed(2) +
      '" width="7" height="7" rx="1.5" transform="rotate(45 ' + x.toFixed(2) + " " + y.toFixed(2) +
      ')" fill="' + (f.s === "in" ? C.ring : tone2) + '" stroke="' + (f.s === "in" ? C.axis : tone2) +
      '" stroke-width="1.5" opacity="0.9"/>';
  }).join("");

  /* Everything that moves with the view is clipped to the plot, or panning
     would run candles out over the price axis and the dates below. */
  const plotted =
    overlays + candles + smaLines +
    level(y1, C.axis) + level(y2, C.axis) + trend + fillMarks + entryMark + exitMark;

  host.querySelectorAll("svg").forEach(n => n.remove());
  host.insertAdjacentHTML("afterbegin",
    '<svg viewBox="0 0 ' + width + " " + height + '" preserveAspectRatio="none" role="img" ' +
    'aria-label="' + t.symbol + " price around the trade, entry " + money(t.entry) +
    (t.open ? " and last " : " and exit ") + money(t.exit) + '">' +
    '<defs><clipPath id="tcClip"><rect x="' + TC_PAD.l + '" y="' + TC_PAD.t +
    '" width="' + plotW + '" height="' + plotH + '"/></clipPath></defs>' +
    grid + axis +
    '<g clip-path="url(#tcClip)">' + plotted + "</g>" +
    smaLabels + overlayText +
    "</svg>");

  /* size the hover target from the same padding, so it cannot drift from it */
  const hit = document.getElementById("tc-hit");
  hit.style.left = TC_PAD.l + "px";
  hit.style.top = TC_PAD.t + "px";
  hit.style.width = plotW + "px";
  hit.style.height = plotH + "px";
  const axisHit = document.getElementById("tc-axis-hit");
  axisHit.style.left = (width - TC_PAD.r) + "px";
  axisHit.style.top = TC_PAD.t + "px";
  axisHit.style.width = TC_PAD.r + "px";
  axisHit.style.height = plotH + "px";

  paintTradeLabels(x1, y1, x2, y2, width, inIndex >= i0 && inIndex <= i1,
    outIndex >= i0 && outIndex <= i1);
  paintTradeTable();
}

/* The two marks are labelled on the plot rather than in a legend: there are only
   two, and each carries a price and the strategy that placed it. */
function paintTradeLabels(x1, y1, x2, y2, width, entryInView, exitInView) {
  const result = TRADE.pnl >= 0 ? GAIN : LOSS;
  const host = document.getElementById("tc-host");
  host.querySelectorAll(".tc-mark").forEach(n => n.remove());
  const strategy = STRAT_BY_ID[TRADE.strategy];
  const place = (x, y, title, price, cls) => {
    const el = document.createElement("div");
    el.className = "tc-mark " + cls;
    const head = document.createElement("span");
    head.className = "tc-k";
    head.textContent = title;
    const val = document.createElement("span");
    val.className = "tc-v num";
    val.textContent = money(price);
    const who = document.createElement("span");
    who.className = "tc-s";
    who.textContent = strategy ? strategy.label : TRADE.strategy;
    el.append(head, val, who);
    el.style.left = Math.round(x) + "px";
    el.style.top = Math.round(y) + "px";
    /* the exit edge reports the result, so it cannot be a fixed colour */
    el.style.borderLeftColor = cls === "exit" ? result : "var(--ink-3)";
    if (x > width * 0.6) el.classList.add("flip");
    host.append(el);
  };
  if (entryInView) place(x1, y1, "Entry", TRADE.entry, "entry");
  if (exitInView) place(x2, y2, TRADE.open ? "Now" : "Exit", TRADE.exit, "exit");
  separateMarks(host);
}

/* On a daily chart an intraday trade opens and closes on the same candle, so
   the two cards land on top of each other. Push them apart along the price
   axis, keeping the higher price above, rather than letting one hide the other. */
function separateMarks(host) {
  const [a, b] = [...host.querySelectorAll(".tc-mark")];
  if (!a || !b) return;
  const boxA = a.getBoundingClientRect(), boxB = b.getBoundingClientRect();
  const overlapY = Math.min(boxA.bottom, boxB.bottom) - Math.max(boxA.top, boxB.top);
  const overlapX = Math.min(boxA.right, boxB.right) - Math.max(boxA.left, boxB.left);
  if (overlapY <= 0 || overlapX <= 0) return;
  const shift = (overlapY + 8) / 2;
  const upper = TRADE.entry >= TRADE.exit ? a : b;
  const lower = upper === a ? b : a;
  upper.style.marginTop = -shift + "px";
  lower.style.marginTop = shift + "px";
}

function paintTradeTable() {
  const rows = TC_STATE.bars.map(b =>
    `${dayOf(b.t)} ${clockOf(b.t)} open ${money(b.o)} high ${money(b.h)} low ${money(b.l)} close ${money(b.c)}`);
  document.getElementById("tc-table").textContent =
    TRADE.symbol + " " + TC_BARS[TC_STATE.bar] + " bars. " + rows.join(". ");
}

function tradeHover(event) {
  const geo = TC_STATE.geo;
  const tip = document.getElementById("tc-tip");
  if (!geo) return;
  /* the drawn window, not TC_STATE.bars — that still carries the run-up bars
     the averages need, and reading the cursor against those reports a bar from
     days before the one under the pointer */
  const bars = geo.shown;
  const index = clamp(Math.round(geo.indexAt(event.clientX)), geo.lo, geo.hi);
  const b = bars[index];
  if (!b) return;
  const row = (label, value) =>
    '<span class="tt-row"><span>' + label + "</span><span>" + money(value) + "</span></span>";
  tip.innerHTML =
    '<span class="tt-k">' + dayOf(b.t) + " " + clockOf(b.t) + "</span>" +
    '<span class="tt-v">' + money(b.c) + "</span>" +
    row("Open", b.o) + row("High", b.h) + row("Low", b.l);
  tip.style.left = clamp(geo.px(index), 70, geo.width - 70) + "px";
  tip.style.top = clamp(geo.py(b.h) - 12, 8, geo.height - 40) + "px";
  tip.classList.add("on");
}

function wireTradeChart() {
  document.getElementById("chart-back").addEventListener("click", () => switchView(TC_ORIGIN));
  document.getElementById("tc-prev").addEventListener("click", () => stepTrade(-1));
  document.getElementById("tc-next").addEventListener("click", () => stepTrade(1));
  document.getElementById("tc-range").addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button || button.dataset.bar === TC_STATE.bar) return;
    TC_STATE.bar = button.dataset.bar;
    for (const b of document.querySelectorAll("#tc-range button"))
      b.setAttribute("aria-pressed", String(b === button));
    loadTradeBars();
  });
  const hit = document.getElementById("tc-hit");
  const axis = document.getElementById("tc-axis-hit");
  let drag = null;

  const redraw = () => { TC_VIEW.custom = true; drawTradeChart(); };

  const clampWindow = () => {
    const count = TC_STATE.geo ? TC_STATE.geo.count : 0;
    if (!count) return;
    const span = Math.min(TC_VIEW.i1 - TC_VIEW.i0, count);
    TC_VIEW.i0 = clamp(TC_VIEW.i0, 0, count - span);
    TC_VIEW.i1 = TC_VIEW.i0 + span;
  };

  /* zoom time around whatever the pointer is over, so the bar under the cursor
     stays under it */
  hit.addEventListener("wheel", event => {
    event.preventDefault();
    const geo = TC_STATE.geo;
    if (!geo) return;
    const anchor = geo.indexAt(event.clientX);
    const span = TC_VIEW.i1 - TC_VIEW.i0;
    const next = clamp(span * (event.deltaY > 0 ? 1.14 : 1 / 1.14), 4, geo.count);
    TC_VIEW.i0 = anchor - (anchor - TC_VIEW.i0) * (next / span);
    TC_VIEW.i1 = TC_VIEW.i0 + next;
    clampWindow();
    redraw();
  }, { passive: false });

  hit.addEventListener("pointerdown", event => {
    hit.setPointerCapture(event.pointerId);
    hit.classList.add("dragging");
    drag = { x: event.clientX, y: event.clientY, mode: "pan" };
  });

  axis.addEventListener("pointerdown", event => {
    axis.setPointerCapture(event.pointerId);
    const geo = TC_STATE.geo;
    if (!TC_VIEW.yManual && geo) TC_VIEW.yManual = { min: geo.yMin, max: geo.yMax };
    drag = { x: event.clientX, y: event.clientY, mode: "scale" };
  });

  const endDrag = event => {
    if (!drag) return;
    drag = null;
    hit.classList.remove("dragging");
    if (hit.hasPointerCapture?.(event.pointerId)) hit.releasePointerCapture(event.pointerId);
    if (axis.hasPointerCapture?.(event.pointerId)) axis.releasePointerCapture(event.pointerId);
  };
  for (const el of [hit, axis]) {
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener("dblclick", () => {
      TC_VIEW = { i0: 0, i1: (TC_STATE.geo?.count) || 1, yManual: null, custom: false };
      drawTradeChart();
    });
  }

  hit.addEventListener("pointermove", event => {
    const geo = TC_STATE.geo;
    if (!geo) return;
    if (!drag) { tradeHover(event); return; }

    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    drag.x = event.clientX; drag.y = event.clientY;
    const span = TC_VIEW.i1 - TC_VIEW.i0;
    const move = -dx * (span / geo.plotW);
    TC_VIEW.i0 += move; TC_VIEW.i1 += move;
    clampWindow();
    /* price only follows the drag once the scale has been locked by hand,
       so an ordinary sideways drag does not quietly rescale the y axis */
    if (TC_VIEW.yManual) {
      const shift = dy * ((geo.yMax - geo.yMin) / geo.plotH);
      TC_VIEW.yManual.min += shift; TC_VIEW.yManual.max += shift;
    }
    document.getElementById("tc-tip").classList.remove("on");
    redraw();
  });

  axis.addEventListener("pointermove", event => {
    if (!drag || drag.mode !== "scale" || !TC_VIEW.yManual) return;
    const dy = event.clientY - drag.y;
    drag.y = event.clientY;
    const mid = (TC_VIEW.yManual.min + TC_VIEW.yManual.max) / 2;
    const half = (TC_VIEW.yManual.max - TC_VIEW.yManual.min) / 2;
    const next = clamp(half * (1 + dy / 180), 1e-4, 1e9);
    TC_VIEW.yManual = { min: mid - next, max: mid + next };
    redraw();
  });

  hit.addEventListener("pointerleave", () =>
    document.getElementById("tc-tip").classList.remove("on"));
}

/* ══ views ═══════════════════════════════════════════════ */

let currentView = "dashboard";
const viewReady = { dashboard: true, portfolio: false, history: false, strategies: false, chart: true };

function switchView(name) {
  currentView = name;
  document.body.dataset.view = name;

  for (const b of document.querySelectorAll(".tabs button")) {
    /* the chart has no tab of its own, so whichever page it was opened from
       stays lit while it is on screen */
    const owner = name === "chart" ? TC_ORIGIN : name;
    if (b.dataset.view === owner) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  for (const id of ["dashboard", "portfolio", "history", "strategies", "chart"]) {
    document.getElementById("view-" + id).classList.toggle("hidden", id !== name);
  }

  if (!viewReady[name]) {
    if (name === "portfolio") renderPortfolio();
    if (name === "history") renderHistory();
    if (name === "strategies") renderRules();
    viewReady[name] = true;
  }

  /* a chart measures zero while its panel is hidden */
  if (name === "dashboard") requestAnimationFrame(drawChart);
  if (name === "chart") requestAnimationFrame(drawTradeChart);
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

let tradeResizeTimer = 0;
new ResizeObserver(() => {
  clearTimeout(tradeResizeTimer);
  tradeResizeTimer = setTimeout(() => { if (currentView === "chart") drawTradeChart(); }, 80);
}).observe(document.getElementById("tc-host"));

document.body.dataset.view = "dashboard";
syncThemeButtons();
initChartInteraction();
wireTradeChart();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
