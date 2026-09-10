import { html, render, repeat, nothing, styleMap } from "/assets/lit.min.js";


const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

const money = v => usd.format(v);
const signedMoney = v => (v > 0 ? "+" : v < 0 ? "−" : "") + usd.format(Math.abs(v));
const signedPct = (v, d = 2) => v === null || !Number.isFinite(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d) + "%";
const ratio = v => Number.isFinite(v) ? v.toFixed(2) : "—";
const plainNum = new Intl.NumberFormat("en-US").format;
const tone = v => (v > 0 ? "pos" : v < 0 ? "neg" : "flat");
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}


const MONTHS = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"];
const MON3 = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DAY3 = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];


const onPhone = () => token("--is-phone") === "1";

const strategyHue = key => "var(--s-" + key.replaceAll("_", "-") + "-h)";

function strategyChip(hue) {
  return html`<span class=${"chip" + (hue ? "" : " plain")}
    style=${styleMap({"--strategy-h": hue})}></span>`;
}

function meterBar(fill, extraClass = "", hue) {
  return html`<div class=${"meter " + extraClass}
    style=${styleMap({"--meter-fill": fill, "--strategy-h": hue})}><i></i></div>`;
}

const clockLabel = m => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
const dparts = d => d.split("-").map(Number);
const parseDate = d => { const [y, m, day] = dparts(d); return new Date(y, m - 1, day); };
const weekStart = d => {
  const at = parseDate(d);
  at.setDate(at.getDate() - ((at.getDay() + 6) % 7));
  return at.getFullYear() + "-" + (at.getMonth() + 1) + "-" + at.getDate();
};

let LEDGER, ACCOUNT, STRATEGIES, STRAT_BY_KEY, OPEN_POSITIONS, ALL_TRADES, tradesByDate;
let SESSION = {}, TOTALS, SESSIONS, LAST_SESSION, BENCH, BENCH_SYMBOL, DAILY, INTRADAY, LATEST;
let FIRST_IX, LAST_IX;
let STRATEGY_PERIODS = {};
let monthCache = new Map();
let todaySel = null;
let unit = "pct";
let stratRange = "D";

const monthIndex = (y, m) => y * 12 + m;

function statsFor(trades, summary) {
  const profits = trades.map(trade => trade.pnl);
  const n = summary?.n ?? profits.length;
  const wins = summary?.wins ?? profits.filter(value => value > 0).length;
  const losses = n - wins;
  const gross_profit = summary?.gross_profit ?? profits.reduce((sum, value) => sum + Math.max(value, 0), 0);
  const gross_loss = summary?.gross_loss ?? -profits.reduce((sum, value) => sum + Math.min(value, 0), 0);
  const net_pnl = summary?.net_pnl ?? profits.reduce((sum, value) => sum + value, 0);
  return {
    n, wins, losses, net_pnl, gross_profit, gross_loss,
    winRate: n ? wins / n * 100 : 0,
    profitFactor: gross_loss ? gross_profit / gross_loss : Infinity,
    expectancy: n ? net_pnl / n : 0,
    avgWin: wins ? gross_profit / wins : 0,
    avgLoss: losses ? gross_loss / losses : 0,
    best: n ? Math.max(...profits) : 0,
    worst: n ? Math.min(...profits) : 0,
  };
}

function periodFromTrades(key, base, trades) {
  const rows = Object.fromEntries(STRATEGIES.map(st => [st.key, [0, 0]]));
  for (const [strategy_key, group] of Map.groupBy(trades, t => t.strategy_key)) {
    rows[strategy_key] = [group.length, Math.round(group.reduce((sum, t) => sum + t.pnl, 0) * 100) / 100];
  }
  STRATEGY_PERIODS[key] = { base, rows };
}

