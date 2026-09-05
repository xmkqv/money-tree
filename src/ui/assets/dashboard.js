"use strict";


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


const REFRESH_MS = 30000;

const PULSE_MS = 2000;
/* The run snapshot is served from a five-second cache, so asking faster than
   that only re-reads the same answer. */
const INSIDES_MS = 5000;


const PHONE = window.matchMedia("(max-width: 720px)");
const onPhone = () => PHONE.matches;

const STRATEGY_COLOURS = {
  orb5: "var(--s-orb5)",
  orb10: "var(--s-orb10)",
  sma: "var(--s-momentum)",
  tfb_50: "var(--s-tfb50)",
  unattributed: "var(--ink-3)",
};

const clockLabel = m => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const dparts = d => d.split("-").map(Number);
const dateOf = d => { const [y, m, day] = dparts(d); return new Date(y, m - 1, day); };
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

function tradesFor(cell) {
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
    positionCapUsd: live.positionCapUsd,
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

  const funded = live.equityDaily.length ? live.equityDaily[0].date : LAST_SESSION.date;
  const [fy, fm] = dparts(funded);
  const [ty, tm] = dparts(live.today);
  FIRST_MONTH = { y: fy, m: fm - 1 };
  LAST_MONTH = { y: ty, m: tm - 1 };
  FIRST_IX = monthIndex(FIRST_MONTH.y, FIRST_MONTH.m);
  LAST_IX = Math.max(FIRST_IX, monthIndex(LAST_MONTH.y, LAST_MONTH.m));

  DAILY = live.equityDaily.map((r, i) => ({
    label: dateOf(r.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
    long: dateOf(r.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }),
    value: Math.round((r.equity - live.invested) * 100) / 100,
    before: i ? Math.round((live.equityDaily[i - 1].equity - live.invested) * 100) / 100 : 0,
  }));
  DAILY.equityBase = live.invested;

  DAILY.liveTip = live.equityDaily.length > 0 && live.equityDaily.at(-1).date === live.today;

  const opening = live.intraday.length ? live.intraday[0].equity : live.equity;
  INTRADAY = live.intraday.map((r, i) => ({
    label: r.t,
    long: (live.intradayDate ? dateOf(live.intradayDate).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) + ", " : "") + r.t,
    value: Math.round((r.equity - live.invested) * 100) / 100,
    before: Math.round(((i ? live.intraday[i - 1].equity : opening) - live.invested) * 100) / 100,
  }));
  INTRADAY.equityBase = live.invested;
  INTRADAY.liveTip = live.intraday.length > 0 && live.intradayDate === live.today;
  if (!INTRADAY.length) INTRADAY = DAILY;

  ACCOUNT.dayOpening = live.intraday.length ? opening : 0;
  ACCOUNT.dayLowEquity = live.intraday.length
    ? ratchetLow(live.intradayDate, Math.min(...live.intraday.map(r => r.equity), live.equity))
    : 0;
  ACCOUNT.dayDrawdownPct = drawdownPct();
}

let SESSION_LOW = { date: "", equity: 0 };

function ratchetLow(date, equity) {
  if (SESSION_LOW.date !== date) SESSION_LOW = { date, equity };
  else SESSION_LOW.equity = Math.min(SESSION_LOW.equity, equity);
  return SESSION_LOW.equity;
}

function drawdownPct() {
  if (!ACCOUNT.dayOpening) return 0;
  const fallen = Math.min(0, ACCOUNT.dayLowEquity - ACCOUNT.dayOpening);
  return Math.abs(fallen) / ACCOUNT.dayOpening * 100;
}


let todayTab = "closed";

const isLatest = () => todaySel.y === LATEST.y && todaySel.m === LATEST.m && todaySel.day === LATEST.day;

function selectedCell() {
  const md = monthData(todaySel.y, todaySel.m);
  return md.days.find(d => d.day === todaySel.day) || null;
}

function renderToday() {
  const cell = selectedCell();
  const trades = tradesFor(cell);
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
    const cells = [];
    for (const [i, c] of row.entries()) {
      const td = document.createElement("td");
      if (c.node) td.append(c.node);
      else td.textContent = c.t;
      td.dataset.label = headers[i];
      if (c.r) td.classList.add("r");
      if (c.cls) td.classList.add(c.cls);
      if (c.dim) td.classList.add("flat");
      cells.push(td);
      tr.append(td);
    }
    const key = cells.find(td => td.querySelector(".sym")) || cells[0];
    if (key) key.classList.add("key");
    const lead = cells.find(td => /^(p&l|unreal)/i.test(td.dataset.label)) || cells[cells.length - 1];
    if (lead && lead !== key) lead.classList.add("lead");
    tbody.append(tr);
  });
  table.replaceChildren(thead, tbody);
}

function selectDay(y, m, day) {
  todaySel = { y, m, day };
  renderToday();
  renderCalendar();
}


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




