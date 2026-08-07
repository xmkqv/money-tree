import asyncio
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
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.core.message import Event
from nautilus_trader.indicators import AverageTrueRange, ExponentialMovingAverage
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import Bar, BarType
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
from nautilus_trader.model.identifiers import (
    InstrumentId,
    PositionId,
    TraderId,
)
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import Order
from nautilus_trader.trading.strategy import Strategy

PRODUCT_TYPE: Final = BybitProductType.LINEAR
SYMBOL: Final = f"ETHUSDT-{PRODUCT_TYPE.value.upper()}"
INSTRUMENT_ID: Final = InstrumentId.from_str(f"{SYMBOL}.BYBIT")
BAR_TYPE: Final = BarType.from_str(f"{SYMBOL}.BYBIT-1-MINUTE-LAST-EXTERNAL")
TRADE_SIZE: Final = Decimal("0.010")
TRADER_ID: Final = TraderId("MONEY-TREE-001")
ENVIRONMENT: Final = BybitEnvironment.MAINNET
STARTING_BALANCE: Final = "10_000 USDT"


class EmaSideTrailingConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    atr_period: PositiveInt = 14
    trailing_atr_multiple: PositiveFloat = 3.0
    fast_ema_period: PositiveInt = 10
    slow_ema_period: PositiveInt = 20
    warmup_bars: PositiveInt = 200
    max_trailing_stop_failures: PositiveInt = 3


class EmaSideTrailing(Strategy):
    config: EmaSideTrailingConfig

    def __init__(self, config: EmaSideTrailingConfig) -> None:
        PyCondition.is_true(
            config.fast_ema_period < config.slow_ema_period,
            f"{config.fast_ema_period=} must be less than {config.slow_ema_period=}",
        )
        super().__init__(config)

        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)
        self.atr = AverageTrueRange(config.atr_period)

        self.instrument: Instrument | None = None
        self.entry_order: Order | None = None
        self.trailing_stop: Order | None = None
        self.trailing_stop_failures = 0

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return

        for indicator in (self.fast_ema, self.slow_ema, self.atr):
            self.register_indicator_for_bars(self.config.bar_type, indicator)

        self.subscribe_trade_ticks(self.config.instrument_id)

        warmup = self.config.bar_type.spec.timedelta * self.config.warmup_bars
        self.request_bars(
            self.config.bar_type,
            start=self.clock.utc_now() - warmup,
            limit=self.config.warmup_bars,
            callback=lambda _: self.subscribe_bars(self.config.bar_type),
        )

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            self.log.info("Warming up indicators", LogColor.BLUE)
            return

        if bar.is_single_price():
            return

        if not self.portfolio.is_flat(self.config.instrument_id):
            return

        entry_side = OrderSide.BUY if self.fast_ema.value >= self.slow_ema.value else OrderSide.SELL
        self._submit_entry(entry_side)

    def on_event(self, event: Event) -> None:
        match event:
            case OrderFilled() if self._is_trailing_stop(event):
                self.trailing_stop = None
            case OrderAccepted() if self._is_trailing_stop(event):
                self.trailing_stop_failures = 0
            case OrderDenied() | OrderRejected() if self._is_trailing_stop(event):
                self._flatten_position(event.reason)
            case OrderDenied() | OrderRejected() if self._is_entry(event):
                self.entry_order = None
            case PositionOpened() | PositionChanged() if self.trailing_stop is None:
                self._attach_trailing_stop(event)
            case PositionClosed():
                self.entry_order = None
                self.trailing_stop = None

    def on_stop(self) -> None:
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)
        self.unsubscribe_bars(self.config.bar_type)

    def on_reset(self) -> None:
        self.fast_ema.reset()
        self.slow_ema.reset()
        self.atr.reset()
        self.entry_order = None
        self.trailing_stop = None
        self.trailing_stop_failures = 0

    def _is_trailing_stop(self, event: OrderEvent) -> bool:
        return (
            self.trailing_stop is not None
            and event.client_order_id == self.trailing_stop.client_order_id
        )

    def _is_entry(self, event: OrderEvent) -> bool:
        return (
            self.entry_order is not None
            and event.client_order_id == self.entry_order.client_order_id
        )

    def _flatten_position(self, reason: str) -> None:
        self.trailing_stop = None
        self.trailing_stop_failures += 1
        self.log.error(f"Trailing stop failed ({reason}); closing position")
        self.close_all_positions(self.config.instrument_id)

        if self.trailing_stop_failures >= self.config.max_trailing_stop_failures:
            self.log.error(f"Stopping after {self.trailing_stop_failures} trailing stop failures")
            self.stop()

    def _attach_trailing_stop(self, event: PositionOpened | PositionChanged) -> None:
        if self.entry_order is None or event.opening_order_id != self.entry_order.client_order_id:
            return

        exit_side = OrderSide.SELL if event.entry == OrderSide.BUY else OrderSide.BUY
        self._submit_trailing_stop(exit_side, event.position_id, event.quantity.as_decimal())

    def _submit_entry(self, order_side: OrderSide) -> None:
        if self.entry_order is not None:
            return

        if (instrument := self.instrument) is None:
            self.log.error("Cannot submit entry: no instrument loaded")
            return

        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=order_side,
            quantity=instrument.make_qty(self.config.trade_size),
        )
        self.entry_order = order
        self.submit_order(order)

    def _submit_trailing_stop(
        self, order_side: OrderSide, position_id: PositionId, quantity: Decimal
    ) -> None:
        if (instrument := self.instrument) is None:
            self.log.error("Cannot submit trailing stop: no instrument loaded")
            return

        atr_offset = self.atr.value * self.config.trailing_atr_multiple
        offset = max(
            Decimal(f"{atr_offset:.{instrument.price_precision}f}"),
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
    provider_config = InstrumentProviderConfig(load_ids=frozenset({INSTRUMENT_ID}))
    node_config = TradingNodeConfig(
        trader_id=TRADER_ID,
        logging=LoggingConfig(use_pyo3=True),
        exec_engine=LiveExecEngineConfig(
            reconciliation=False,
            graceful_shutdown_on_exception=True,
        ),
        data_clients={
            BYBIT: BybitDataClientConfig(
                environment=ENVIRONMENT,
                instrument_provider=provider_config,
                product_types=(PRODUCT_TYPE,),
            ),
        },
        exec_clients={
            BYBIT: SandboxExecutionClientConfig(
                venue=BYBIT,
                starting_balances=[STARTING_BALANCE],
            ),
        },
    )

    node = TradingNode(config=node_config)
    node.trader.add_strategy(
        EmaSideTrailing(
            config=EmaSideTrailingConfig(
                instrument_id=INSTRUMENT_ID,
                bar_type=BAR_TYPE,
                trade_size=TRADE_SIZE,
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
    node = build_node()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main()
