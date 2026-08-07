# Node

Verification record for money_tree/node.py, postdating the research record

Checked on 2026-08-07 against nautilus-trader 1.231.0

## Method

| Stage | Command | Result |
| --- | --- | --- |
| Static | `ruff check`, `ruff format --check`, `ty check` | Pass, 9 files |
| Instrument load | `load_instruments()` | 1 instrument, `ETHUSDT-LINEAR.BYBIT` |
| Live session | `money-tree`, 5 minutes, SIGINT stop | Exit 0, 488 log lines |
| Event drive | `on_event` fed a real `PositionChanged` | Re-armed a cleared trailing stop |

The live session used the mainnet Bybit feed and the simulated sandbox venue. No real order was placed.

## Confirmed behavior

| Spec rule | Observation |
| --- | --- |
| `live(feed) and simulated(venue)` | Data client subscribed to mainnet trades and 1-minute bars; execution client is `SandboxExecutionClient` with a 10 000 USDT opening balance |
| `seeded(instrument) precedes connect(node)` | Instruments enter the cache after `node.build()` and before `node.run()`; the strategy resolved its instrument at `on_start` |
| `flat(strategy) → enter(side(fast_ema, slow_ema))` | First live bar close at 09:48:00 produced a BUY market order, filled at 1914.33 |
| `open(position) → attached(trailing_stop)` | `PositionOpened` produced a reduce-only SELL trailing stop, offset 3.23 on a last-price trigger |

Warmup works as designed. `request_bars` returned 199 bars and registered indicators consumed them, because
`Actor.handle_bar` updates indicators before branching on the historical flag. `indicators_initialized()`
was true on the first live bar and the warmup log line never fired, so no live bar is spent warming up.

Shutdown flattens. `on_stop` cancelled the working stop and closed the position; the fills landed 7 ms
after the strategy reported STOPPED and 5 s before the clients stopped.

## Findings

| # | Finding | Evidence | Effect |
| --- | --- | --- | --- |
| 1 | The trailing stop re-arms on a position the strategy is abandoning | `PositionChanged.opening_order_id` carries the opening order of the position, not the order that changed it; driving `on_event` with a flatten order id distinct from the entry id still submitted a stop | After a stop failure, `_flatten_position` clears the stop and closes the position; a partial fill of that close re-enters the attach branch, so the abandoned position gets a fresh stop and a second rejection raises the failure count again |
| 2 | The instrument loader ignores `ENVIRONMENT` | `load_instruments` calls `get_cached_bybit_http_client()` with no arguments, whose default is Mainnet; `ENVIRONMENT` reaches only the data client | Selecting Testnet seeds mainnet instruments into a testnet-fed node. Both names resolve to the same enum, so passing the constant through is a one-line change |
| 3 | Fee rates are fallbacks, not the venue schedule | `Missing credentials for fee rates, using defaults`; the loaded instrument carries `maker_fee` and `taker_fee` both at 0.001 | The round trip cost 0.0382844 USDT on 19.14 USDT of notional, 20 basis points. Identical maker and taker rates are a placeholder, and the taker rate is above Bybit's published schedule, so sandbox results understate the strategy |
| 4 | The trade tick subscription is load-bearing and unmarked | No `on_trade_tick` handler exists, yet the sandbox venue runs `trade_execution` on an `L1_MBP` book | Trade ticks are what move the matching engine and fill orders. The subscription reads as vestigial, and removing it would stop every fill without an error |
| 5 | `on_stop` is asymmetric with `on_start` | The log shows only a bar unsubscribe | Trade ticks stay subscribed until the client stops |
| 6 | Flat on exit depends on `timeout_post_stop` | STOPPED at 09:52:05.595, `PositionClosed` at 09:52:05.602, clients stopped at 09:52:10.597 | The cancel and close are issued but not awaited. A shorter post-stop timeout would leave a position open. The session ran under an explicit 5 s override, half the default |
| 7 | A running session is silent | Between the entry and shutdown the strategy emitted no line of its own, only 91 engine-forwarded order updates | Position, exposure, and realized return are unobservable without reading order events |
| 8 | `warmup_bars` sets both the lookback window and the row limit | The request spanned 200 minutes with a limit of 200 and returned 199 | The two roles cannot be tuned apart, and a limit above the venue cap would silently shorten the window |

## Session outcome

One round trip, held 247 s, opened at 1914.33 and closed at 1914.11, realized −0.04048440 USDT.
Commission accounted for 0.03828440 of that loss.

## Design notes

The strategy holds a position continuously. `on_bar` enters whenever the portfolio is flat, and the
trailing stop is the only exit, so a stop-out is followed by a fresh entry on the next bar in whichever
direction the fast and slow averages then imply. A whipsaw therefore pays two taker crossings per cycle,
and finding 3 governs how that cost is measured.

`max_trailing_stop_failures` counts cumulatively across the session and resets only when a stop is
accepted, so three failures spread across hours still stop the node.

`reject_stop_orders` defaults to true on the sandbox venue, which rejects a stop whose trigger is already
in the market. That is the path `_flatten_position` guards, and finding 1 sits on it.

## Acted on

Finding 6 is closed. The explicit `timeout_post_stop` override is removed, so the unawaited cancel and
close now run under the 10 s default. A later session confirmed the flatten still completes: SIGINT
cancelled the working stop and closed the position.

Findings 1, 2, 3, 4, 5, 7, and 8 are open.