const SWITCH_STATE = {
  online:  { label: "Online",  hint: "Enabled — this engine is allowed to trade" },
  paused:  { label: "Paused",  hint: "Paused by us — it manages what it holds, opens nothing new" },
  offline: { label: "Offline", hint: "Not on the bot's roster — this engine is not running at all" },
  unknown: { label: "Unknown", hint: "The bot has not reported, so its roster is unknown" },
};

const SESSION_STATE = {
  open:   { label: "Open",   hint: "Inside its entry window — it can open a trade now" },
  closed: { label: "Closed", hint: "Outside its entry window — no new trade will start" },
};

function switchState(id) {
  const bot = LIVE.bot || {};
  if (!bot.reported) return "unknown";
  if (!(bot.strategies || []).includes(id)) return "offline";
  return (bot.paused || []).includes(id) ? "paused" : "online";
}

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
    nm.title = s.label;
    strat.append(chip, nm);
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


const PAD = { t: 12, r: 58, b: 22, l: 16 };

const chart = {
  series: null,
  i0: 0, i1: 1,          
  yManual: null,         
  preset: "ALL",
  custom: false,
};

let geo = null;          

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

function chartWindow() {
  const s = chart.series;
  if (!s || !s.length) return null;                    
  const N = s.length;
  const lo = clamp(Math.floor(chart.i0), 0, N - 1);
  const hi = clamp(Math.ceil(chart.i1), 0, N - 1);
  const baseline = s[lo].before;
  const visible = [];
  for (let i = lo; i <= hi; i++) visible.push({ i, p: s[i], y: s[i].value - baseline });
  return { s, N, lo, hi, baseline, visible, last: visible[visible.length - 1] };
}

function paintChartHero(w) {
  const delta = w.last.y;
  const equityAtStart = w.s.equityBase + w.baseline;

  const big = document.getElementById("chart-big");
  big.textContent = signedMoney(delta);
  big.className = "big num " + tone(delta);

  const d = document.getElementById("chart-delta");
  d.textContent = signedPct((delta / equityAtStart) * 100) + " over view";
  d.className = "delta " + tone(delta);

  document.getElementById("chart-note").textContent =
    w.visible[0].p.label + " – " + w.last.p.label + (chart.series === INTRADAY && LIVE.intradayDate ? " · " + dayOf(LIVE.intradayDate) : "");

  document.getElementById("chart-table").innerHTML =
    "<table><caption>Cumulative profit and loss across the visible window</caption><tbody>" +
    w.visible.map(v => "<tr><th scope='row'>" + v.p.long + "</th><td>" + signedMoney(v.y) + "</td></tr>").join("") +
    "</tbody></table>";
}

function drawChart() {
  const w = chartWindow();
  if (!w) return;
  paintChartHero(w);
  if (onPhone()) return;            

  const host = document.getElementById("chart-host");
  const width = host.clientWidth;
  const height = host.clientHeight;
  if (width < 60 || height < 60) return;
  readTheme();

  const { N, lo, hi, baseline, visible } = w;
  const plotW = width - PAD.l - PAD.r;
  const plotH = height - PAD.t - PAD.b;

  const i0 = chart.i0, i1 = chart.i1;

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
  const indexAt = clientX => {
    const box = document.getElementById("chart-host").getBoundingClientRect();
    return i0 + ((clientX - box.left - PAD.l) / plotW) * (i1 - i0);
  };
  geo = { width, height, plotW, plotH, N, px, py, indexAt, yMin, yMax, baseline, lo, hi };

  const zeroY = clamp(py(0), PAD.t, PAD.t + plotH);
  const line = visible.map((v, k) => (k ? "L" : "M") + px(v.i).toFixed(2) + " " + py(v.y).toFixed(2)).join(" ");
  const area = line +
    " L" + px(visible[visible.length - 1].i).toFixed(2) + " " + zeroY.toFixed(2) +
    " L" + px(visible[0].i).toFixed(2) + " " + zeroY.toFixed(2) + " Z";

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

  Object.assign(document.getElementById("plot-hit").style, {
    left: PAD.l + "px", top: PAD.t + "px", width: plotW + "px", height: plotH + "px",
  });
  Object.assign(document.getElementById("axis-hit").style, {
    left: (width - PAD.r) + "px", top: PAD.t + "px", width: PAD.r + "px", height: plotH + "px",
  });
}


const ZOOM_STEP = 1.14;
const SCALE_TRAVEL_PX = 180;
const TAP_TRAVEL_PX = 8;

