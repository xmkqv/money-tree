"""A live NautilusTrader node.

Trades an EMA cross on Bybit perpetuals, protecting each position with an ATR-scaled
trailing stop. Live Bybit data feeds a local simulated exchange, so the node needs no
API key, no account, and risks nothing.
"""

import asyncio
from datetime import timedelta
from decimal import Decimal
from typing import Final

from nautilus_trader.adapters.bybit import (
    BYBIT,
    BybitDataClientConfig,
    BybitEnvironment,
    BybitInstrumentProvider,
    BybitLiveDataClientFactory,
    BybitProductType,
    get_cached_bybit_http_client,
)
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import (
    InstrumentProviderConfig,
    LiveExecEngineConfig,
    LoggingConfig,
    PositiveFloat,
    PositiveInt,
    StrategyConfig,
    TradingNodeConfig,
)
from nautilus_trader.core.correctness import PyCondition  # ty: ignore[unresolved-import]
from nautilus_trader.core.message import Event  # ty: ignore[unresolved-import]
from nautilus_trader.indicators import AverageTrueRange, ExponentialMovingAverage
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import Bar, BarType  # ty: ignore[unresolved-import]
from nautilus_trader.model.enums import OrderSide, TrailingOffsetType, TriggerType
from nautilus_trader.model.events import (
    OrderAccepted,
    OrderDenied,
    OrderEvent,
    OrderFilled,
    OrderRejected,
    PositionChanged,
    PositionClosed,
    PositionOpened,
)
from nautilus_trader.model.identifiers import (  # ty: ignore[unresolved-import]
    InstrumentId,
    PositionId,
    TraderId,
)
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import Order
from nautilus_trader.trading.strategy import Strategy  # ty: ignore[unresolved-import]

PRODUCT_TYPE: Final = BybitProductType.LINEAR
SYMBOL: Final = f"ETHUSDT-{PRODUCT_TYPE.value.upper()}"
INSTRUMENT_ID: Final = InstrumentId.from_str(f"{SYMBOL}.BYBIT")
BAR_TYPE: Final = BarType.from_str(f"{SYMBOL}.BYBIT-1-MINUTE-LAST-EXTERNAL")
TRADE_SIZE: Final = Decimal("0.010")
TRADER_ID: Final = TraderId("MONEY-TREE-001")
ENVIRONMENT: Final = BybitEnvironment.MAINNET
STARTING_BALANCE: Final = "10_000 USDT"


class EmaCrossTrailingConfig(StrategyConfig, frozen=True):
    """Configuration for `EmaCrossTrailing`."""

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    atr_period: PositiveInt = 14
    trailing_atr_multiple: PositiveFloat = 3.0
    fast_ema_period: PositiveInt = 10
    slow_ema_period: PositiveInt = 20
    warmup_days: PositiveInt = 1
    max_stop_failures: PositiveInt = 3


