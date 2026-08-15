from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from lumibot.entities import Asset, Order
from lumibot.strategies import Strategy

from money_tree.model import OrderSide

HISTORY_SHORTAGE_PREFIX = "Not enough historical data."


@dataclass(frozen=True, slots=True)
class TradingParameters:
    instrument: str
    state_path: Path | None

    @classmethod
    def parse(cls, values: Mapping[str, object]) -> TradingParameters:
        instrument = values.get("instrument")
        if not isinstance(instrument, str) or not instrument:
            raise ValueError("instrument parameter must be nonempty text")
        state_path_value = values.get("state_path")
        if state_path_value is None:
            state_path = None
        elif isinstance(state_path_value, Path):
            state_path = state_path_value
        elif isinstance(state_path_value, str):
            state_path = Path(state_path_value)
        else:
            raise TypeError("state_path parameter must be a path, text, or null")
        return cls(instrument=instrument, state_path=state_path)


class RuntimeLumibot:
    def __init__(self, strategy: Strategy) -> None:
        self.strategy = strategy

    @property
    def is_backtesting(self) -> bool:
        return bool(self.strategy.is_backtesting)

    @property
    def parameters(self) -> TradingParameters:
        return TradingParameters.parse(self.strategy.parameters)

    def find_order(self, identifier: str) -> Order | None:
        order = self.strategy.get_order(identifier)
        if order is not None or self.is_backtesting:
            return order
        return self.strategy.broker._pull_order(identifier, self.strategy.name)

    def wait_orders_clear(self) -> bool:
        return bool(self.strategy.broker.wait_orders_clear(self.strategy.name))

    def order_side(self, order: Order) -> OrderSide:
        if order.is_buy_order():
            return OrderSide.BUY
        if order.is_sell_order():
            return OrderSide.SELL
        raise RuntimeError(f"unsupported fill order side {order.side!r}")

    def find_price_bars(
        self,
        asset: Asset,
        n_bar: int,
        interval: str,
        *,
        include_after_hours: bool,
    ) -> pl.DataFrame | None:
        try:
            bars = self.strategy.get_historical_prices(
                asset,
                n_bar,
                interval,
                include_after_hours=include_after_hours,
            )
        except ValueError as error:
            if str(error).startswith(HISTORY_SHORTAGE_PREFIX):
                return None
            raise
        if bars is None:
            return None
        frame = bars.polars_df
        if not isinstance(frame, pl.DataFrame):
            raise TypeError("LumiBot price bars must use a Polars DataFrame")
        return None if frame.is_empty() else frame