function wirePanZoom(spec) {
  const { plot, axis, view, geometry, spanMin, spanMax, scaleMin, clampWindow, redraw, onReset } = spec;
  const { onHover, onLeave, pinchable } = spec;
  let drag = null;
  let pinch = null;
  const touches = new Map();

  const twoFingers = () => [...touches.values()].slice(0, 2);
  const spreadOf = () => {
    const [a, b] = twoFingers();
    return Math.hypot(a.x - b.x, a.y - b.y);
  };
  const midpointOf = () => {
    const [a, b] = twoFingers();
    return (a.x + b.x) / 2;
  };

  const zoomAbout = (span, clientX) => {
    const geo = geometry();
    if (!geo) return;
    const anchor = geo.indexAt(clientX);
    const current = view.i1 - view.i0;
    const next = clamp(span, spanMin, spanMax(geo));
    view.i0 = anchor - (anchor - view.i0) * (next / current);
    view.i1 = view.i0 + next;
    clampWindow();
    redraw();
  };

  plot.addEventListener("wheel", event => {
    event.preventDefault();
    const span = view.i1 - view.i0;
    zoomAbout(span * (event.deltaY > 0 ? ZOOM_STEP : 1 / ZOOM_STEP), event.clientX);
  }, { passive: false });

  plot.addEventListener("pointerdown", event => {
    if (pinchable && event.pointerType === "touch") {
      touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (touches.size === 2) {
        pinch = { spread: spreadOf(), span: view.i1 - view.i0 };
        drag = null;
        plot.classList.remove("dragging");
        onLeave?.();
        return;
      }
      if (touches.size > 2) return;
    }
    plot.setPointerCapture(event.pointerId);
    plot.classList.add("dragging");
    drag = { x: event.clientX, y: event.clientY, mode: "pan", travel: 0 };
  });

  axis.addEventListener("pointerdown", event => {
    axis.setPointerCapture(event.pointerId);
    const geo = geometry();
    if (!view.yManual && geo) view.yManual = { min: geo.yMin, max: geo.yMax };
    drag = { x: event.clientX, y: event.clientY, mode: "scale", travel: 0 };
  });

  const endDrag = event => {
    touches.delete(event.pointerId);
    if (touches.size < 2) pinch = null;
    if (!drag) return;
    const tapped = event.type === "pointerup" && event.pointerType === "touch";
    if (pinchable && tapped && drag.travel < TAP_TRAVEL_PX) onHover?.(event);
    drag = null;
    plot.classList.remove("dragging");
    if (plot.hasPointerCapture?.(event.pointerId)) plot.releasePointerCapture(event.pointerId);
    if (axis.hasPointerCapture?.(event.pointerId)) axis.releasePointerCapture(event.pointerId);
  };

  for (const el of [plot, axis]) {
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener("dblclick", onReset);
  }

  plot.addEventListener("pointermove", event => {
    const geo = geometry();
    if (!geo) return;
    if (touches.has(event.pointerId))
      touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pinch && touches.size >= 2) {
      const spread = spreadOf();
      if (spread > 0) zoomAbout(pinch.span * (pinch.spread / spread), midpointOf());
      return;
    }
    if (!drag || drag.mode !== "pan") {
      onHover?.(event);
      return;
    }
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    drag.x = event.clientX; drag.y = event.clientY;
    drag.travel += Math.abs(dx) + Math.abs(dy);
    const span = view.i1 - view.i0;
    const move = -dx * (span / geo.plotW);
    view.i0 += move; view.i1 += move;
    clampWindow();
    if (view.yManual) {
      const shift = dy * ((geo.yMax - geo.yMin) / geo.plotH);
      view.yManual.min += shift; view.yManual.max += shift;
    }
    redraw();
    onLeave?.();
  });

  axis.addEventListener("pointermove", event => {
    if (!drag || drag.mode !== "scale" || !view.yManual || !geometry()) return;
    const dy = event.clientY - drag.y;
    drag.y = event.clientY;
    const mid = (view.yManual.min + view.yManual.max) / 2;
    const half = (view.yManual.max - view.yManual.min) / 2;
    const next = clamp(half * (1 + dy / SCALE_TRAVEL_PX), scaleMin, 1e9);
    view.yManual = { min: mid - next, max: mid + next };
    redraw();
  });

  plot.addEventListener("pointerleave", event => {
    if (pinchable && event.pointerType === "touch") return;
    onLeave?.();
  });
}

function clampChartWindow() {
  const N = chart.series.length;
  const span = clamp(chart.i1 - chart.i0, 3, N - 1);
  if (chart.i0 < 0) chart.i0 = 0;
  if (chart.i0 + span > N - 1) chart.i0 = N - 1 - span;
  chart.i1 = chart.i0 + span;
}

function chartHover(event) {
  const tip = document.getElementById("chart-tip");
  const svg = document.getElementById("chart-host").querySelector("svg");
  if (!svg) return;
  const i = clamp(Math.round(geo.indexAt(event.clientX)), geo.lo, geo.hi);
  const point = chart.series[i];
  const y = point.value - geo.baseline;
  const cross = svg.querySelector("#cross");
  const dot = svg.querySelector("#crossDot");

  cross.setAttribute("x1", geo.px(i)); cross.setAttribute("x2", geo.px(i));
  cross.setAttribute("opacity", "1");
  dot.setAttribute("cx", geo.px(i)); dot.setAttribute("cy", geo.py(y));
  dot.setAttribute("fill", y >= 0 ? GAIN : LOSS);
  dot.setAttribute("opacity", "1");

  const equityAtStart = chart.series.equityBase + geo.baseline;
  tip.innerHTML = "<span class='tt-k'>" + point.long + "</span>" +
    "<span class='tt-v " + tone(y) + "'>" + signedMoney(y) + "</span>" +
    "<span class='tt-row'><span>from view start</span><span>" + signedPct((y / equityAtStart) * 100) + "</span></span>";
  tip.classList.add("on");
  tip.style.left = clamp(geo.px(i), 80, geo.width - 80) + "px";
  tip.style.top = Math.max(52, geo.py(y)) + "px";
}