function monthData(y, m) {
  const key = y + "-" + m;
  if (monthCache.has(key)) return monthCache.get(key);

  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const start = y + "-" + String(m + 1).padStart(2, "0") + "-01";
  const end = y + "-" + String(m + 1).padStart(2, "0") + "-" + daysInMonth;
  const opening = (LEDGER.equityDaily.findLast(row => row.date < start)
    ?? LEDGER.equityDaily.find(row => row.date >= start && row.date <= end))?.equity ?? null;
  const days = [];
  let running = opening;

  for (let d = 1; d <= daysInMonth; d++) {
    const weekday = new Date(y, m, d).getDay();
    const iso = y + "-" + String(m + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
    const hit = LEDGER.days.find(x => x.date === iso);
    const entry = {
      day: d, weekday, weekend: weekday === 0 || weekday === 6,
      pnl: null, trades: 0, wins: 0,
      before: hit ? hit.before : running, iso,
    };
    if (hit) {
      entry.pnl = hit.pnl;
      entry.trades = hit.trades;
      entry.wins = hit.wins;
      running = hit.before + hit.pnl;
    }
    entry.pct = entry.pnl === null || !entry.before ? null : (entry.pnl / entry.before) * 100;
    days.push(entry);
  }

  const traded = days.filter(d => d.pnl !== null);
  const result = {
    y, m, days, opening,
    pnl: Math.round(traded.reduce((s, d) => s + d.pnl, 0) * 100) / 100,
    trades: traded.reduce((s, d) => s + d.trades, 0),
    wins: traded.reduce((s, d) => s + d.wins, 0),
  };
  result.pct = result.opening ? (result.pnl / result.opening) * 100 : null;
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

let accountReadAt = 0, accountObservation;

function derive(ledger, readAt) {
  if (readAt < accountReadAt) {
    const attribution = new Map(ledger.positions.map(pos => [pos.symbol, pos]));
    ledger = { ...ledger, ...accountObservation, positions: accountObservation.positions.map(pos => {
      const history = attribution.get(pos.symbol);
      return history ? { ...pos, strategy_key: history.strategy_key, entered_at: history.entered_at, fills: history.fills } : pos;
    }) };
  }
  const changed = keys => keys.some(key => JSON.stringify(ledger[key]) !== JSON.stringify(LEDGER?.[key]));
  const historyChanged = changed(["trades", "strategies", "days", "periods", "invested", "benchmark", "benchmarkSymbol", "today", "totals", "windows", "equityDaily"]);
  const seriesChanged = changed(["equityDaily", "intraday", "intradayDate", "invested", "today"]);
  LEDGER = ledger;
  if (historyChanged) {
    monthCache.clear();
    STRATEGY_PERIODS = {};

    STRATEGIES = ledger.strategies.map(s => ({
      ...s,
      hue: s.key === "unattributed" ? null : strategyHue(s.key),
    }));
    STRAT_BY_KEY = Object.fromEntries(STRATEGIES.map(x => [x.key, x]));

    ALL_TRADES = ledger.trades.map(t => {
      const [y, m, day] = dparts(t.date);
      return { ...t, y, m: m - 1, day, weekday: parseDate(t.date).getDay() };
    }).reverse();

    tradesByDate = Map.groupBy([...ALL_TRADES].reverse(), t => t.date);

    TOTALS = statsFor(ALL_TRADES, ledger.totals);


    SESSIONS = ledger.days.map(d => ({
      ...d,
      pct: d.before ? (d.pnl / d.before) * 100 : null,
      label: parseDate(d.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
      long: parseDate(d.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric" }),
    }));

    LAST_SESSION = SESSIONS[SESSIONS.length - 1] || { date: ledger.equityDaily.at(-1).date, pnl: 0, before: ledger.equity, pct: 0, trades: 0, wins: 0 };

    periodFromTrades("D", LAST_SESSION.before, tradesByDate.get(LAST_SESSION.date) || []);
    for (const key of ["W", "M"]) {
      const period = ledger.periods[key];
      periodFromTrades(key, period.base, ledger.trades.filter(t => t.date >= period.start && t.date <= ledger.today));
    }
    periodFromTrades("ALL", ledger.invested, ledger.trades);

    const bench = ledger.benchmark;
    const at = i => bench[i].close;
    BENCH_SYMBOL = ledger.benchmarkSymbol;
    BENCH = bench.length > 1
      ? { D: (at(bench.length - 1) / at(bench.length - 2) - 1) * 100, W: ledger.periods.W.benchmarkPct,
          M: ledger.periods.M.benchmarkPct, ALL: (at(bench.length - 1) / at(0) - 1) * 100 }
      : { D: null, W: ledger.periods.W.benchmarkPct, M: ledger.periods.M.benchmarkPct, ALL: bench.length && at(0) ? 0 : null };

    const [ly, lm, lday] = dparts(LAST_SESSION.date);
    LATEST = { y: ly, m: lm - 1, day: lday };

    const funded = ledger.equityDaily.length ? ledger.equityDaily[0].date : LAST_SESSION.date;
    const [fy, fm] = dparts(funded);
    const [ty, tm] = dparts(ledger.today);
    FIRST_IX = monthIndex(fy, fm - 1);
    LAST_IX = Math.max(FIRST_IX, monthIndex(ty, tm - 1));

  }
  ACCOUNT = {
    ...ACCOUNT,
    invested: ledger.invested,
    positionCapPct: ledger.positionCapPct,
    dailyLossLimitPct: ledger.dailyLossLimitPct,
  };

  if (seriesChanged) {
    [DAILY, INTRADAY] = [ledger.equityDaily, ledger.intraday].map((rows, intraday) => {
      const series = rows.map((r, i) => {
        const date = parseDate(intraday ? ledger.intradayDate : r.date);
        return {
          label: intraday ? r.t : date.toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
          long: date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) + (intraday ? ", " + r.t : ""),
          value: Math.round((r.equity - ledger.invested) * 100) / 100,
          before: Math.round(((i ? rows[i - 1].equity : intraday ? r.equity : ledger.invested) - ledger.invested) * 100) / 100,
        };
      });
      series.equityBase = ledger.invested;
      series.todayTip = rows.length > 0 && (intraday ? ledger.intradayDate : rows.at(-1).date) === ledger.today;
      return series;
    });
    if (!INTRADAY.length) INTRADAY = DAILY;
    ACCOUNT.dayOpening = ledger.intraday[0]?.equity || 0;
    ACCOUNT.dayLowEquity = ledger.intraday.length
      ? ratchetLow(ledger.intradayDate, Math.min(...ledger.intraday.map(r => r.equity), ledger.equity))
      : 0;
  }
  applyPulse(ledger, Math.max(readAt, accountReadAt));
  return historyChanged;
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
    iso === LEDGER.today ? "Today" : isLatest() ? "Last session" : "Session";
  document.getElementById("today-date").textContent =
    DAY3[weekday] + " " + todaySel.day + " " + MON3[todaySel.m] + " " + todaySel.y;
  document.getElementById("today-reset").classList.toggle("hidden", isLatest());

  document.getElementById("n-closed").textContent = trades.length;
  document.getElementById("n-open").textContent = OPEN_POSITIONS.length;

  const sum = document.getElementById("today-sum");
  const table = document.getElementById("today-table");

  if (todayTab === "open") {
    render(html`Unrealized <b class=${tone(ACCOUNT.unrealized_pnl)}>${signedMoney(ACCOUNT.unrealized_pnl)}</b>
      <span>Deployed <b>${money(ACCOUNT.deployed)}</b></span><span>Exposure <b>${ACCOUNT.exposurePct.toFixed(1)}%</b></span>
      <span>Largest <b>${ACCOUNT.largestPositionPct.toFixed(1)}%</b> of ${ACCOUNT.positionCapPct.toFixed(1)}% cap</span>`, sum);
    buildTable(table,
      ["Symbol", "Strategy", "Entry", "Last", "Value", "Unreal."],
      OPEN_POSITIONS.map(pos => [
        symbolCell(pos.symbol, pos.side),
        stratCell(pos.strategy_key),
        { t: money(pos.entry), r: true },
        { t: money(pos.last), r: true },
        { t: money(pos.value), r: true, dim: true },
        { t: signedMoney(pos.unrealized_pnl), r: true, cls: tone(pos.unrealized_pnl) },
      ]), 2);
    return;
  }

  if (!cell) {
    render(html`<span>No session</span>`, sum);
    render(html`<tbody><tr><td class="empty">No session on this date.</td></tr></tbody>`, table);
    return;
  }

  if (!trades.length) {
    render(html`<span>No closed trades</span>`, sum);
    render(html`<tbody><tr><td class="empty">No trades closed in this session.</td></tr></tbody>`, table);
    return;
  }

  render(sessionSummary(cell), sum);

  buildTable(table,
    ["Time", "Symbol", "Strategy", "In", "Out", "P&L"],
    trades.map(t => tradeCells(t)), 3);
}

function tradeCells(trade, linked = false) {
  return [
    { t: clockLabel(trade.minute), dim: true },
    symbolCell(trade.symbol, trade.side, linked ? trade : null),
    stratCell(trade.strategy_key),
    { t: money(trade.entry), r: true },
    { t: money(trade.exit), r: true },
    { t: signedMoney(trade.pnl), r: true, cls: tone(trade.pnl) },
  ];
}

function sessionSummary(session) {
  return html`Realised <b class=${tone(session.pnl)}>${signedMoney(session.pnl)}</b>
    <span><b>${session.wins}</b> of <b>${session.trades}</b> won</span>
    <span>Return <b class=${tone(session.pct)}>${signedPct(session.pct)}</b></span>`;
}

function symbolCell(symbol, side, trade) {
  return { symbol, node: html`<span>
    ${trade ? html`<button class="sym linked" type="button" title="Chart this trade"
      @click=${() => openTradeChart(trade.open ? positionTrade(OPEN_POSITIONS.find(pos => pos.symbol === symbol)) : trade, currentView)}>${symbol}</button>`
      : html`<span class="sym">${symbol}</span>`}
    <span class=${"side" + (side === "short" ? " short" : "")}
      title=${side === "short" ? "Short" : "Long"}>${side === "short" ? "S" : "L"}</span>
  </span>` };
}

function stratCell(strategy_key) {
  const strategy = STRAT_BY_KEY[strategy_key];
  return { node: html`<span class="tstrat" title=${strategy.label}>
    ${strategyChip(strategy.hue)}<span>${strategy.short}</span>
  </span>` };
}

function buildTable(table, headers, rows, rightFrom, rowClass) {
  const rowTemplate = (row, index) => {
    const key = Math.max(0, row.findIndex(cell => cell.symbol));
    const lead = headers.findIndex(header => /^(p&l|unrealized)/i.test(header));
    return html`<tr class=${rowClass?.(row, index) || ""}>${row.map((cell, column) => html`
      <td data-label=${headers[column]} class=${[
        cell.r ? "r" : "", cell.cls, cell.dim ? "flat" : "",
        column === key ? "key" : column === (lead < 0 ? row.length - 1 : lead) ? "lead" : "",
      ].filter(Boolean).join(" ")}>${cell.node ?? cell.t}</td>`)}</tr>`;
  };
  const retained = table.id === "pf-open-table" || table.id === "today-table" && todayTab === "open";
  render(html`<thead><tr>${headers.map((header, index) => html`
    <th scope="col" class=${index >= rightFrom ? "r" : ""}>${header}</th>`)}</tr></thead>
    <tbody>${retained ? repeat(rows, row => row.find(cell => cell.symbol).symbol, rowTemplate)
      : rows.map(rowTemplate)}</tbody>`, table);
}

function selectDay(y, m, day) {
  todaySel = { y, m, day };
  renderToday();
  renderCalendar();
}


function renderAccount() {
  const bar = document.getElementById("status");
  bar.classList.toggle("closed", !LEDGER.marketOpen);
  const note = botNote();
  if (note) bar.dataset.bot = "stale";
  else delete bar.dataset.bot;
  render(html`<span class="dot"></span><span class="word" id="st-word">${LEDGER.marketOpen ? "Market open" : "Market closed"}</span>
    <span class="sep"></span><span id="st-session">${LEDGER.marketOpen ? "closes " + LEDGER.nextClose : "opens " + LEDGER.nextOpen}</span>
    <span class="sep"></span><span id="st-strats">Account ${LEDGER.accountNumber} · ${OPEN_POSITIONS.length} positions</span>
    <span class="sep"></span><span class="asof" id="st-asof"></span>
    <span class="sep"></span><span class="bot-note" id="st-bot">${note}</span>`, bar);
  markFeed();
  document.getElementById("chart-funded").textContent =
    "Funded " + money(ACCOUNT.invested) + " · " + LEDGER.funded;
  renderAccountValues("dashboard");
  render(html`<div class="winrate-top"><span class="k">Win rate</span>
    <span class="v" id="v-winrate">${TOTALS.winRate.toFixed(1)}%</span></div>
    <div class="winrate-bar" id="winrate-bar" role="img"
      aria-label=${"Win rate " + TOTALS.winRate.toFixed(1) + " percent: " + TOTALS.wins + " wins and " +
        TOTALS.losses + " losses across " + TOTALS.n + " closed trades"}>
      <span class="w" id="bar-w" style=${styleMap({flex: TOTALS.wins})}></span>
      <span class="l" id="bar-l" style=${styleMap({flex: TOTALS.losses})}></span></div>
    <div class="winrate-legend"><span id="lg-w">${TOTALS.wins} wins</span><span id="lg-l">${TOTALS.losses} losses</span></div>`,
    document.getElementById("performance"));
}

function renderAccountValues(view) {
  const portfolio = view === "portfolio";
  const limit = (value, maximum, digits) => html`<b>${value.toFixed(digits)}%</b> of ${maximum.toFixed(digits)}%`;
  const cap = ["Position cap", portfolio ? "pf-cap" : "v-cap", limit(ACCOUNT.largestPositionPct, ACCOUNT.positionCapPct, 1), "lim",
    portfolio ? "pf-cap-meter" : "m-cap", clamp(ACCOUNT.largestPositionPct / ACCOUNT.positionCapPct, 0, 1)];
  const stats = portfolio ? [
    ["Unrealized", "pf-unrealized-pnl", signedMoney(ACCOUNT.unrealized_pnl), "v " + tone(ACCOUNT.unrealized_pnl)],
    ["Positions", "pf-count", OPEN_POSITIONS.length],
    ["Exposure", "pf-exposure", ACCOUNT.exposurePct.toFixed(1) + "%"],
    ["Largest", "pf-largest", ACCOUNT.largestPositionPct.toFixed(1) + "%"],
    ["Buying power", "pf-risk", money(ACCOUNT.buyingPower)], cap,
  ] : [
    ["Total return", "v-tr", html`${signedMoney(ACCOUNT.totalReturn)}<span class="u">${signedPct(ACCOUNT.rateOfReturn)}</span>`, "v " + tone(ACCOUNT.totalReturn)],
    ["Last session", "v-d24", html`${signedMoney(LAST_SESSION.pnl)}<span class="u">${signedPct(LAST_SESSION.pnl / STRATEGY_PERIODS.D.base * 100)}</span>`, "v " + tone(LAST_SESSION.pnl)],
    ["Open positions", "v-open", OPEN_POSITIONS.length],
    ["Exposure", "v-exposure", ACCOUNT.exposurePct.toFixed(1) + "%"],
    ["Daily loss limit", "v-dll", limit(ACCOUNT.dayDrawdownPct, ACCOUNT.dailyLossLimitPct, 2), "lim", "m-dll",
      Math.max(clamp(ACCOUNT.dayDrawdownPct / ACCOUNT.dailyLossLimitPct, 0, 1), .015)], cap,
  ];
  render(html`<div class="value-row"><span class="label">${portfolio ? "Market value" : "Portfolio"}</span>
    <span class="figure" id=${portfolio ? "pf-value" : "v-portfolio"}>${money(portfolio ? ACCOUNT.deployed : ACCOUNT.portfolio)}</span></div>
    <div class="value-row secondary"><span class="label">Cash</span>
      <span class="figure" id=${portfolio ? "pf-cash" : "v-cash"}>${money(ACCOUNT.cash)}</span></div>
    <div class="stat-grid">${stats.map(([label, id, value, cls, meter, fill]) => html`
      <div class="stat"><span class="k">${label}</span><span class=${cls || "v"} id=${id}>${value}</span>
        ${meter ? html`<div class=${"meter" + (meter === "m-dll" ? " loss" : "")}>
          <i id=${meter} style=${styleMap({"--meter-fill": fill})}></i></div>` : nothing}</div>`)}</div>`,
    document.querySelector("#view-" + view + " .rail .panel-body"));
}

function renderPeriodReturns() {
  document.querySelector(".bench-note").textContent = "vs " + BENCH_SYMBOL;
  render([['Session', 'D'], ['Week', 'W'], ['Month', 'M'], ['Inception', 'ALL']].map(([label, key]) => {
    const period = STRATEGY_PERIODS[key];
    const pnl = Object.values(period.rows).reduce((sum, row) => sum + row[1], 0);
    const pct = period.base ? pnl / period.base * 100 : null;
    return html`<div class="period-cell"><span class="k">${label}</span>
      <span class=${"v " + tone(pct)}>${unit === "pct" ? signedPct(pct) : signedMoney(pnl)}</span>
      <span class="bench">${BENCH_SYMBOL} ${signedPct(BENCH[key])}</span></div>`;
  }), document.getElementById("period-cells"));
}

const SWITCH_STATE = {
  online:  { label: "Online",  hint: "This strategy is selected and can open positions" },
  paused:  { label: "Paused",  hint: "This strategy manages existing positions and opens no new positions" },
  unselected: { label: "Unselected", hint: "This strategy is not selected; existing positions are still managed" },
  unknown: { label: "Unknown", hint: "The bot has not reported its selected strategies" },
  stale: { label: "Last known", hint: "The bot has stopped reporting; this is its last report" },
};

const SESSION_STATE = {
  open:   { label: "Open",   hint: "Inside its entry window — it can open a trade now" },
  closed: { label: "Closed", hint: "Outside its entry window — no new trade will start" },
};

function switchState(strategy_key) {
  const bot = LEDGER.bot || {};
  if (!bot.reported) return "unknown";
  if (!(bot.strategies || []).includes(strategy_key)) return "unselected";
  if (!bot.running) return "stale";
  return (bot.paused || []).includes(strategy_key) ? "paused" : "online";
}

function botNote() {
  const bot = LEDGER.bot || {};
  if (!bot.reported) return "Bot has never reported";
  if (bot.running) return "";
  const since = bot.reportedAgoMinutes;
  return Number.isFinite(since)
    ? "Bot last reported " + (since < 1 ? "under a minute" : Math.round(since) + " min") + " ago"
    : "Bot has stopped reporting";
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

function sessionState(strategy_key) {
  const window = (LEDGER.windows || {})[strategy_key];
  if (!LEDGER.marketOpen || !window) return "closed";
  const now = tradingMinutes();
  return now >= toMinutes(window.from) && now <= toMinutes(window.to) ? "open" : "closed";
}

function windowLabel(strategy_key) {
  const window = (LEDGER.windows || {})[strategy_key];
  return window ? window.from + "–" + window.to + " ET" : "";
}

function stateBadge(kind, key, table, extra) {
  return html`<span class=${"run-state " + kind + " is-" + key}
    title=${table[key].hint + (extra ? " (" + extra + ")" : "")}>${table[key].label}</span>`;
}

function stateBadges(strategy_key) {
  return html`<span class="states">
    ${stateBadge("switch", switchState(strategy_key), SWITCH_STATE)}
    ${stateBadge("session", sessionState(strategy_key), SESSION_STATE, windowLabel(strategy_key))}
  </span>`;
}

function renderStrategies(period) {
  const selected = STRATEGY_PERIODS[period];
  render(STRATEGIES.map(strategy => {
    const [trades, pnl] = selected.rows[strategy.key];
    if (strategy.key === "unattributed" && !trades) return nothing;
    return html`<tr><td><div class="strat" title=${strategy.label}>
      ${strategyChip(strategy.hue)}<span class="name">${strategy.short}</span>
      ${strategy.key === "unattributed" ? nothing : stateBadges(strategy.key)}
    </div></td><td class=${"r num" + (trades ? "" : " flat")}>${trades ? plainNum(trades) : "—"}</td>
    <td class="r pnl-cell"><span class=${"num " + tone(pnl)}>${trades ? signedMoney(pnl) : "—"}</span>
      <span class="sub">${trades ? signedPct(selected.base ? pnl / selected.base * 100 : null) : ""}</span>
    </td></tr>`;
  }), document.getElementById("strat-body"));
}

const space = step => parseFloat(token(step)) || 12;

function axisMetrics(hostId) {
  const size = parseFloat(getComputedStyle(document.getElementById(hostId)).fontSize) || 10;
  return { size, advance: size * 0.62 };
}

const gutterFor = (labels, advance) =>
  Math.ceil(Math.max(...labels.map(text => text.length)) * advance) + 16;

const CHART_PAD = { t: 1, b: 1.8, l: 1.3 };
const TRADE_PAD = { t: 1.3, b: 3.3, l: 0.9 };
const TRADE_PAD_PHONE = { t: 1, b: 3.2, l: 0.5 };

function plotBox(hostId, { minimum, scale, widest }) {
  const host = document.getElementById(hostId);
  const width = host.clientWidth, height = host.clientHeight;
  if (width < minimum || height < minimum) return null;
  const { advance } = axisMetrics(hostId);
  const unit = space("--space-md");
  const pad = {
    t: unit * scale.t, r: gutterFor(widest, advance), b: unit * scale.b, l: unit * scale.l,
  };
  return { host, width, height, advance, pad, plotW: width - pad.l - pad.r, plotH: height - pad.t - pad.b };
}

function paintSvg(box, label, body) {
  box.host.querySelectorAll("svg").forEach(n => n.remove());
  box.host.insertAdjacentHTML("afterbegin",
    '<svg viewBox="0 0 ' + box.width + " " + box.height + '" preserveAspectRatio="none" ' +
    'role="img" aria-label="' + label + '">' + body + "</svg>");
}

function sizeHits(box) {
  Object.assign(box.host.querySelector(".plot-hit").style, {
    left: box.pad.l + "px", top: box.pad.t + "px",
    width: box.plotW + "px", height: box.plotH + "px",
  });
  Object.assign(box.host.querySelector(".axis-hit").style, {
    left: (box.width - box.pad.r) + "px", top: box.pad.t + "px",
    width: box.pad.r + "px", height: box.plotH + "px",
  });
}

const chart = {
  series: null,
  i0: 0, i1: 1,
  yManual: null,
  preset: "ALL",
  custom: false,
};

let geo = null, chartPointer = null;

function presetWindow(range) {
  if (range === "D") return { series: INTRADAY, i0: 0, i1: Math.max(1, INTRADAY.length - 1) };
  const n = DAILY.length;
  const i0 = LEDGER.periods[range]?.equityIndex ?? 0;
  return { series: DAILY, i0, i1: Math.max(i0 + 1, n - 1) };
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
  queueChart();
}

function pressOnly(selector, isPressed) {
  for (const b of document.querySelectorAll(selector)) {
    b.setAttribute("aria-pressed", String(isPressed(b)));
  }
}

function wireGroup(id, key, apply) {
  document.getElementById(id).addEventListener("click", ev => {
    const btn = ev.target.closest("button");
    if (!btn) return;
    const value = btn.dataset[key];
    pressOnly(`#${id} button`, b => b.dataset[key] === value);
    apply(value);
  });
}

function syncRangeButtons() {
  pressOnly("#chart-range button", b => !chart.custom && b.dataset.range === chart.preset);
}

function syncTimeframeButtons() {
  pressOnly("#tc-range button", b => b.dataset.timeframe === TC_STATE.timeframe);
}

function markCustom() {
  if (chart.custom) return;
  chart.custom = true;
  syncRangeButtons();
}

function yTicks(yMin, yMax, divisor) {
  const step = niceStep((yMax - yMin) / divisor);
  const ticks = [];
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) ticks.push(v);
  return ticks;
}

function hoveredIndex(geo, clientX) {
  return clamp(Math.round(geo.indexAt(clientX)), geo.lo, geo.hi);
}

function niceStep(raw) {
  const mag = Math.pow(10, Math.floor(Math.log10(Math.abs(raw) || 1)));
  const norm = raw / mag;
  return (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
}

function indexBounds(i0, i1, length) {
  return [clamp(Math.floor(i0), 0, length - 1), clamp(Math.ceil(i1), 0, length - 1)];
}

function chartWindow() {
  const s = chart.series;
  if (!s || !s.length) return null;
  const [lo, hi] = indexBounds(chart.i0, chart.i1, s.length);
  const period = !chart.custom && LEDGER.periods[chart.preset];
  const baseline = period?.base != null ? period.base - s.equityBase : s[lo].before;
  const visible = [];
  for (let i = lo; i <= hi; i++) visible.push({ i, p: s[i], y: s[i].value - baseline });
  return { s, lo, hi, baseline, visible, last: visible[visible.length - 1] };
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
    w.visible[0].p.label + " – " + w.last.p.label + (chart.series === INTRADAY && LEDGER.intradayDate ? " · " + dayOf(LEDGER.intradayDate) : "");

  document.getElementById("chart-table").innerHTML =
    "<table><caption>Cumulative profit and loss across the visible window</caption><tbody>" +
    w.visible.map(v => "<tr><th scope='row'>" + v.p.long + "</th><td>" + signedMoney(v.y) + "</td></tr>").join("") +
    "</tbody></table>";
}

function tickLabels(w) {
  const ys = w.visible.map(v => v.y).concat([0]);
  const reach = Math.max(Math.abs(Math.min(...ys)), Math.abs(Math.max(...ys))) * 1.14;
  return ["−" + usd0.format(reach || 1)];
}

function coalesce(draw) {
  let frame = 0;
  return () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(draw);
  };
}

const same = (a, b) => a.length === b.length && a.every((value, i) => Object.is(value, b[i]));

let chartOutput = [];
const queueChart = coalesce(() => {
  const host = document.getElementById("chart-host");
  const output = [
    chart.series, chart.series?.at(-1)?.value, chart.i0, chart.i1,
    chart.yManual?.min, chart.yManual?.max,
    unit, resolvedTheme(), host.clientWidth, host.clientHeight,
  ];
  if (same(output, chartOutput)) return;
  chartOutput = output;
  drawChart();
});

const queueTradeChart = coalesce(() => drawTradeChart());

function drawChart() {
  const w = chartWindow();
  if (!w) return;
  paintChartHero(w);
  if (onPhone()) return;

  const box = plotBox("chart-host", { minimum: 60, scale: CHART_PAD, widest: tickLabels(w) });
  if (!box) return;
  const { width, height, pad: PAD, plotW, plotH } = box;

  const { lo, hi, baseline, visible } = w;

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
    const rect = document.getElementById("chart-host").getBoundingClientRect();
    return i0 + ((clientX - rect.left - PAD.l) / plotW) * (i1 - i0);
  };
  geo = { width, height, plotW, plotH, px, py, indexAt, yMin, yMax, baseline, lo, hi };

  const zeroY = clamp(py(0), PAD.t, PAD.t + plotH);
  const line = visible.map((v, k) => (k ? "L" : "M") + px(v.i).toFixed(2) + " " + py(v.y).toFixed(2)).join(" ");
  const area = line +
    " L" + px(visible[visible.length - 1].i).toFixed(2) + " " + zeroY.toFixed(2) +
    " L" + px(visible[0].i).toFixed(2) + " " + zeroY.toFixed(2) + " Z";

  const ticks = yTicks(yMin, yMax, 3.2);

  const gridSvg = ticks.map(t =>
    '<line class="' + (Math.abs(t) < 1e-9 ? "grid-zero" : "grid") + '" x1="' + PAD.l +
    '" y1="' + py(t).toFixed(2) + '" x2="' + (width - PAD.r) + '" y2="' + py(t).toFixed(2) + '"' +
    (Math.abs(t) < 1e-9 ? ' stroke-dasharray="3 3"' : "") + "/>" +
    '<text x="' + (width - PAD.r + 8) + '" y="' + (py(t) + 3.5).toFixed(2) + '">' +
    (t >= 0 ? "" : "−") + usd0.format(Math.abs(t)) + "</text>"
  ).join("");

  const count = visible.length;
  const every = Math.max(1, Math.ceil(count / 6));
  const xSvg = visible.map((v, k) =>
    (k % every === 0 || k === count - 1)
      ? '<text x="' + clamp(px(v.i), PAD.l + 14, width - PAD.r - 14).toFixed(2) + '" y="' + (height - 6) +
        '" text-anchor="middle">' + v.p.label + "</text>"
      : ""
  ).join("");

  const last = visible[visible.length - 1];
  const lastTone = last.y >= 0 ? "mark-gain" : "mark-loss";

  paintSvg(box, "Cumulative profit and loss across the visible window",
      "<defs>" +
        '<linearGradient id="gGain" x1="0" x2="0" y1="' + PAD.t + '" y2="' + zeroY + '" gradientUnits="userSpaceOnUse">' +
          '<stop class="g0" offset="0"/><stop class="g1" offset="1"/></linearGradient>' +
        '<linearGradient id="gLoss" x1="0" x2="0" y1="' + zeroY + '" y2="' + (height - PAD.b) + '" gradientUnits="userSpaceOnUse">' +
          '<stop class="g0" offset="0"/><stop class="g1" offset="1"/></linearGradient>' +
        '<clipPath id="cPlot"><rect x="' + PAD.l + '" y="' + PAD.t + '" width="' + plotW + '" height="' + plotH + '"/></clipPath>' +
        '<clipPath id="cPos"><rect x="0" y="0" width="' + width + '" height="' + Math.max(0, zeroY) + '"/></clipPath>' +
        '<clipPath id="cNeg"><rect x="0" y="' + zeroY + '" width="' + width + '" height="' + Math.max(0, height - zeroY) + '"/></clipPath>' +
      "</defs>" +
      gridSvg +
      '<g clip-path="url(#cPlot)">' +
        '<path class="area-gain" d="' + area + '" clip-path="url(#cPos)"/>' +
        '<path class="area-loss" d="' + area + '" clip-path="url(#cNeg)"/>' +
        '<path class="series mark-gain" d="' + line + '" ' +
          'vector-effect="non-scaling-stroke" clip-path="url(#cPos)"/>' +
        '<path class="series mark-loss" d="' + line + '" ' +
          'vector-effect="non-scaling-stroke" clip-path="url(#cNeg)"/>' +
        '<line class="crosshair" id="cross" x1="0" y1="' + PAD.t + '" x2="0" y2="' + (PAD.t + plotH) + '" ' +
          'vector-effect="non-scaling-stroke" opacity="0"/>' +
        '<circle class="dot ' + lastTone + '" id="crossDot" r="4.5" opacity="0"/>' +
        '<circle class="dot ' + lastTone + '" cx="' + px(last.i).toFixed(2) + '" cy="' + py(last.y).toFixed(2) + '" r="4.5"/>' +
      "</g>" +
      xSvg
  );

  sizeHits(box);
  if (chartPointer !== null) chartHover({ clientX: chartPointer });
}


const ZOOM_STEP = 1.14;
const SCALE_TRAVEL_PX = 180;
const TAP_TRAVEL_PX = 8;

function wirePanZoom(options) {
  const { plot, axis, view, geometry, spanMin, spanMax, scaleMin, clampWindow, redraw, onReset } = options;
  const { onHover, onLeave, pinchable } = options;
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
  if (!N) return;
  const end = Math.max(1, N - 1);
  const span = Math.min(Math.max(chart.i1 - chart.i0, 3), end);
  chart.i0 = clamp(chart.i0, 0, end - span);
  chart.i1 = chart.i0 + span;
}

function chartHover(event) {
  chartPointer = event.clientX;
  const tip = document.getElementById("chart-tip");
  const svg = document.getElementById("chart-host").querySelector("svg");
  if (!svg || !geo) return;
  const i = hoveredIndex(geo, event.clientX);
  const point = chart.series[i];
  const y = point.value - geo.baseline;
  const cross = svg.querySelector("#cross");
  const dot = svg.querySelector("#crossDot");

  cross.setAttribute("x1", geo.px(i)); cross.setAttribute("x2", geo.px(i));
  cross.setAttribute("opacity", "1");
  dot.setAttribute("cx", geo.px(i)); dot.setAttribute("cy", geo.py(y));
  dot.setAttribute("class", "dot " + (y >= 0 ? "mark-gain" : "mark-loss"));
  dot.setAttribute("opacity", "1");

  const equityAtStart = chart.series.equityBase + geo.baseline;
  render(html`<span class="tt-k">${point.long}</span><span class=${"tt-v " + tone(y)}>${signedMoney(y)}</span>
    <span class="tt-row"><span>from view start</span><span>${signedPct(y / equityAtStart * 100)}</span></span>`, tip);
  tip.classList.add("on");
  tip.style.left = clamp(geo.px(i), 80, geo.width - 80) + "px";
  tip.style.top = Math.max(52, geo.py(y)) + "px";
}

function chartLeave() {
  chartPointer = null;
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
    spanMax: () => Math.max(1, chart.series.length - 1),
    scaleMin: 1e-3,
    clampWindow: clampChartWindow,
    redraw: () => { markCustom(); queueChart(); },
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

  const peak = Math.max(1, ...md.days.filter(d => d.pnl !== null).map(d => Math.abs(d.pnl)));

  document.getElementById("cal-month").textContent = MONTHS[calM] + " " + calY;

  const ix = monthIndex(calY, calM);
  document.getElementById("cal-prev").disabled = ix <= FIRST_IX;
  document.getElementById("cal-next").disabled = ix >= LAST_IX;

  document.getElementById("sum-trades").textContent = md.trades ? plainNum(md.trades) : "—";
  document.getElementById("sum-wins").textContent = md.trades ? plainNum(md.wins) : "—";

  for (const [id, value] of [["sum-pnl", signedMoney(md.pnl)], ["sum-pct", signedPct(md.pct)]]) {
    const element = document.getElementById(id);
    element.textContent = md.trades ? value : "—";
    element.className = "v " + tone(md.trades ? md.pnl : 0);
  }

  render(rows.map(row => html`<tr>
    ${row.cells.map(cell => html`<td>${dayCell(cell, peak, tip)}</td>`)}
    <td><div class=${"cell total " + (row.any ? row.pnl >= 0 ? "gain" : "loss" : "")}>
      <span class="d">Week</span><span class=${"p " + (row.any ? tone(row.pnl) : "flat")}>
        ${row.any ? signedMoney(row.pnl) : "—"}</span><span class="q">${row.any ? signedPct(row.pct) : ""}</span>
    </div></td></tr>`), body);
}


function dayCell(cell, peak, tip) {
  if (!cell) return html`<div class="cell out"></div>`;
  if (cell.pnl === null) return html`<div class="cell idle"><span class="d">${cell.day}</span><span class="p">—</span></div>`;
  const show = target => {
    const box = target.getBoundingClientRect();
    const ref = tip.offsetParent.getBoundingClientRect();
    render(html`<span class="tt-k">${DAY3[cell.weekday]} ${cell.day} ${MON3[calM]} ${calY}</span>
      <span class=${"tt-v " + tone(cell.pnl)}>${signedMoney(cell.pnl)}</span>
      ${[["Return", signedPct(cell.pct)], ["Trades", cell.trades], ["Wins", cell.wins + " of " + cell.trades]].map(([label, value]) =>
        html`<span class="tt-row"><span>${label}</span><span>${value}</span></span>`)}`, tip);
    tip.classList.add("on");
    tip.style.left = clamp(box.left - ref.left + box.width / 2, 76, ref.width - 76) + "px";
    tip.style.top = Math.max(88, box.top - ref.top - 6) + "px";
  };

  const hide = () => {
    tip.classList.remove("on");
    tip.style.left = "0px";
    tip.style.top = "0px";
  };

  return html`<div class=${"cell has " + (cell.pnl >= 0 ? "gain" : "loss") +
    (calY === todaySel.y && calM === todaySel.m && cell.day === todaySel.day ? " sel" : "")}
    tabindex="0" role="button" style=${styleMap({"--depth": (Math.abs(cell.pnl) / peak).toFixed(4)})}
    @click=${() => selectDay(calY, calM, cell.day)}
    @keydown=${event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectDay(calY, calM, cell.day); } }}
    @pointerenter=${event => show(event.currentTarget)} @focus=${event => show(event.currentTarget)}
    @pointerleave=${hide} @blur=${hide}
    aria-label=${DAY3[cell.weekday] + " " + cell.day + " " + MON3[calM] + ", " + signedMoney(cell.pnl) +
      ", " + signedPct(cell.pct) + ", " + cell.wins + " of " + cell.trades + " trades won"}>
    <span class="d">${cell.day}</span><span class=${"p " + tone(cell.pnl)}>${signedMoney(cell.pnl)}</span>
    <span class="q">${signedPct(cell.pct)}</span></div>`;
}


function renderPortfolio() {
  renderAccountValues("portfolio");

  render(STRATEGIES.map(strategy => {
    const held = OPEN_POSITIONS.filter(position => position.strategy_key === strategy.key);
    if (!held.length) return nothing;
    const value = held.reduce((sum, position) => sum + position.value, 0);
    return html`<div class="alloc-row"><div class="nm">
      ${strategyChip(strategy.hue)}<span>${strategy.short}</span>
      <span class="eyebrow">${held.length}${held.length === 1 ? " position" : " positions"}</span></div>
      <div class="amt">${money(value)}<span class="pc">${(value / ACCOUNT.deployed * 100).toFixed(0)}%</span></div>
      ${meterBar(value / ACCOUNT.deployed, strategy.hue ? "strategy" : "plain", strategy.hue)}</div>`;
  }), document.getElementById("pf-alloc"));

  render(repeat(OPEN_POSITIONS, position => position.symbol, position => html`
    <div class=${"weight-row" + (position.weight >= ACCOUNT.positionCapPct - .2 ? " near" : "")}>
      <div class="nm">${position.symbol}</div><div class="gap">${position.weight.toFixed(1)}% · ${money(position.value)}</div>
      ${meterBar(clamp(position.weight / ACCOUNT.positionCapPct, .03, 1))}</div>`), document.getElementById("pf-weights"));

  document.getElementById("pf-open-note").textContent =
    OPEN_POSITIONS.length + " held · " + money(ACCOUNT.deployed);

  buildTable(document.getElementById("pf-open-table"),
    ["Symbol", "Strategy", "Opened", "Quantity", "Entry", "Last", "Value", "Weight", "Unrealized"],
    OPEN_POSITIONS.map(pos => [
      symbolCell(pos.symbol, pos.side, positionTrade(pos)),
      stratCell(pos.strategy_key),
      { t: pos.entered_at ? dayOf(pos.entered_at) : "—", dim: true },
      { t: String(pos.quantity), r: true, dim: true },
      { t: money(pos.entry), r: true },
      { t: money(pos.last), r: true },
      { t: money(pos.value), r: true },
      { t: pos.weight.toFixed(1) + "%", r: true, dim: true },
      { t: signedMoney(pos.unrealized_pnl) + "  " + signedPct(pos.unrealized_pnl_percent), r: true, cls: tone(pos.unrealized_pnl) },
    ]), 3);

  const prev = [...SESSIONS].reverse().find(session => session.date !== LEDGER.today);
  const trades = prev ? tradesByDate.get(prev.date) || [] : [];

  document.getElementById("pf-prev-date").textContent = prev ? prev.long : "—";
  render(prev ? sessionSummary(prev) : html`<span>No earlier session yet</span>`, document.getElementById("pf-prev-sum"));

  buildTable(document.getElementById("pf-prev-table"),
    ["Time", "Symbol", "Strategy", "In", "Out", "P&L"],
    trades.map(t => tradeCells(t, true)), 3);
}


function tile(k, v, cls, sub) {
  return html`<div class="tile"><span class="k">${k}</span><span class=${"v " + (cls || "")}>${v}</span>
    ${sub ? html`<span class="sub">${sub}</span>` : nothing}</div>`;
}

function renderHistory() {
  document.getElementById("hs-span").textContent =
    SESSIONS.length ? SESSIONS[0].long + " – " + SESSIONS.at(-1).long : "No closed trades";

  const L = TOTALS;
  const tiles = document.getElementById("hs-tiles");
  render([
    tile("Realised P&L", signedMoney(L.net_pnl), tone(L.net_pnl), "closed round trips"),
    tile("Trades", plainNum(L.n), "", SESSIONS.length + " sessions"),
    tile("Win rate", L.winRate.toFixed(1) + "%", "", L.wins + "W / " + L.losses + "L"),
    tile("Profit factor", ratio(L.profitFactor), Number.isFinite(L.profitFactor) ? tone(L.profitFactor - 1) : "flat", "gross profit ÷ gross loss"),
    tile("Expectancy", signedMoney(L.expectancy), tone(L.expectancy), "per trade"),
    tile("Average win", signedMoney(L.avgWin), "pos", plainNum(L.wins) + " trades"),
    tile("Average loss", signedMoney(-L.avgLoss), "neg", plainNum(L.losses) + " trades"),
    tile("Payoff ratio", ratio(L.avgWin / L.avgLoss), "", "avg win ÷ avg loss"),
    tile("Best trade", signedMoney(L.best), "pos"),
    tile("Worst trade", signedMoney(L.worst), "neg"),
  ], tiles);

  const peak = Math.max(...SESSIONS.map(m => Math.abs(m.pnl)));
  render(SESSIONS.map(session => {
    const fill = html`<div class="fill" title=${session.long + " · " + signedMoney(session.pnl)}
      style=${styleMap({height: Math.max(2, Math.abs(session.pnl) / peak * 100) + "%"})}></div>`;
    return html`<div class="ybar"><div class="track"><div class="up">${session.pnl >= 0 ? fill : nothing}</div>
      <div class="down">${session.pnl < 0 ? fill : nothing}</div></div><div class="lab">${session.label}</div></div>`;
  }), document.getElementById("hs-strip"));

  buildTable(document.getElementById("hs-sessions"),
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
      const st2 = statsFor(ALL_TRADES.filter(t => t.strategy_key === st.key));
      return [
        stratCell(st.key),
        { t: plainNum(st2.n), r: true, dim: true },
        { t: st2.n ? st2.winRate.toFixed(1) + "%" : "—", r: true, dim: true },
        { t: st2.n ? ratio(st2.profitFactor) : "—", r: true, cls: Number.isFinite(st2.profitFactor) ? tone(st2.profitFactor - 1) : "flat" },
        { t: signedMoney(st2.net_pnl), r: true, cls: tone(st2.net_pnl) },
      ];
    }), 1);

  const fs = document.getElementById("f-strategy");
  if (fs.options.length === 1) {
    for (const st of STRATEGIES) fs.append(new Option(st.short, st.key));
  }
  const sessions = document.getElementById("f-session");
  const selected = sessions.value;
  sessions.replaceChildren(new Option("All", ""),
    ...[...SESSIONS].reverse().map(session => new Option(session.long, session.date)));
  sessions.value = SESSIONS.some(session => session.date === selected) ? selected : "";

  renderLog();
}

