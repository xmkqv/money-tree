import assert from "node:assert/strict";
import test from "node:test";

import { init, ledger } from "./world/dashboard.mjs";

test("calendar retains ledger days after trade statistics are calculated", () => {
  const world = init();
  world.derive(ledger());
  assert.equal(world.evaluate("monthData(2026, 8).trades"), 1);
  assert.equal(world.evaluate("monthData(2026, 8).pnl"), 100);
  assert.equal(world.evaluate("ACCOUNT.closed"), 1);
});

test("history renders when there are no closed trades", () => {
  const world = init();
  world.derive({ ...ledger(), trades: [], days: [] });
  world.evaluate("renderHistory()");
  assert.equal(world.nodes.get("hs-span").textContent, "No closed trades");
});