function chartLeave() {
  document.getElementById("chart-tip").classList.remove("on");
  const svg = document.getElementById("chart-host").querySelector("svg");
  if (!svg) return;
  svg.querySelector("#cross").setAttribute("opacity", "0");
  svg.querySelector("#crossDot").setAttribute("opacity", "0");
}

function initChartInteraction() {
  wirePanZoom({
    plot: document.getElementById("plot-hit"),
    axis: document.getElementById("axis-hit"),
    view: chart,
    geometry: () => geo,
    spanMin: 3,
    spanMax: () => chart.series.length - 1,
    scaleMin: 1e-3,
    clampWindow: clampChartWindow,
    redraw: () => { markCustom(); drawChart(); },
    onReset: () => setRange(chart.preset),
    onHover: chartHover,
    onLeave: chartLeave,
    pinchable: false,
  });
}




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

  document.getElementById("pf-cap-note").textContent = "vs " + money(ACCOUNT.positionCapUsd) + " cap";
  document.getElementById("pf-cap").innerHTML =
    "<b>" + ACCOUNT.largestPositionPct.toFixed(1) + "%</b> of " + ACCOUNT.positionCapPct.toFixed(1) + "%";
  const cm = document.getElementById("pf-cap-meter");
  cm.style.width = clamp(ACCOUNT.largestPositionPct / ACCOUNT.positionCapPct, 0, 1) * 100 + "%";
  cm.style.background = "var(--ink-3)";

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

  const fs = document.getElementById("f-strategy");
  if (fs.options.length === 1) {
    for (const st of STRATEGIES) fs.append(new Option(st.label, st.id));
    const fm = document.getElementById("f-month");
    for (const m of [...SESSIONS].reverse()) fm.append(new Option(m.long, m.date));
  }

  renderLog();
}

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

  const days = [...new Set(rows.map(t => t.date))].sort();
  const shade = rows.map(t => days.indexOf(t.date) % 2 === 1);

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



const TC_BARS = { "5Min": "5 min", "1Hour": "1 hour", "1Day": "Day" };
let TRADE = null, TC_STATE = { bar: "5Min", bars: null, hover: null };
let TC_LEVELS = null, TC_COTRADES = [];
const TC_VIEW = { i0: 0, i1: 0, yManual: null, custom: false };
let TC_ORIGIN = "history";

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
  if (from) TC_ORIGIN = from;
  TC_LEVELS = null;
  TC_STATE = { bar: "5Min", bars: null, hover: null };
  TC_COTRADES = ALL_TRADES.filter(t => t.symbol === trade.symbol).slice().reverse();
  if (trade.open) TC_COTRADES.push(trade);
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
  const index = TC_COTRADES.findIndex(t => t === TRADE);
  document.getElementById("tc-step").hidden = TC_COTRADES.length < 2;
  document.getElementById("tc-count").textContent = (index + 1) + " of " + TC_COTRADES.length;
  document.getElementById("tc-prev").disabled = index <= 0;
  document.getElementById("tc-next").disabled = index < 0 || index >= TC_COTRADES.length - 1;
}

function stepTrade(by) {
  const index = TC_COTRADES.findIndex(t => t === TRADE) + by;
  if (index < 0 || index >= TC_COTRADES.length) return;
  openTradeChart(TC_COTRADES[index]);
}

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
    ["Entry", money(t.entry), dayLabel(t.inDate) + " " + clockLabel(t.inMinute)],
    [t.open ? "Last" : "Exit", money(t.exit),
      t.open ? "still open" : dayLabel(t.date) + " " + clockLabel(t.minute)],
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

function dayLabel(iso) {
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
  setTradeView(0, Math.max(1, TC_STATE.bars.length - TC_STATE.first));
  paintRail();
  drawTradeChart();
}

const TC_PADS = {
  wide:  { l: 10, r: 62, t: 16, b: 40 },
  phone: { l: 6,  r: 50, t: 12, b: 38 },
};