function openedCell(trade) {
  const [, month, day] = dparts(dateOf(trade.entered_at));
  const overnight = dateOf(trade.entered_at) !== trade.date;
  return { dim: true, node: html`<span class="in-time"
    title=${overnight ? "Opened " + day + " " + MON3[month - 1] + ", held to the exit shown" : nothing}>
    <span>${clockOf(trade.entered_at)}</span>${overnight ? html`<span class="in-day">${day} ${MON3[month - 1]}</span>` : nothing}
  </span>` };
}

function renderLog() {
  const strategy_key = document.getElementById("f-strategy").value;
  const side = document.getElementById("f-side").value;
  const result = document.getElementById("f-result").value;
  const session = document.getElementById("f-session").value;
  const symbol = document.getElementById("f-symbol").value.trim().toUpperCase();

  const rows = ALL_TRADES.filter(t =>
    (!strategy_key || t.strategy_key === strategy_key) &&
    (!side || t.side === side) &&
    (!result || (result === "win" ? t.pnl > 0 : t.pnl <= 0)) &&
    (!session || session === t.date) &&
    (!symbol || t.symbol.includes(symbol))
  );

  const st = statsFor(rows);
  document.getElementById("hs-count").textContent = rows.length === ALL_TRADES.length
    ? plainNum(rows.length) + " trades"
    : plainNum(rows.length) + " of " + plainNum(ALL_TRADES.length) + " · " +
      signedMoney(st.net_pnl) + " · " + st.winRate.toFixed(1) + "% won";

  const table = document.getElementById("hs-log");

  if (!rows.length) {
    render(html`<tbody><tr><td class="empty">No trades match these filters.</td></tr></tbody>`, table);
    return;
  }

  const days = [...new Set(rows.map(t => t.date))].sort();
  const shade = rows.map(t => days.indexOf(t.date) % 2 === 1);

  const weeks = rows.map(t => weekStart(t.date));

  buildTable(table,
    ["Date", "In time", "Out time", "Symbol", "Strategy", "Entry", "Exit", "P&L"],
    rows.map(t => [
      { t: DAY3[t.weekday] + " " + t.day + " " + MON3[t.m] + " " + String(t.y).slice(2), cls: "log-date" },
      openedCell(t),
      ...tradeCells(t, true),
    ]), 5, (_row, index) => [
      shade[index] ? "band" : "",
      index && weeks[index] !== weeks[index - 1] ? "week-edge" : "",
    ].filter(Boolean).join(" "));
}



