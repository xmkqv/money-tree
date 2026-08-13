"""
sma_nautilus.py

    uv add "nautilus_trader[ib]" plotly   # verified against 1.231.0 (beta; paths move)

The five-stage pipeline does not survive the port. Nautilus is event-driven:
there is no gen_trades pass over a frame, no plot stage. Data goes into a
catalog ahead of time; indicators update per-bar inside the strategy; orders
are submitted as events; analysis comes off the engine afterwards.

Same code path runs backtest and live — that is the entire reason to be here.
Ingest goes through the Interactive Brokers adapter's historical client: the
same adapter that would drive a live node, so the instrument definitions in
the catalog are the real contract, not a stub.

Needs TWS or IB Gateway running with API enabled (TWS paper 7497, gateway
paper 4002); the fetch is skipped once the catalog is populated.

    TICKER=AAPL START=2015-01-01 IB_PORT=7497 uv run scripts/demo.py
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
    StrategyConfig,
)
from nautilus_trader.core.datetime import unix_nanos_to_dt
from nautilus_trader.indicators.averages import SimpleMovingAverage
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled, PositionOpened
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.trading.strategy import Strategy

BAR_SPEC = "1-DAY-LAST"  # daily bars, aggregated from last price, loaded EXTERNAL


# ---------------------------------------------------------------- config


class SMAConfig(StrategyConfig, frozen=True):
    """Nautilus configs are frozen msgspec structs — not @dataclass. No mutation."""

    instrument_id: InstrumentId
    bar_type: BarType
    fast: int = 150
    slow: int = 200
    slope_lookback: int = 20
    threshold: float = 0.8
    trade_size: Decimal = Decimal("100")


# ---------------------------------------------------------------- 0/1: ingest


def load_env() -> tuple[Path, str]:
    catalog_path = Path(os.environ.get("CATALOG_PATH", ".catalog"))
    ticker = os.environ.get("TICKER", "AAPL")
    return catalog_path, ticker


async def fetch(ticker: str, start: str) -> tuple[list[Instrument], list[Bar]]:
    """
    The provider seam — now the IB adapter's historical client, which returns
    catalog-ready Instrument and Bar objects. No frame, no wrangler.
    """
    from nautilus_trader.adapters.interactive_brokers.common import IBContract
    from nautilus_trader.adapters.interactive_brokers.historical import (
        HistoricInteractiveBrokersClient,
    )

    client = HistoricInteractiveBrokersClient(
        host=os.environ.get("IB_HOST", "127.0.0.1"),
        port=int(os.environ.get("IB_PORT", "7497")),  # TWS paper 7497, gateway paper 4002
        client_id=int(os.environ.get("IB_CLIENT_ID", "5")),
        log_level="ERROR",
    )
    await client.connect()
    await asyncio.sleep(2)  # let the API handshake settle before requesting

    contract = IBContract(
        secType="STK",
        symbol=ticker,
        exchange="SMART",
        primaryExchange=os.environ.get("IB_PRIMARY_EXCHANGE", "NASDAQ"),
    )
    instruments = await client.request_instruments(contracts=[contract])
    bars = await client.request_bars(
        bar_specifications=[BAR_SPEC],
        start_date_time=datetime.fromisoformat(start),
        end_date_time=datetime.now(),
        tz_name="America/New_York",
        contracts=[contract],
        use_rth=True,
    )
    if not instruments or not bars:
        raise RuntimeError(f"IB returned nothing for {ticker!r} — check subscriptions")
    return instruments, bars


def ingest(catalog_path: Path, ticker: str, start: str) -> ParquetDataCatalog:
    """
    One-off, not per-run. Fetch -> catalog.write_data(). This is where the
    provider seam lives now; the strategy never sees a fetcher.
    """
    catalog_path.mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(catalog_path)

    if any(i.id.symbol.value == ticker for i in catalog.instruments()):
        return catalog  # already ingested; the catalog is the source of truth

    instruments, bars = asyncio.run(fetch(ticker, start))
    catalog.write_data(instruments)
    catalog.write_data(bars)
    return catalog


# ---------------------------------------------------------------- 2/3: strategy


class SMAStrategy(Strategy):
    """
    Indicators are stateful objects fed bar-by-bar, not columns. That kills the
    free parameter sweep — a window grid means N engine runs, not N columns.
    """

    def __init__(self, config: SMAConfig) -> None:
        super().__init__(config)
        self.sma_fast = SimpleMovingAverage(config.fast)
        self.sma_slow = SimpleMovingAverage(config.slow)
        # manual ring buffers: a streaming indicator has no .diff()
        self._fast_window: deque[float] = deque(maxlen=config.slope_lookback + 1)
        self._slow_window: deque[float] = deque(maxlen=config.slope_lookback + 1)
        self.fills: list[dict] = []

    def on_start(self) -> None:
        """register_indicator_for_bars() then subscribe_bars(). Engine handles updates."""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"instrument {self.config.instrument_id} not in cache")
            self.stop()
            return
        self.register_indicator_for_bars(self.config.bar_type, self.sma_fast)
        self.register_indicator_for_bars(self.config.bar_type, self.sma_slow)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        # SMAs emit garbage until warm, and 200 bars of warmup is a lot of garbage
        if not self.indicators_initialized():
            return

        self._fast_window.append(self.sma_fast.value)
        self._slow_window.append(self.sma_slow.value)

        score, fired = self.score_rules(bar)
        instrument_id = self.config.instrument_id

        # position state is queried, not inferred — no entries/exits arrays
        if score >= self.config.threshold and self.portfolio.is_flat(instrument_id):
            order = self.order_factory.market(
                instrument_id=instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
            )
            self.submit_order(order)
            self.log.info(f"entry score={score:.2f} fired={fired}")
        elif score < self.config.threshold and self.portfolio.is_net_long(instrument_id):
            self.close_all_positions(instrument_id)
            self.log.info(f"exit score={score:.2f} fired={fired}")

    def score_rules(self, bar: Bar) -> tuple[float, tuple[str, ...]]:
        """fired/total, same as before."""
        close = bar.close.as_double()
        fast = self.sma_fast.value
        slow = self.sma_slow.value
        fast_slope = self._fast_window[-1] - self._fast_window[0]
        slow_slope = self._slow_window[-1] - self._slow_window[0]

        rules = {
            "fast>slow": fast > slow,
            "close>fast": close > fast,
            "close>slow": close > slow,
            "fast_rising": fast_slope > 0.0,
            "slow_rising": slow_slope > 0.0,
        }
        fired = tuple(name for name, hit in rules.items() if hit)
        return len(fired) / len(rules), fired

    def on_order_filled(self, event: OrderFilled) -> None:
        """Fills are asynchronous. This is where a Trade record gets written."""
        self.fills.append(
            {
                "ts": unix_nanos_to_dt(event.ts_event),
                "instrument": str(event.instrument_id),
                "side": event.order_side.name,
                "qty": float(event.last_qty),
                "price": float(event.last_px),
            }
        )

    def on_position_opened(self, event: PositionOpened) -> None:
        self.log.info(f"position opened: {event.instrument_id} qty={event.quantity}")

    def on_stop(self) -> None:
        # an open position at end-of-data is not a result
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)


# ---------------------------------------------------------------- 4: run/report


def build_run_config(catalog: ParquetDataCatalog, cfg: SMAConfig) -> BacktestRunConfig:
    """
    Venue (fill model, account type, starting balance) + data + ImportableStrategyConfig.
    Strategies are referenced by import path, not instance — that is what lets the
    same config drive a live node.
    """
    venue = BacktestVenueConfig(
        name=cfg.instrument_id.venue.value,
        oms_type="NETTING",
        account_type="CASH",
        base_currency="USD",
        starting_balances=["100000 USD"],
    )
    data = BacktestDataConfig(
        catalog_path=str(catalog.path),
        data_cls=Bar,
        instrument_id=cfg.instrument_id,
        bar_spec=BAR_SPEC,
    )
    engine = BacktestEngineConfig(
        strategies=[
            ImportableStrategyConfig(
                strategy_path=f"{SMAStrategy.__module__}:{SMAStrategy.__qualname__}",
                config_path=f"{SMAConfig.__module__}:{SMAConfig.__qualname__}",
                config={
                    "instrument_id": cfg.instrument_id,
                    "bar_type": cfg.bar_type,
                    "fast": cfg.fast,
                    "slow": cfg.slow,
                    "slope_lookback": cfg.slope_lookback,
                    "threshold": cfg.threshold,
                    "trade_size": cfg.trade_size,
                },
            ),
        ],
        logging=LoggingConfig(log_level="ERROR"),
    )
    return BacktestRunConfig(
        engine=engine,
        data=[data],
        venues=[venue],
        # default True wipes the engine cache after the run, leaving nothing
        # for report(); main() disposes explicitly once reports are written
        dispose_on_completion=False,
    )


def run(run_config: BacktestRunConfig) -> BacktestNode:
    node = BacktestNode(configs=[run_config])
    node.run()
    return node


def report(node: BacktestNode, out: Path) -> None:
    """
    engine.trader.generate_positions_report() / generate_order_fills_report()
    for the tables; create_tearsheet() for the charts — Nautilus grew a native
    plotly tearsheet (equity, drawdown, returns, bars-with-fills), so no
    external charting stack is needed.
    """
    out.mkdir(parents=True, exist_ok=True)
    engine = node.get_engines()[0]

    fills = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    venue = engine.cache.instruments()[0].id.venue
    account = engine.trader.generate_account_report(venue)

    fills.to_csv(out / "fills.csv")
    positions.to_csv(out / "positions.csv")
    account.to_csv(out / "account.csv")

    if not positions.empty:
        pnl = positions["realized_pnl"].map(lambda v: float(str(v).split(" ")[0]))
        print(f"positions: {len(positions)}  realized_pnl: {pnl.sum():,.2f} USD")
    if not account.empty:
        print(f"final balance: {account.iloc[-1]['total']} USD")

    from nautilus_trader.analysis.config import (
        TearsheetBarsWithFillsChart,
        TearsheetConfig,
    )
    from nautilus_trader.analysis.tearsheet import create_tearsheet

    bar_type = engine.cache.bar_types()[0]
    config = TearsheetConfig()  # run info, stats, equity, drawdown, returns...
    config = TearsheetConfig(
        charts=[TearsheetBarsWithFillsChart(bar_type=str(bar_type)), *config.charts],
    )
    create_tearsheet(
        engine,
        output_path=str(out / "tearsheet.html"),
        title="SMA demo",
        node=node,  # lets bars_with_fills read bars off the cached run
        config=config,
    )
    print(f"reports + tearsheet -> {out}/")


def main() -> None:
    catalog_path, ticker = load_env()
    start = os.environ.get("START", "2015-01-01")

    catalog = ingest(catalog_path, ticker, start)
    instrument = next(i for i in catalog.instruments() if i.id.symbol.value == ticker)

    cfg = SMAConfig(
        instrument_id=instrument.id,
        bar_type=BarType.from_str(f"{instrument.id}-{BAR_SPEC}-EXTERNAL"),
    )

    node = run(build_run_config(catalog, cfg))
    report(node, Path(os.environ.get("OUT", "out")))
    node.dispose()


if __name__ == "__main__":
    main()