function drawTradeChart() {
  const host = document.getElementById("tc-host");
  const bars = TC_STATE.bars;
  if (!bars || !bars.length) return;
  const TC_PAD = onPhone() ? TC_PADS.phone : TC_PADS.wide;
  const width = host.clientWidth, height = host.clientHeight;
  if (width < 80 || height < 80) return;
  readTheme();

  const t = TRADE;
  const plotW = width - TC_PAD.l - TC_PAD.r, plotH = height - TC_PAD.t - TC_PAD.b;

  const averages = {};
  for (const { length } of SMA_SET) {
    if (TC_SHOW["sma" + length] && bars.length >= length) {
      averages[length] = movingAverage(bars, length);
    }
  }
  const first = TC_STATE.first || 0;
  const all = bars.slice(first);
  if (!all.length) return;
  if (TC_VIEW.i1 <= TC_VIEW.i0) setTradeView(0, all.length);

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
  const byMonths = daily && byDay.size > roomFor;
  const anchors = byMonths ? byMonth : byDay;

  const keep = Math.max(1, Math.ceil(anchors.size / roomFor));
  const labelled = new Map();
  [...anchors.entries()].forEach(([text, index], n) => {
    if (n % keep === 0) labelled.set(index, text);
  });
  const boundary = new Set(anchors.values());

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

  const CHAR = 6.1, GAP = 10;          
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
    if (previous.clamped && !candidate.clamped) kept[kept.length - 1] = candidate;
    else if (previous.clamped && candidate.clamped) kept[kept.length - 1] = candidate;
  }

  const rules = shown.map((_bar, k) => {
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

  smaEnds.sort((a, b) => a.y - b.y);
  smaEnds.forEach((end, i) => {
    if (i && end.y - smaEnds[i - 1].y < 12) end.y = smaEnds[i - 1].y + 12;
  });
  const smaLabels = smaEnds.map(end =>
    '<text x="' + (width - TC_PAD.r - 4) + '" y="' + (end.y - 3).toFixed(2) + '" fill="' + end.colour +
    '" font-size="10" text-anchor="end" font-weight="600" paint-order="stroke" stroke="' + C.ring +
    '" stroke-width="3" stroke-linejoin="round" font-family="Roboto Mono, monospace">' +
    end.length + "</text>").join("");

  const band = (top, bottom, colour) =>
    '<rect x="' + TC_PAD.l + '" y="' + Math.min(top, bottom).toFixed(2) + '" width="' + plotW +
    '" height="' + Math.abs(bottom - top).toFixed(2) + '" fill="' + colour + '" opacity="0.07"/>';
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
      '" height="' + h.toFixed(2) + '" fill="' + colour + '" opacity="' + (up ? 0.9 : 1) + '"/>';
  }).join("");

  const tone2 = t.pnl >= 0 ? GAIN : LOSS;
  const x1 = px(inIndex), y1 = py(t.entry), x2 = px(outIndex), y2 = py(t.exit);
  const trend =
    '<line x1="' + x1.toFixed(2) + '" y1="' + y1.toFixed(2) + '" x2="' + x2.toFixed(2) + '" y2="' + y2.toFixed(2) +
    '" stroke="' + tone2 + '" stroke-width="2" stroke-linecap="round" stroke-dasharray="6 4" opacity="0.95"/>';

  const level = (y, colour) =>
    '<line x1="' + TC_PAD.l + '" y1="' + y.toFixed(2) + '" x2="' + (width - TC_PAD.r) + '" y2="' + y.toFixed(2) +
    '" stroke="' + colour + '" stroke-width="1" stroke-dasharray="2 5" opacity="0.5"/>';

  const entryMark =
    '<circle cx="' + x1.toFixed(2) + '" cy="' + y1.toFixed(2) + '" r="5.5" fill="' + C.ring +
    '" stroke="' + C.axis + '" stroke-width="2.5"/>';
  const exitMark =
    '<circle cx="' + x2.toFixed(2) + '" cy="' + y2.toFixed(2) + '" r="6" fill="' + tone2 +
    '" stroke="' + C.ring + '" stroke-width="2"/>';

  const fillMarks = (t.fills || []).map(f => {
    const i = nearest(stampOf(f.d, f.m));
    const x = px(i), y = py(f.p);
    return '<rect x="' + (x - 3.5).toFixed(2) + '" y="' + (y - 3.5).toFixed(2) +
      '" width="7" height="7" rx="1.5" transform="rotate(45 ' + x.toFixed(2) + " " + y.toFixed(2) +
      ')" fill="' + (f.s === "in" ? C.ring : tone2) + '" stroke="' + (f.s === "in" ? C.axis : tone2) +
      '" stroke-width="1.5" opacity="0.9"/>';
  }).join("");

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
    el.style.borderLeftColor = cls === "exit" ? result : "var(--ink-3)";
    if (x > width * 0.6) el.classList.add("flip");
    host.append(el);
  };
  if (entryInView) place(x1, y1, "Entry", TRADE.entry, "entry");
  if (exitInView) place(x2, y2, TRADE.open ? "Now" : "Exit", TRADE.exit, "exit");
  separateMarks(host);
}

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
  wirePanZoom({
    plot: document.getElementById("tc-hit"),
    axis: document.getElementById("tc-axis-hit"),
    view: TC_VIEW,
    geometry: () => TC_STATE.geo,
    spanMin: 4,
    spanMax: geo => geo.count,
    scaleMin: 1e-4,
    clampWindow: clampTradeWindow,
    redraw: () => { TC_VIEW.custom = true; drawTradeChart(); },
    onReset: resetTradeView,
    onHover: tradeHover,
    onLeave: () => document.getElementById("tc-tip").classList.remove("on"),
    pinchable: true,
  });
}