const blankTradeState = timeframe => ({ timeframe, bars: null, averages: [] });
let TRADE = null, TC_STATE = blankTradeState("5Min");
let TC_LEVELS = null, TC_COTRADES = [];
const TC_VIEW = { i0: 0, i1: 0, yManual: null, custom: false };
let TC_ORIGIN = "history";

const TC_SHOW = { range: true, stop: true, targets: true };

function selectTradeState(timeframe) {
  TC_STATE = blankTradeState(timeframe);
  TC_LEVELS = null;
  Object.assign(TC_VIEW, { i0: 0, i1: 0, yManual: null, custom: false });
  document.getElementById("tc-host").querySelectorAll("svg, .tc-mark").forEach(n => n.remove());
  document.getElementById("tc-tip").classList.remove("on");
  render(nothing, document.getElementById("tc-table"));
  paintRail();
}

function clockOf(iso) {
  const at = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/New_York", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(at);
}

function dateOf(iso) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(iso));
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
  if (!position.entered_at) return null;
  return {
    symbol: position.symbol,
    side: position.side,
    strategy_key: position.strategy_key,
    entry: position.entry,
    exit: position.last,
    pnl: position.unrealized_pnl,
    quantity: position.quantity,
    entered_at: position.entered_at,
    date: LEDGER.today,
    minute: tradingMinutes(),
    duration_minutes: Math.max(0,
      Math.floor((Date.now() - Date.parse(position.entered_at)) / 60000)),
    fills: position.fills || [],
    open: true,
  };
}