class EmaCrossTrailing(Strategy):
    """Enter on an EMA cross, per bar while flat.

    A `reduce_only` trailing stop is attached on open and stays on, so the position is
    never unprotected between bars. A stop the venue rejects closes the position, and
    repeated failures stop the strategy.
    """

    config: EmaCrossTrailingConfig

    def __init__(self, config: EmaCrossTrailingConfig) -> None:
        PyCondition.is_true(
            config.fast_ema_period < config.slow_ema_period,
            f"{config.fast_ema_period=} must be less than {config.slow_ema_period=}",
        )
        super().__init__(config)

        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)
        self.atr = AverageTrueRange(config.atr_period)

        self.instrument: Instrument | None = None
        self.entry: Order | None = None
        self.trailing_stop: Order | None = None
        self.stop_failures = 0

    def on_start(self) -> None:
        """Prime indicators, request warmup, then subscribe to the live feeds.

        Trade ticks feed the simulated exchange, which matches orders against ticks and
        ignores bars; they are subscribed even though no strategy logic reads them.
        """
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        for indicator in (self.fast_ema, self.slow_ema, self.atr):
            self.register_indicator_for_bars(self.config.bar_type, indicator)

        self.subscribe_trade_ticks(self.config.instrument_id)

        self.request_bars(
            self.config.bar_type,
            start=self.clock.utc_now() - timedelta(days=self.config.warmup_days),
            callback=lambda _: self.subscribe_bars(self.config.bar_type),
        )

    def on_bar(self, bar: Bar) -> None:
        """Take the side the fast EMA sits on, whenever flat."""
        if not self.indicators_initialized():
            self.log.info("Warming up indicators", LogColor.BLUE)
            return

        if bar.is_single_price():
            return

        if not self.portfolio.is_flat(self.config.instrument_id):
            return

        side = OrderSide.BUY if self.fast_ema.value >= self.slow_ema.value else OrderSide.SELL
        self._submit_entry(side)

    def on_event(self, event: Event) -> None:
        """Keep exactly one trailing stop attached to the open position."""
        match event:
            case OrderFilled() if self._is_trailing_stop(event):
                self.trailing_stop = None
            case OrderAccepted() if self._is_trailing_stop(event):
                self.stop_failures = 0
            case OrderDenied() | OrderRejected() if self._is_trailing_stop(event):
                self._flatten_unprotected(event.reason)
            case OrderDenied() | OrderRejected() if self._is_entry(event):
                self.entry = None
            case PositionOpened() | PositionChanged() if self.trailing_stop is None:
                self._attach_trailing_stop(event)
            case PositionClosed():
                self.entry = None
                self.trailing_stop = None

    def on_stop(self) -> None:
        """Cancel and close everything still at the venue.

        Trade ticks are left subscribed: the simulated exchange needs them to fill the
        market close, and the node tears the data feed down on disposal.
        """
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        self.fast_ema.reset()
        self.slow_ema.reset()
        self.atr.reset()
        self.entry = None
        self.trailing_stop = None
        self.stop_failures = 0

    def _is_trailing_stop(self, event: OrderEvent) -> bool:
        return (
            self.trailing_stop is not None
            and event.client_order_id == self.trailing_stop.client_order_id
        )

    def _is_entry(self, event: OrderEvent) -> bool:
        return self.entry is not None and event.client_order_id == self.entry.client_order_id

    def _flatten_unprotected(self, reason: str) -> None:
        """Close a position whose trailing stop the venue would not take.

        Clearing the stop reference first lets `on_event` attach a fresh one; keeping it
        would strand the position with no protection.
        """
        self.trailing_stop = None
        self.stop_failures += 1
        self.log.error(f"Trailing stop failed ({reason}); closing position")
        self.close_all_positions(self.config.instrument_id)

        if self.stop_failures >= self.config.max_stop_failures:
            self.log.error(f"Stopping after {self.stop_failures} trailing stop failures")
            self.stop()

    def _attach_trailing_stop(self, event: PositionOpened | PositionChanged) -> None:
        if self.entry is None or event.opening_order_id != self.entry.client_order_id:
            return

        exit_side = OrderSide.SELL if event.entry == OrderSide.BUY else OrderSide.BUY
        self._submit_trailing_stop(exit_side, event.position_id, event.quantity.as_decimal())

    def _submit_entry(self, order_side: OrderSide) -> None:
        if (instrument := self.instrument) is None:
            self.log.error("Cannot submit entry: no instrument loaded")
            return

        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=order_side,
            quantity=instrument.make_qty(self.config.trade_size),
        )
        self.entry = order
        self.submit_order(order)

    def _submit_trailing_stop(
        self, order_side: OrderSide, position_id: PositionId, quantity: Decimal
    ) -> None:
        """Submit a reduce-only trailing stop sized to the position it protects.

        The ATR offset is floored at one tick so a quiet market can't round it to zero,
        which the venue rejects.
        """
        if (instrument := self.instrument) is None:
            self.log.error("Cannot submit trailing stop: no instrument loaded")
            return

        scaled = self.atr.value * self.config.trailing_atr_multiple
        offset = max(
            Decimal(f"{scaled:.{instrument.price_precision}f}"),
            instrument.price_increment.as_decimal(),
        )
        order = self.order_factory.trailing_stop_market(
            instrument_id=self.config.instrument_id,
            order_side=order_side,
            quantity=instrument.make_qty(quantity),
            trailing_offset=offset,
            trailing_offset_type=TrailingOffsetType.PRICE,
            trigger_type=TriggerType.LAST_PRICE,
            reduce_only=True,
        )
        self.trailing_stop = order
        self.submit_order(order, position_id=position_id)


def load_instruments() -> list[Instrument]:
    """Fetch the traded instrument from Bybit's public REST API.

    Run before the node connects: the simulated exchange builds a matching engine per
    cached instrument at connect and won't add one later, so an unseeded instrument makes
    every order reject with "no market".
    """

    async def load() -> list[Instrument]:
        provider = BybitInstrumentProvider(
            client=get_cached_bybit_http_client(),
            product_types=(PRODUCT_TYPE,),
            config=InstrumentProviderConfig(load_ids=frozenset({INSTRUMENT_ID})),
        )
        await provider.load_ids_async([INSTRUMENT_ID])
        return list(provider.get_all().values())

    return asyncio.run(load())


def build_node() -> TradingNode:
    """Build the live trading node, ready to run.

    Execution is a local simulated exchange that keeps no state across runs, so
    reconciliation is disabled.
    """
    instrument_provider = InstrumentProviderConfig(load_ids=frozenset({INSTRUMENT_ID}))
    config = TradingNodeConfig(
        trader_id=TRADER_ID,
        logging=LoggingConfig(use_pyo3=True),
        exec_engine=LiveExecEngineConfig(
            reconciliation=False,
            purge_closed_orders_interval_mins=15,
            purge_closed_orders_buffer_mins=60,
            purge_closed_positions_interval_mins=15,
            purge_closed_positions_buffer_mins=60,
            purge_account_events_interval_mins=15,
            purge_account_events_lookback_mins=60,
            graceful_shutdown_on_exception=True,
        ),
        data_clients={
            BYBIT: BybitDataClientConfig(
                environment=ENVIRONMENT,
                instrument_provider=instrument_provider,
                product_types=(PRODUCT_TYPE,),
            ),
        },
        exec_clients={
            BYBIT: SandboxExecutionClientConfig(
                venue=BYBIT,
                starting_balances=[STARTING_BALANCE],
            ),
        },
        timeout_connection=20.0,
        timeout_post_stop=5.0,
    )

    node = TradingNode(config=config)
    node.trader.add_strategy(
        EmaCrossTrailing(
            config=EmaCrossTrailingConfig(
                instrument_id=INSTRUMENT_ID,
                bar_type=BAR_TYPE,
                trade_size=TRADE_SIZE,
                order_id_tag="001",
            ),
        ),
    )
    node.add_data_client_factory(BYBIT, BybitLiveDataClientFactory)
    node.add_exec_client_factory(BYBIT, SandboxLiveExecClientFactory)
    node.build()

    for instrument in load_instruments():
        node.kernel.cache.add_instrument(instrument)

    return node


def main() -> None:
    """Run the node until interrupted, then dispose of it."""
    node = build_node()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main()