function clampTradeWindow() {
  const count = TC_STATE.geo ? TC_STATE.geo.count : 0;
  if (!count) return;
  const span = Math.min(TC_VIEW.i1 - TC_VIEW.i0, count);
  TC_VIEW.i0 = clamp(TC_VIEW.i0, 0, count - span);
  TC_VIEW.i1 = TC_VIEW.i0 + span;
}

function setTradeView(i0, i1) {
  TC_VIEW.i0 = i0;
  TC_VIEW.i1 = i1;
  TC_VIEW.yManual = null;
  TC_VIEW.custom = false;
}

function resetTradeView() {
  setTradeView(0, (TC_STATE.geo?.count) || 1);
  drawTradeChart();
}


let currentView = "dashboard";
const viewReady = { dashboard: true, portfolio: false, history: false, strategies: false, insides: false, chart: true };

function switchView(name) {
  currentView = name;
  document.body.dataset.view = name;

  for (const b of document.querySelectorAll(".tabs button")) {
    const owner = name === "chart" ? TC_ORIGIN : name;
    if (b.dataset.view === owner) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  for (const id of ["dashboard", "portfolio", "history", "strategies", "insides", "chart"]) {
    document.getElementById("view-" + id).classList.toggle("hidden", id !== name);
  }

  if (!viewReady[name]) {
    if (name === "portfolio") renderPortfolio();
    if (name === "history") renderHistory();
    if (name === "strategies") renderRules();
    viewReady[name] = true;
  }

  /* The run state is a five-second read of a value held in memory, and it is
     the whole point of this page, so it is asked for on the way in and on
     every tick the page is open rather than riding the ledger's cadence. */
  if (name === "insides") readInsides();
  if (name === "dashboard") requestAnimationFrame(drawChart);
  if (name === "chart") requestAnimationFrame(drawTradeChart);
  window.scrollTo(0, 0);
}



/* The bot's own report on itself. Everything drawn here comes from the state
   snapshot the bot posts every few seconds, which the web service holds in
   memory and nothing writes down — so the page says what it can and cannot
   know rather than letting an empty table read as a quiet session. */

const RUN_WORDS = {
  running: "Running",
  starting: "Starting",
  stopped: "Stopped",
  failed: "Failed",
  unknown: "Not reporting",
};
const RUN_TONES = { running: "pos", starting: "warn", stopped: "flat", failed: "neg" };
const LEVEL_RANK = { info: 0, warning: 1, error: 2 };
const SWITCH_WORDS = { online: "on", paused: "paused", offline: "off", unknown: "?" };
/* The bot keeps this many events per run, from bot/export.py. */
const EVENTS_KEPT = 50;

let INSIDES = null;
let insidesLevel = "all";

/* Trailing zeros make 0.5% read as 0.50%, which invites the eye to compare it
   with figures it is not stated to that precision. Same rule as _pct in
   ui/strategies.py, so the two pages quote a limit identically. */
function limitPct(fraction) {
  return Number((fraction * 100).toFixed(2)).toString() + "%";
}

function secondsLabel(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return Math.round(seconds) + "s";
  if (seconds < 3600) return Math.floor(seconds / 60) + "m " + Math.round(seconds % 60) + "s";
  const hours = Math.floor(seconds / 3600);
  return hours + "h " + Math.floor((seconds % 3600) / 60) + "m";
}

/* Seconds matter here in a way they do not anywhere else on the site: a burst
   of events inside one minute is exactly what a bad open looks like. */
function eventClock(iso) {
  const at = new Date(iso);
  const clock = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(at);
  return dayOf(iso) + " " + clock;
}

/* The roster of names is normally learnt from the ledger, but this page has to
   read when the ledger cannot: an engine reporting an error is exactly when
   the broker read is also failing, and a page that went blank then would be
   useless at the one moment it is wanted. So the label is resolved when the
   roster is known and passed through untouched when it is not. */
function engineOf(published) {
  if (!published) return null;
  const roster = (LIVE && LIVE.strategies) || [];
  return roster.find(s => s.id === published || s.label === published) || null;
}

function engineIdOf(published) {
  const known = engineOf(published);
  return known ? known.id : null;
}

function engineNameOf(published) {
  if (!published) return "—";
  const known = engineOf(published);
  return known ? known.short : published;
}

function paintInsidesRun() {
  const snapshot = INSIDES;
  const status = snapshot ? snapshot.status : "unknown";
  const stale = !snapshot || INSIDES_STALE;
  const now = Date.now();
  const since = snapshot ? (now - Date.parse(snapshot.started_at)) / 1000 : NaN;
  const heard = snapshot ? (now - Date.parse(snapshot.heartbeat_at)) / 1000 : NaN;

  document.getElementById("in-run").textContent = snapshot
    ? "run " + String(snapshot.run_id).slice(0, 8)
    : "no run reported";

  const alarm = document.getElementById("in-alarm");
  alarm.textContent = !snapshot
    ? "The bot has never reported to this page. Either it is not running, or it has no "
      + "STATE_EXPORT_URL and STATE_EXPORT_SECRET to report through — in which case every "
      + "event it raises is discarded where it is raised."
    : stale
      ? "The bot has stopped reporting. Everything below is its last word, not its current "
        + "state."
      : status === "failed"
        ? "The bot reported a failure. The events below are the last thing it said."
        : "";
  alarm.hidden = !alarm.textContent;

  document.getElementById("in-tiles").replaceChildren(
    tile("Status", RUN_WORDS[status] || status, RUN_TONES[status] || "flat",
      stale && snapshot ? "last report is stale" : ""),
    tile("Last report", snapshot ? secondsLabel(heard) + " ago" : "—", stale ? "warn" : "pos",
      "posted every 5s"),
    tile("Running for", snapshot ? secondsLabel(since) : "—", "", "since the run began"),
    tile("Reports", snapshot ? String(snapshot.sequence) : "—", "", "snapshots posted"),
  );

  const roster = document.getElementById("in-roster");
  roster.replaceChildren();
  if (!snapshot) {
    const none = document.createElement("span");
    none.className = "engine is-unknown";
    none.textContent = "Roster unknown — the bot has not reported one.";
    roster.append(none);
    return;
  }
  const paused = new Set(snapshot.paused || []);
  /* The bot publishes its roster in its own order. Listed here by the name on
     screen, like every other list of engines on the site — and reading runs of
     digits as numbers, so ORB5 comes before ORB10, the way label_order in
     ledger.py sorts the lists the server builds. */
  const roll = [...snapshot.strategies].sort((a, b) =>
    engineNameOf(a).localeCompare(engineNameOf(b), undefined, { numeric: true }));
  for (const published of roll) {
    const state = paused.has(published) ? "paused" : "online";
    const id = engineIdOf(published);
    const wrap = document.createElement("span");
    wrap.className = "engine is-" + state;
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = STRATEGY_COLOURS[id] || "var(--ink-3)";
    const name = document.createElement("span");
    name.textContent = engineNameOf(published);
    const word = document.createElement("span");
    word.className = "st";
    word.textContent = SWITCH_WORDS[state];
    wrap.append(chip, name, word);
    roster.append(wrap);
  }
}

function paintInsidesLimits() {
  const limits = INSIDES && INSIDES.configuration;
  const host = document.getElementById("in-limits");
  if (!limits) {
    host.replaceChildren(tile("Limits", "—", "flat", "not reported"));
    return;
  }
  host.replaceChildren(
    tile("Risk per trade", limitPct(limits.risk_per_trade_max), "", "of equity, per position"),
    tile("Risk per day", limitPct(limits.risk_per_day_max), "", "then everything is closed"),
    tile("Position cap", money(limits.position_value_usd_max), "", "at most in one name"),
    tile("Fractional", limits.fractional_orders ? "Yes" : "No", "", "part shares allowed"),
  );
}

function paintInsidesEvents() {
  const all = INSIDES ? INSIDES.events.slice().reverse() : [];
  const shown = insidesLevel === "all" ? all : all.filter(e => LEVEL_RANK[e.level] > 0);
  const attention = all.filter(e => LEVEL_RANK[e.level] > 0).length;

  const note = document.getElementById("in-note");
  if (!INSIDES) {
    note.textContent = "No events: the bot has not reported. That is not the same as a quiet "
      + "session — an unreported bot raises events into nothing.";
  } else if (!all.length) {
    note.textContent = "The bot has reported no events on this run yet.";
  } else {
    note.textContent = all.length + " event" + (all.length === 1 ? "" : "s") + " on this run, "
      + attention + " needing a look. The bot keeps only its last " + EVENTS_KEPT + ", and both it "
      + "and this page hold them in memory only — a restart of either starts the list again, so "
      + "a short list is not proof of a quiet run.";
  }

  /* The message leads and the clock trails because buildTable reads a row the
     way the trade tables are shaped: the first cell becomes the card's subject
     on a phone and the last is set beside it. What the bot said is the subject
     here, and the clock is the short figure that pairs with it. */
  const rows = shown.map(event => [
    { t: event.message, cls: "msg" },
    { node: levelPill(event.level) },
    { t: engineNameOf(event.strategy) },
    { t: event.kind, cls: "flat" },
    { t: eventClock(event.occurred_at), cls: "flat" },
  ]);
  buildTable(
    document.getElementById("in-events"),
    ["What it said", "Level", "Engine", "Kind", "When"],
    rows,
    99,
    row => {
      const level = row[1].node.dataset.level;
      return level === "error" ? "failure" : level === "warning" ? "attention" : "";
    },
  );
  if (!rows.length) {
    const body = document.createElement("tbody");
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.className = "empty";
    td.textContent = insidesLevel === "all"
      ? "Nothing reported."
      : "Nothing needing a look. Every event on this run is routine.";
    tr.append(td);
    body.append(tr);
    document.getElementById("in-events").append(body);
  }
}

function levelPill(level) {
  const pill = document.createElement("span");
  pill.className = "lvl lvl-" + level;
  pill.dataset.level = level;
  pill.textContent = level;
  return pill;
}

function paintInsides() {
  paintInsidesRun();
  paintInsidesLimits();
  paintInsidesEvents();
}

let INSIDES_STALE = true;

async function readInsides() {
  try {
    const response = await fetch("/api/run", { credentials: "same-origin" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const body = await response.json();
    INSIDES = body.data;
    INSIDES_STALE = Boolean(body.stale);
  } catch (error) {
    INSIDES = null;
    INSIDES_STALE = true;
  }
  paintInsides();
}


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
    : "Bot not reporting — risk limits shown are from the mode environment";

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
  /* The roster names engines by their short label, which is learnt from the
     ledger. Until that arrives the page falls back to the long label the bot
     published, so repaint once it lands rather than leaving the two forms
     mixed for as long as the reader stays on the page. */
  if (viewReady.insides && INSIDES) paintInsidesRun();
}


function mergeMarks(marks) {
  const rows = new Map(OPEN_POSITIONS.map(pos => [pos.symbol, pos]));
  if (marks.length !== rows.size || marks.some(m => !rows.has(m.symbol))) return false;
  for (const mark of marks) Object.assign(rows.get(mark.symbol), mark);
  OPEN_POSITIONS.sort((a, b) => b.value - a.value);
  return true;
}

function retipSeries(series, equity) {
  if (!series.liveTip || !series.length) return;
  series[series.length - 1].value = Math.round((equity - series.equityBase) * 100) / 100;
}

function applyPulse(pulsed) {
  ACCOUNT.portfolio = pulsed.equity;
  ACCOUNT.cash = pulsed.cash;
  ACCOUNT.deployed = pulsed.marketValue;
  ACCOUNT.unrealised = pulsed.unrealised;
  ACCOUNT.buyingPower = pulsed.buyingPower;
  ACCOUNT.totalReturn = Math.round((ACCOUNT.portfolio - ACCOUNT.invested) * 100) / 100;
  ACCOUNT.rateOfReturn = ACCOUNT.invested ? (ACCOUNT.totalReturn / ACCOUNT.invested) * 100 : 0;
  ACCOUNT.exposurePct = ACCOUNT.portfolio ? (ACCOUNT.deployed / ACCOUNT.portfolio) * 100 : 0;

  if (ACCOUNT.dayOpening) ACCOUNT.dayLowEquity = ratchetLow(SESSION_LOW.date, pulsed.equity);
  ACCOUNT.dayDrawdownPct = drawdownPct();

  const aligned = mergeMarks(pulsed.positions);
  ACCOUNT.openPositions = OPEN_POSITIONS.length;
  ACCOUNT.largestPositionPct = OPEN_POSITIONS.length
    ? Math.max(...OPEN_POSITIONS.map(p => p.weight)) : 0;

  retipSeries(DAILY, pulsed.equity);
  retipSeries(INTRADAY, pulsed.equity);

  LIVE.asOf = pulsed.asOf;
  return aligned;
}

function hovering(id) {
  const node = document.getElementById(id);
  return node !== null && node.matches(":hover");
}

function paintPulse() {
  renderAccount();
  if (currentView === "dashboard") {
    drawChart();
    if (todayTab === "open" && !hovering("today-table")) renderToday();
  }
  if (currentView === "portfolio" && viewReady.portfolio && !hovering("pf-open-table")) {
    renderPortfolio();
  }
}

let resyncing = false;

let pulsing = false;

async function pulse() {
  if (!booted || pulsing) return;       
  pulsing = true;
  try {
    const response = await fetch("/api/pulse", { headers: { Accept: "application/json" } });
    if (response.status === 401) { location.replace("/login"); return; }
    if (!response.ok) throw new Error("pulse failed (" + response.status + ")");

    const aligned = applyPulse((await response.json()).data);
    paintPulse();
    markFeed("ok");

    if (!aligned && !resyncing) {
      resyncing = true;
      refresh().finally(() => { resyncing = false; });
    }
  } catch (error) {
    markFeed("error", "feed unavailable — retrying");
  } finally {
    pulsing = false;
  }
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


document.querySelector(".tabs").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (btn && btn.dataset.view) switchView(btn.dataset.view);
});

document.getElementById("in-levels").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  insidesLevel = btn.dataset.level;
  for (const b of document.querySelectorAll("#in-levels button")) {
    b.setAttribute("aria-pressed", String(b === btn));
  }
  paintInsidesEvents();
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
  try { localStorage.setItem("mt-theme", btn.dataset.setTheme); } catch (error) {  }
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

PHONE.addEventListener("change", () => {
  if (!onPhone() && currentView === "dashboard") requestAnimationFrame(drawChart);
});

document.body.dataset.view = "dashboard";
syncThemeButtons();
initChartInteraction();
wireTradeChart();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, REFRESH_MS);
setInterval(() => { if (!document.hidden) pulse(); }, PULSE_MS);
setInterval(() => {
  if (!document.hidden && currentView === "insides") readInsides();
}, INSIDES_MS);

document.addEventListener("visibilitychange", () => {
  if (document.hidden) return;
  pulse();
  refresh();
  if (currentView === "insides") readInsides();
});
