import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const source = readFileSync(new URL("../../src/mt/web/assets/dashboard.js", import.meta.url), "utf8");

export function init() {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {
      dataset: {},
      style: {},
      children: [],
      options: [],
      value: "",
      addEventListener() {},
      querySelector() { return null; },
      getAttribute() { return null; },
      setAttribute() {},
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      classList: { add() {}, remove() {}, toggle() {} },
    });
    return nodes.get(id);
  };
  const context = createContext({
    window: { matchMedia: () => ({ matches: false, addEventListener() {} }) },
    document: {
      body: node("body"),
      documentElement: node("html"),
      getElementById: node,
      querySelector: node,
      querySelectorAll: () => [],
      createElement: () => node(Symbol()),
      addEventListener() {},
    },
    ResizeObserver: class { observe() {} },
    fetch: async () => ({ ok: false, status: 503 }),
  });
  runInContext(source, context);
  return {
    nodes,
    evaluate: code => runInContext(code, context),
    derive: ledger => {
      context.input = ledger;
      runInContext("derive(input)", context);
    },
  };
}

export function ledger() {
  return {
    today: "2026-09-08", funded: "8 Sep 2026", equity: 10100, invested: 10000,
    cash: 10100, marketValue: 0, unrealised: 0, buyingPower: 10100,
    positionCapPct: 10, dailyLossLimitPct: 2,
    strategies: [{ id: "daily_sma", short: "Daily SMA", label: "Daily SMA" }],
    positions: [],
    trades: [{ symbol: "AAPL", strategy: "daily_sma", date: "2026-09-08", pnl: 100 }],
    days: [{ date: "2026-09-08", pnl: 100, trades: 1, wins: 1, before: 10000 }],
    equityDaily: [{ date: "2026-09-08", equity: 10100 }],
    intraday: [], intradayDate: "", benchmark: [], benchmarkSymbol: "SPY",
  };
}