async function openTradeChart(trade, from) {
  TRADE = trade;
  if (from) TC_ORIGIN = from;
  selectTradeState("5Min");
  TC_COTRADES = ALL_TRADES.filter(t => t.symbol === trade.symbol).reverse();
  if (trade.open) TC_COTRADES.push(trade);
  syncTimeframeButtons();
  document.getElementById("chart-back").textContent =
    TC_ORIGIN === "portfolio" ? "← Portfolio" : "← Trade log";
  switchView("chart");
  paintTradeFacts();
  paintStepper();
  loadTradeLevels();
  await loadTradeBars();
}

async function loadTradeLevels() {
  const state = TC_STATE;
  const t = TRADE;
  if (t.strategy_key === "unattributed") { TC_LEVELS = {}; paintRail(); return; }
  const query = new URLSearchParams({
    symbol: t.symbol, strategy_key: t.strategy_key, side: t.side, entry: String(t.entry), opened: dateOf(t.entered_at),
  });
  try {
    const response = await fetch("/api/levels?" + query, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const payload = await response.json();
    if (TC_STATE !== state) return;
    TC_LEVELS = payload.data;
  } catch {
    if (TC_STATE !== state) return;
    TC_LEVELS = {};
  }
  paintRail();
  if (TC_STATE.bars) queueTradeChart();
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

function paintRail() {
  render((TC_STATE.averages || []).map(({length, values}, index) => {
    const enough = values.some(value => value !== null);
    return railToggle("sma" + length, "SMA " + length, index, enough,
      enough ? "" : "Not enough bars at this size");
  }), document.getElementById("tc-smas"));
  const has = TC_LEVELS || {};
  render([
    railToggle("range", "Opening range", null, Boolean(has.range), has.range ? "" : "Breakout trades only"),
    railToggle("stop", "Stop", null, has.stop !== undefined, has.stop !== undefined ? "" : "Not reconstructable"),
    railToggle("targets", "Targets", null, Boolean(has.targets), has.targets ? "" : "Breakout trades only"),
  ], document.getElementById("tc-overlays"));
  document.getElementById("tc-rail-note").textContent =
    has.strategy_key ? "Stop and targets are reconstructed from the rules." : "";
}

function averageColor(index) {
  return SESSION.sma_colors[index % SESSION.sma_colors.length];
}

function railToggle(key, label, averageIndex, enabled, why) {
  return html`<label class=${"tc-toggle" + (enabled ? "" : " off")} title=${why || nothing}>
    <input type="checkbox" .checked=${enabled && TC_SHOW[key]} ?disabled=${!enabled}
      @change=${event => { TC_SHOW[key] = event.target.checked; queueTradeChart(); }}>
    <span class=${"tc-swatch" + (averageIndex === null ? " plain" : "")}
      style=${styleMap({"--sma-h": averageIndex === null ? undefined : "var(" + averageColor(averageIndex) + ")"})}></span>
    <span>${label}</span></label>`;
}

function paintTradeFacts() {
  const t = TRADE;
  document.getElementById("tc-title").textContent = t.symbol;
  const strategy = STRAT_BY_KEY[t.strategy_key];
  document.getElementById("tc-sub").textContent =
    (strategy ? strategy.short : t.strategy_key) + " · " + (t.side === "short" ? "Short" : "Long") +
    (t.open ? " · Open" : "");

  const openNote = document.getElementById("tc-open-note");
  openNote.textContent = t.open
    ? "This position is still open. The second mark is the current price, not an exit, and "
      + "the figure beside it is unrealized P&L."
    : "";
  openNote.hidden = !t.open;

  const held = t.duration_minutes >= 1440
    ? Math.round(t.duration_minutes / 1440) + "d"
    : t.duration_minutes >= 60 ? Math.floor(t.duration_minutes / 60) + "h " + (t.duration_minutes % 60) + "m" : t.duration_minutes + "m";

  const facts = [
    ["Entry", money(t.entry), dayOf(t.entered_at) + " " + clockOf(t.entered_at)],
    [t.open ? "Last" : "Exit", money(t.exit),
      t.open ? "still open" : dayLabel(t.date) + " " + clockLabel(t.minute)],
    ["Quantity", plainNum(Math.round(t.quantity * 100) / 100), ""],
    [t.open ? "Held so far" : "Held", held, ""],
    [t.open ? "Unrealized" : "P&L", signedMoney(t.pnl),
      signedPct(((t.exit - t.entry) / t.entry) * 100 * (t.side === "short" ? -1 : 1))],
  ];
  render(facts.map(([label, value, sub]) => html`<div class="fact"><span class="k">${label}</span>
    <span class=${"v num" + (label === "P&L" ? " " + tone(t.pnl) : "")}>${value}</span>
    ${sub ? html`<span class="s">${sub}</span>` : nothing}</div>`), document.getElementById("tc-facts"));
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
  const state = TC_STATE;
  const t = TRADE;
  tcState("Loading " + document.querySelector("#tc-range [aria-pressed=true]").textContent.trim().toLowerCase() + " bars…");
  const query = new URLSearchParams({
    symbol: t.symbol, timeframe: TC_STATE.timeframe, opened: dateOf(t.entered_at), closed: t.date,
  });
  try {
    const response = await fetch("/api/bars?" + query, { headers: { Accept: "application/json" } });
    if (TC_STATE !== state) return;
    if (response.status === 401) { location.replace("/login"); return; }
    if (!response.ok) throw new Error("HTTP " + response.status);
    const payload = await response.json();
    if (TC_STATE !== state) return;
    TC_STATE.averages = payload.data.averages;
    TC_STATE.bars = payload.data.bars.map(b => ({ ...b, x: barStamp(b.t) }));
    const from = barStamp(payload.data.displayFrom);
    TC_STATE.first = Math.max(0, TC_STATE.bars.findIndex(b => b.x >= from));
  } catch (error) {
    if (TC_STATE !== state) return;
    TC_STATE.bars = null;
    tcState("Historical bars could not be read. Try again in a moment.");
    return;
  }
  if (!TC_STATE.bars.length) {
    tcState("No historical bars are available for this window.");
    return;
  }
  tcState("");
  setTradeView(0, Math.max(1, TC_STATE.bars.length - TC_STATE.first));
  paintRail();
  paintTradeTable();
  queueTradeChart();
}

function drawTradeChart() {
  const bars = TC_STATE.bars;
  if (!bars || !bars.length) return;
  const reach = Math.max(...bars.map(b => b.h));
  const box = plotBox("tc-host", {
    minimum: 80,
    scale: onPhone() ? TRADE_PAD_PHONE : TRADE_PAD,
    widest: [money(reach)],
  });
  if (!box) return;
  const { host, width, height, advance, pad: TC_PAD, plotW, plotH } = box;

  const t = TRADE;

  const averages = {};
  for (const { length, values } of TC_STATE.averages) {
    if (TC_SHOW["sma" + length] && bars.length >= length) {
      averages[length] = values;
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
  const inIndex = nearest(barStamp(t.entered_at));
  const outIndex = nearest(stampOf(t.date, t.minute));

  const i0 = TC_VIEW.i0, i1 = TC_VIEW.i1;
  const [lo, hi] = indexBounds(i0, i1, all.length);
  const visible = all.slice(lo, hi + 1);

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
    yMin = Math.min(...visible.map(b => b.l), ...extra);
    yMax = Math.max(...visible.map(b => b.h), ...extra);
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
    px, py, width, height, bars: all,
    lo, hi, yMin, yMax, plotW, plotH, indexAt, count: all.length,
  };

  const ticks = yTicks(yMin, yMax, 4.2);
  const grid = ticks.map(v =>
    '<line class="grid" x1="' + TC_PAD.l + '" y1="' + py(v).toFixed(2) + '" x2="' + (width - TC_PAD.r) +
    '" y2="' + py(v).toFixed(2) + '"/>' +
    '<text x="' + (width - TC_PAD.r + 8) + '" y="' + (py(v) + 3.5).toFixed(2) + '">' +
    money(v) + "</text>").join("");

  const LABEL_WIDTH = advance * 13;
  const roomFor = Math.max(2, Math.floor(plotW / LABEL_WIDTH));

  const firstOf = key => {
    const seen = new Map();
    visible.forEach((b, k) => { const at = key(b.t); if (!seen.has(at)) seen.set(at, k + lo); });
    return seen;
  };
  const daily = TC_STATE.timeframe === "1Day";
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
    const b = visible[i - lo];
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

  const CHAR = advance, GAP = 10;
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
    if (previous.clamped) kept[kept.length - 1] = candidate;
  }

  const rules = visible.map((_bar, k) => {
    const i = k + lo;
    return boundary.has(i) && i > lo
      ? '<line class="grid" x1="' + px(i - 0.5).toFixed(2) + '" y1="' + TC_PAD.t + '" x2="' +
        px(i - 0.5).toFixed(2) + '" y2="' + (TC_PAD.t + plotH) + '"/>'
      : "";
  }).join("");

  const axis = rules + kept.map(candidate =>
    candidate.lines.map((line, row) =>
      '<text class="' + (candidate.named ? "named" : "") + '" x="' + candidate.x.toFixed(2) +
      '" y="' + (height - 15 + row * 11) + '" text-anchor="middle">' + line + "</text>").join("")
  ).join("");

  const smaEnds = [];
  const smaLines = TC_STATE.averages.map(({ length }, index) => {
    const values = averages[length];
    if (!values) return "";
    let path = "", lastY = null;
    visible.forEach((_, k) => {
      const i = k + lo;
      const v = values[i + first];
      if (v === null || v === undefined) return;
      path += (path ? "L" : "M") + px(i).toFixed(2) + " " + py(v).toFixed(2) + " ";
      lastY = py(v);
    });
    if (!path) return "";
    if (lastY !== null) smaEnds.push({ y: lastY, index, length });
    return '<path class="sma" data-sma="' + index + '" d="' + path.trim() + '"/>';
  }).join("");

  smaEnds.sort((a, b) => a.y - b.y);
  smaEnds.forEach((end, i) => {
    if (i && end.y - smaEnds[i - 1].y < 12) end.y = smaEnds[i - 1].y + 12;
  });
  const smaLabels = smaEnds.map(end =>
    '<text class="sma-label halo" data-sma="' + end.index + '" x="' + (width - TC_PAD.r - 4) +
    '" y="' + (end.y - 3).toFixed(2) + '" text-anchor="end">' + end.length + "</text>").join("");

  const band = (top, bottom) =>
    '<rect class="band" x="' + TC_PAD.l + '" y="' + Math.min(top, bottom).toFixed(2) + '" width="' + plotW +
    '" height="' + Math.abs(bottom - top).toFixed(2) + '"/>';
  let overlays = "", overlayText = "";
  const named = (y, mark, text, dash) => {
    overlays +=
      '<line class="level ' + mark + '" x1="' + TC_PAD.l + '" y1="' + y.toFixed(2) + '" x2="' +
      (width - TC_PAD.r) + '" y2="' + y.toFixed(2) + '" stroke-dasharray="' + dash + '"/>';
    overlayText +=
      '<text class="level-label halo ' + mark + '" x="' + (TC_PAD.l + 5) + '" y="' + (y - 4).toFixed(2) +
      '">' + text + "</text>";
  };

  if (TC_SHOW.range && levels.range) {
    overlays += band(py(levels.range.high), py(levels.range.low));
    named(py(levels.range.high), "axis", "Range high " + money(levels.range.high), "4 3");
    named(py(levels.range.mid), "axis", "Range mid " + money(levels.range.mid), "2 4");
    named(py(levels.range.low), "axis", "Range low " + money(levels.range.low), "4 3");
  }
  if (TC_SHOW.stop && levels.stop !== undefined) {
    named(py(levels.stop), "mark-loss", "Stop " + money(levels.stop), "5 4");
  }
  if (TC_SHOW.targets && levels.targets) {
    levels.targets.forEach((value, i) => {
      named(py(value), "mark-gain", "Target " + (i + 1) + " " + money(value), "1 4");
    });
  }

  const bodyW = Math.max(1.5, Math.min(9, step * 0.62));
  const barMarks = visible.map((b, k) => {
    const i = k + lo;
    const up = b.c >= b.o;
    const mark = up ? "gain" : "loss";
    const x = px(i);
    const top = py(Math.max(b.o, b.c)), bottom = py(Math.min(b.o, b.c));
    const h = Math.max(1, bottom - top);
    return '<line class="wick mark-' + mark + '" x1="' + x.toFixed(2) + '" y1="' + py(b.h).toFixed(2) +
      '" x2="' + x.toFixed(2) + '" y2="' + py(b.l).toFixed(2) + '"/>' +
      '<rect class="body fill-' + mark + '" x="' + (x - bodyW / 2).toFixed(2) + '" y="' + top.toFixed(2) +
      '" width="' + bodyW.toFixed(2) + '" height="' + h.toFixed(2) + '"/>';
  }).join("");

  const outcome = t.pnl >= 0 ? "gain" : "loss";
  const x1 = px(inIndex), y1 = py(t.entry), x2 = px(outIndex), y2 = py(t.exit);
  const trend =
    '<line class="trend mark-' + outcome + '" x1="' + x1.toFixed(2) + '" y1="' + y1.toFixed(2) +
    '" x2="' + x2.toFixed(2) + '" y2="' + y2.toFixed(2) + '"/>';

  const hint = y =>
    '<line class="hint" x1="' + TC_PAD.l + '" y1="' + y.toFixed(2) + '" x2="' + (width - TC_PAD.r) +
    '" y2="' + y.toFixed(2) + '"/>';

  const entryMark =
    '<circle class="entry-mark" cx="' + x1.toFixed(2) + '" cy="' + y1.toFixed(2) + '" r="5.5"/>';
  const exitMark =
    '<circle class="exit-mark fill-' + outcome + '" cx="' + x2.toFixed(2) + '" cy="' + y2.toFixed(2) + '" r="6"/>';

  const fillMarks = (t.fills || []).map(f => {
    const i = nearest(stampOf(f.d, f.m));
    const x = px(i), y = py(f.p);
    return '<rect class="' + (f.s === "in" ? "fill-in" : "fill-out fill-" + outcome) +
      '" x="' + (x - 3.5).toFixed(2) + '" y="' + (y - 3.5).toFixed(2) +
      '" width="7" height="7" rx="1.5" transform="rotate(45 ' + x.toFixed(2) + " " + y.toFixed(2) + ')"/>';
  }).join("");

  const plotted =
    overlays + barMarks + smaLines +
    hint(y1) + hint(y2) + trend + fillMarks + entryMark + exitMark;

  paintSvg(box,
    t.symbol + " price around the trade, entry " + money(t.entry) +
    (t.open ? " and last " : " and exit ") + money(t.exit),
    '<defs><clipPath id="tcClip"><rect x="' + TC_PAD.l + '" y="' + TC_PAD.t +
    '" width="' + plotW + '" height="' + plotH + '"/></clipPath></defs>' +
    grid + axis +
    '<g clip-path="url(#tcClip)">' + plotted + "</g>" +
    smaLabels + overlayText);

  for (const element of host.querySelectorAll("[data-sma]")) {
    element.style.setProperty("--sma-h", "var(" + averageColor(Number(element.dataset.sma)) + ")");
  }

  sizeHits(box);

  paintTradeLabels(x1, y1, x2, y2, width, inIndex >= i0 && inIndex <= i1,
    outIndex >= i0 && outIndex <= i1);
}

function paintTradeLabels(x1, y1, x2, y2, width, entryInView, exitInView) {
  const outcome = TRADE.pnl >= 0 ? "gain" : "loss";
  const host = document.getElementById("tc-host");
  host.querySelectorAll(".tc-mark").forEach(n => n.remove());
  const strategy = STRAT_BY_KEY[TRADE.strategy_key];
  const place = (x, y, title, price, cls) => {
    const el = document.createElement("div");
    el.className = "tc-mark " + cls + (cls === "exit" ? " mark-" + outcome : "");
    const head = document.createElement("span");
    head.className = "tc-k";
    head.textContent = title;
    const val = document.createElement("span");
    val.className = "tc-v num";
    val.textContent = money(price);
    const who = document.createElement("span");
    who.className = "tc-s";
    who.textContent = strategy ? strategy.short : TRADE.strategy_key;
    el.append(head, val, who);
    el.style.left = Math.round(x) + "px";
    el.style.top = Math.round(y) + "px";
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
    TRADE.symbol + " " + document.querySelector("#tc-range [aria-pressed=true]").textContent.trim() + " bars. " + rows.join(". ");
}

function tradeHover(event) {
  const geo = TC_STATE.geo;
  const tip = document.getElementById("tc-tip");
  if (!geo) return;
  const bars = geo.bars;
  const index = hoveredIndex(geo, event.clientX);
  const b = bars[index];
  if (!b) return;
  render(html`<span class="tt-k">${dayOf(b.t)} ${clockOf(b.t)}</span><span class="tt-v">${money(b.c)}</span>
    ${[["Open", b.o], ["High", b.h], ["Low", b.l]].map(([label, value]) =>
      html`<span class="tt-row"><span>${label}</span><span>${money(value)}</span></span>`)}`, tip);
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
    if (!button || button.dataset.timeframe === TC_STATE.timeframe) return;
    selectTradeState(button.dataset.timeframe);
    loadTradeLevels();
    syncTimeframeButtons();
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
    redraw: () => { TC_VIEW.custom = true; queueTradeChart(); },
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
  queueTradeChart();
}


let currentView = "dashboard";
const viewReady = { dashboard: true, portfolio: false, history: false, strategies: false, chart: true };

function switchView(name) {
  currentView = name;
  document.body.dataset.view = name;

  for (const b of document.querySelectorAll(".tabs button")) {
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
    if (name === "strategies") renderConfig();
    viewReady[name] = true;
  }

  if (name === "dashboard") queueChart();
  if (name === "chart") requestAnimationFrame(drawTradeChart);
  window.scrollTo(0, 0);
}



let CONFIG = null;

function configRow(row) {
  return html`<div class="config-row" title=${row.name}>
    <span class="label">${row.label}</span>
    <span class="value">${row.bound ? html`<i>${row.bound}</i>` : nothing}${row.value}</span>
  </div>`;
}

function configCard(card) {
  const isStrategy = Boolean(STRAT_BY_KEY?.[card.key]);
  const idle = isStrategy && switchState(card.key) !== "online";
  return html`<section class=${"panel config-card" + (idle ? " is-idle" : "")}>
    <div class="panel-head">
      <h2>${isStrategy ? strategyChip(strategyHue(card.key)) : nothing}<span>${card.name}</span></h2>
      ${isStrategy ? stateBadges(card.key) : nothing}
    </div>
    <div class="panel-body">
      <div class="config-rows">${card.rows.map(configRow)}</div>
      ${card.namespace ? html`<p class="config-foot">${card.namespace}*</p>` : nothing}
    </div>
  </section>`;
}

function paintConfig() {
  if (!CONFIG) return;
  document.getElementById("rules-config").textContent = CONFIG.configured
    ? "Reported by the bot"
    : "From the mode environment";
  render(repeat(CONFIG.cards, card => card.name, configCard),
    document.getElementById("rules-cards"));
}

async function renderConfig() {
  if (CONFIG) { paintConfig(); return; }
  try {
    const response = await fetch("/api/strategies", { credentials: "same-origin" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    CONFIG = (await response.json()).data;
  } catch (error) {
    document.getElementById("rules-cards").textContent =
      "The configuration could not be loaded. Reload the page to try again.";
    return;
  }
  paintConfig();
}


let calY = 0, calM = 0, booted = false;

function renderAll() {
  renderAccount();
  renderPeriodReturns();
  renderStrategies(stratRange);
  renderCalendar();
  renderToday();
  if (viewReady.portfolio) renderPortfolio();
  if (viewReady.history) renderHistory();
  if (viewReady.strategies) paintConfig();
}


function mergePositions(pulsed) {
  const rows = new Map((OPEN_POSITIONS || []).map(pos => [pos.symbol, pos]));
  const aligned = rows.size === pulsed.length && pulsed.every(pos => rows.has(pos.symbol));
  OPEN_POSITIONS = pulsed.map(pos => Object.assign(rows.get(pos.symbol) || {
    strategy_key: "unattributed", entered_at: null, fills: [],
  }, pos));
  return aligned;
}

function retipSeries(series, equity) {
  if (!series.todayTip || !series.length) return;
  series[series.length - 1].value = Math.round((equity - series.equityBase) * 100) / 100;
}

function applyPulse(pulsed, readAt) {
  if (readAt < accountReadAt) return true;
  accountReadAt = readAt;
  accountObservation = Object.fromEntries(
    ["orders", "asOf", "equity", "cash", "buyingPower", "marketValue", "unrealized_pnl", "positions"].map(key => [key, pulsed[key]])
  );
  ACCOUNT.portfolio = pulsed.equity;
  ACCOUNT.cash = pulsed.cash;
  ACCOUNT.deployed = pulsed.marketValue;
  ACCOUNT.unrealized_pnl = pulsed.unrealized_pnl;
  ACCOUNT.buyingPower = pulsed.buyingPower;
  ACCOUNT.totalReturn = Math.round((ACCOUNT.portfolio - ACCOUNT.invested) * 100) / 100;
  ACCOUNT.rateOfReturn = ACCOUNT.invested ? (ACCOUNT.totalReturn / ACCOUNT.invested) * 100 : null;
  ACCOUNT.exposurePct = ACCOUNT.portfolio ? (ACCOUNT.deployed / ACCOUNT.portfolio) * 100 : 0;

  if (ACCOUNT.dayOpening) ACCOUNT.dayLowEquity = ratchetLow(SESSION_LOW.date, pulsed.equity);
  ACCOUNT.dayDrawdownPct = drawdownPct();
  if (!SESSIONS.length) STRATEGY_PERIODS.D.base = LAST_SESSION.before = pulsed.equity;

  const aligned = mergePositions(pulsed.positions);
  ACCOUNT.largestPositionPct = OPEN_POSITIONS.length
    ? Math.max(...OPEN_POSITIONS.map(p => p.weight)) : 0;

  retipSeries(DAILY, pulsed.equity);
  retipSeries(INTRADAY, pulsed.equity);

  Object.assign(LEDGER, accountObservation);
  return aligned;
}

function paintPulse() {
  renderAccount();
  renderStrategies(stratRange);
  if (viewReady.strategies) paintConfig();
  if (currentView === "dashboard") {
    queueChart();
    if (todayTab === "open") renderToday();
  }
  if (currentView === "portfolio" && viewReady.portfolio) {
    renderPortfolio();
  }
}

let pendingRefresh, refreshTimer, resumeAt = 0, failedAt = 0;

async function readAccount(path) {
  try {
    if (Date.now() < resumeAt) throw new Error("feed paused");
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    if (response.status === 401) location.replace("/login");
    if (!response.ok) {
      const pause = Number(response.headers.get("Retry-After"));
      if (pause > 0) resumeAt = Math.max(resumeAt, Date.now() + pause * 1000);
      throw new Error("read failed (" + response.status + ")");
    }
    return await response.json();
  } catch (error) {
    failedAt = Date.now();
    throw error;
  }
}

let pulsing = false;

async function pulse() {
  if (!booted || pulsing) return;
  pulsing = true;
  try {
    const payload = await readAccount("/api/pulse");
    const aligned = applyPulse(payload.data, Date.parse(payload.read_at));
    paintPulse();
    markFeed();
    if (!aligned) void refresh();
  } catch (error) {
    markFeed("error");
  } finally {
    pulsing = false;
  }
}

function markFeed(state) {
  if (!LEDGER) render(html`<span id="st-asof"></span>`, document.getElementById("status"));
  const stale = accountReadAt < failedAt || Date.now() - accountReadAt > SESSION.pulse_seconds * 1000;
  document.getElementById("status").dataset.feed = state || (stale ? "error" : "ok");
  document.getElementById("st-asof").textContent =
    (state === "error" || stale ? "feed unavailable · " : "") + (LEDGER?.asOf || "awaiting account");
}

function refresh() {
  if (pendingRefresh) return pendingRefresh;
  clearTimeout(refreshTimer);
  pendingRefresh = refreshLedger().finally(() => {
    pendingRefresh = null;
    if (!document.hidden) refreshTimer = setTimeout(refresh,
      Math.max(SESSION.refresh_seconds * 1000, resumeAt - Date.now()));
  });
  return pendingRefresh;
}

async function refreshLedger() {
  try {
    const payload = await readAccount("/api/ledger");
    const first = !booted;
    const keepSelection = todaySel;
    const intraday = chart.series === INTRADAY;

    const historyChanged = derive(payload.data, Date.parse(payload.read_at));

    if (first || !keepSelection || !tradesByDate.has(
      keepSelection.y + "-" + String(keepSelection.m + 1).padStart(2, "0") + "-" + String(keepSelection.day).padStart(2, "0")
    )) {
      todaySel = { ...LATEST };
      calY = LATEST.y;
      calM = LATEST.m;
    }

    if (historyChanged) renderAll();
    else paintPulse();

    if (chart.custom) {
      chart.series = intraday ? INTRADAY : DAILY;
      queueChart();
    } else {
      setRange(chart.preset);
    }

    booted = true;
    markFeed();
  } catch (error) {
    markFeed("error");
  }
}


document.querySelector(".tabs").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (btn && btn.dataset.view) switchView(btn.dataset.view);
});

document.getElementById("chart-range").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (btn) setRange(btn.dataset.range);
});

wireGroup("strat-range", "range", value => { stratRange = value; renderStrategies(value); });

wireGroup("unit-toggle", "unit", value => { unit = value; renderPeriodReturns(); });

wireGroup("today-tabs", "tab", value => { todayTab = value; renderToday(); });

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

for (const id of ["f-strategy", "f-side", "f-result", "f-session"]) {
  document.getElementById(id).addEventListener("change", renderLog);
}
document.getElementById("f-symbol").addEventListener("input", renderLog);
document.getElementById("f-clear").addEventListener("click", () => {
  for (const id of ["f-strategy", "f-side", "f-result", "f-session"]) document.getElementById(id).value = "";
  document.getElementById("f-symbol").value = "";
  renderLog();
});

function resolvedTheme() {
  return document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}

function syncThemeButtons() {
  pressOnly("#theme-toggle button", b => b.dataset.setTheme === resolvedTheme());
}

function repaintForTheme() {
  if (currentView === "dashboard") queueChart();
  if (currentView === "chart") queueTradeChart();
}

document.getElementById("theme-toggle").addEventListener("click", ev => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  document.documentElement.setAttribute("data-theme", btn.dataset.setTheme);
  try { localStorage.setItem("mt-theme", btn.dataset.setTheme); } catch {}
  syncThemeButtons();
  repaintForTheme();
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.getAttribute("data-theme")) { syncThemeButtons(); repaintForTheme(); }
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/logout", { method: "POST", headers: { "X-CSRF-Token": SESSION.csrf_token || "" } });
  location.replace("/login");
});

new ResizeObserver(queueChart).observe(document.getElementById("chart-host"));

let tradeResizeTimer = 0;
new ResizeObserver(() => {
  clearTimeout(tradeResizeTimer);
  tradeResizeTimer = setTimeout(() => { if (currentView === "chart") queueTradeChart(); }, 80);
}).observe(document.getElementById("tc-host"));

let wasPhone = onPhone();
window.addEventListener("resize", () => {
  const isPhone = onPhone();
  if (isPhone === wasPhone) return;
  wasPhone = isPhone;
  if (!isPhone && currentView === "dashboard") queueChart();
});

document.body.dataset.view = "dashboard";
syncThemeButtons();
initChartInteraction();
wireTradeChart();
(async () => {
  const read = await fetch("/api/session", { cache: "no-store" });
  if (!read.ok) return;
  SESSION = await read.json();
  await refresh();
  setInterval(() => { if (!document.hidden) pulse(); }, SESSION.pulse_seconds * 1000);
})();

document.addEventListener("visibilitychange", () => {
  if (document.hidden) { clearTimeout(refreshTimer); return; }
  pulse();
  refresh();
});
