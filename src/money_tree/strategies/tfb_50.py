from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

import polars as pl
from lumibot.entities import Order, Position

from money_tree.bars import market_datetime_expression, normalize_price_bars
from money_tree.indicators import indicator_plan
from money_tree.model import Direction, OrderRole, StrategyName, Tfb50State
from money_tree.opening_range import to_market_datetime
from money_tree.strategies.base import TradingStrategy

INSTRUMENT = "SPY"
MARKET = "NYSE"
BAR_INTERVAL = "day"
SLEEP_INTERVAL = "1D"
STATE_PATH = Path(".money-tree/tfb-50-live-state.json")
N_BAR_HISTORY = 60
N_BAR_SMA_SLOPE = 3
ADX_MAX = 20.0
RSI_EXIT_MAX = 50.0
POSITION_FRACTION = Decimal("0.10")
SWING_SPAN = 2
USD_PRICE_TICK = 0.01
QUANTITY_STEP = Decimal("1")


@dataclass(frozen=True, slots=True)
class EntryDecision:
    protective_stop_price: float


class ExitSignal(StrEnum):
    PREVIOUS_LOW = "close below previous low"
    EMERGENCY = "close below 20 SMA with RSI below 50"


def _floor_price(value: float, price_tick: float) -> float:
    tick = Decimal(str(price_tick))
    units = (Decimal(str(value)) / tick).to_integral_value(rounding=ROUND_DOWN)
    return float(units * tick)


def _swing_low_condition(span: int = SWING_SPAN) -> pl.Expr:
    low = pl.col("low")
    return pl.all_horizontal(
        low < low.shift(offset) for offset in range(-span, span + 1) if offset != 0
    )


def latest_confirmed_swing_low(
    frame: pl.DataFrame,
    *,
    swing_span: int = SWING_SPAN,
    price_tick: float = USD_PRICE_TICK,
) -> float | None:
    if swing_span <= 0 or price_tick <= 0:
        raise ValueError("swing-low settings must be positive")
    value = (
        normalize_price_bars(frame)
        .lazy()
        .select(pl.col("low").filter(_swing_low_condition(swing_span)).last())
        .collect()
        .item()
    )
    if value is None:
        return None
    return _floor_price(float(value), price_tick)


def highest_confirmed_swing_low_since(
    frame: pl.DataFrame,
    entered_on: date,
    *,
    swing_span: int = SWING_SPAN,
    price_tick: float = USD_PRICE_TICK,
) -> float | None:
    if swing_span <= 0 or price_tick <= 0:
        raise ValueError("swing-low settings must be positive")
    values = normalize_price_bars(frame).with_columns(
        market_datetime_expression(frame).alias("market_datetime")
    )
    value = (
        values.lazy()
        .filter(
            _swing_low_condition(swing_span) & (pl.col("market_datetime").dt.date() >= entered_on)
        )
        .select(pl.col("low").max())
        .collect()
        .item()
    )
    if value is None:
        return None
    return _floor_price(float(value), price_tick)


def decide_entry(
    frame: pl.DataFrame,
    *,
    sma_slope_span: int = N_BAR_SMA_SLOPE,
    swing_span: int = SWING_SPAN,
    price_tick: float = USD_PRICE_TICK,
) -> EntryDecision | None:
    if sma_slope_span <= 0:
        raise ValueError("SMA slope span must be positive")
    protective_stop_price = latest_confirmed_swing_low(
        frame,
        swing_span=swing_span,
        price_tick=price_tick,
    )
    if protective_stop_price is None:
        return None
    summary = (
        indicator_plan(frame)
        .select(
            previous_high=pl.col("high").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_50=pl.col("sma_50").last(),
            prior_sma_50=pl.col("sma_50").slice(-(sma_slope_span + 1), 1).first(),
            adx_14=pl.col("adx_14").last(),
        )
        .filter(
            pl.all_horizontal(pl.all().is_not_null())
            & (pl.col("close") > pl.col("sma_50"))
            & (pl.col("sma_50") > pl.col("prior_sma_50"))
            & (pl.col("adx_14") < ADX_MAX)
            & (pl.col("close") > pl.col("previous_high"))
        )
        .collect()
    )
    if summary.is_empty():
        return None
    close_price = float(summary.item(0, "close"))
    if protective_stop_price <= 0 or protective_stop_price >= close_price:
        return None
    return EntryDecision(protective_stop_price=protective_stop_price)


def decide_exit(frame: pl.DataFrame) -> ExitSignal | None:
    summary = (
        indicator_plan(frame)
        .select(
            previous_low=pl.col("low").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_20=pl.col("sma_20").last(),
            rsi_14=pl.col("rsi_14").last(),
        )
        .collect()
    )
    if summary.is_empty():
        return None
    current = summary.row(0, named=True)
    if (
        current["close"] is not None
        and current["previous_low"] is not None
        and current["close"] < current["previous_low"]
    ):
        return ExitSignal.PREVIOUS_LOW
    emergency_values = (current["close"], current["sma_20"], current["rsi_14"])
    if all(value is not None for value in emergency_values) and (
        current["close"] < current["sma_20"] and current["rsi_14"] < RSI_EXIT_MAX
    ):
        return ExitSignal.EMERGENCY
    return None


class Tfb50Strategy(TradingStrategy):
    strategy_name = StrategyName.TFB_50
    protective_stop_time_in_force = "gtc"
    parameters: ClassVar[dict[str, object]] = {
        "instrument": INSTRUMENT,
        "state_path": STATE_PATH,
        "persisted": True,
        "position_fraction": POSITION_FRACTION,
        "sma_slope_span": N_BAR_SMA_SLOPE,
        "swing_span": SWING_SPAN,
    }

    @property
    def tfb_state(self) -> Tfb50State:
        state = self.state.strategy_state
        if not isinstance(state, Tfb50State):
            raise RuntimeError("tfb-50 state is not initialized")
        return state

    def initialize(self) -> None:
        self.sleeptime = SLEEP_INTERVAL
        self.set_market(MARKET)
        self.position_fraction = Decimal(str(self.parameters["position_fraction"]))
        self.sma_slope_span = int(Decimal(str(self.parameters["sma_slope_span"])))
        self.swing_span = int(Decimal(str(self.parameters["swing_span"])))
        if not Decimal("0") < self.position_fraction <= Decimal("1"):
            raise ValueError("position fraction must be greater than zero and at most one")
        if self.sma_slope_span <= 0 or self.swing_span <= 0:
            raise ValueError("strategy spans must be positive")
        self._initialize_trading_state(
            instrument=str(self.parameters["instrument"]),
            state_path=Path(str(self.parameters["state_path"])),
            persisted=bool(self.parameters["persisted"]),
        )

    def on_trading_iteration(self) -> None:
        observed_at = to_market_datetime(self.get_datetime())
        self._start_session(observed_at.date(), keep_position=True)
        position = self.get_position(self.instrument)
        if position is not None and float(position.quantity) < 0:
            raise RuntimeError("tfb-50 supports long positions only")
        if self.state.position.direction is not Direction.FLAT:
            if position is None:
                raise RuntimeError("broker position is missing during tfb-50 trading")
            if (
                self._get_order(OrderRole.PROTECTIVE_STOP) is None
                and self._get_order(OrderRole.FLATTEN) is None
            ):
                protective_stop_price = (
                    self.tfb_state.active_protective_stop_price
                    or self.tfb_state.initial_protective_stop_price
                )
                if protective_stop_price is None:
                    self._flatten("protective stop state is missing", disable=True)
                    return
                self._replace_protective_stop(protective_stop_price)
        try:
            bars = self.get_historical_prices(
                self.instrument,
                N_BAR_HISTORY,
                BAR_INTERVAL,
                include_after_hours=False,
            )
        except ValueError as error:
            if "Not enough historical data" not in str(error):
                raise
            return
        if bars is None or bars.empty:
            return
        frame = bars.polars_df
        if position is not None and float(position.quantity) > 0:
            self._manage_position(frame)
            return
        if any(self._get_order(role) is not None for role in OrderRole):
            return
        if self.state.disabled or self.state.entered:
            return
        self.state.clear_strategy_position()
        decision = decide_entry(
            frame,
            sma_slope_span=self.sma_slope_span,
            swing_span=self.swing_span,
        )
        if decision is not None:
            self._submit_entry_order(decision)

    def _submit_entry_order(self, decision: EntryDecision) -> None:
        observed_price = self.get_last_price(self.instrument)
        if observed_price is None:
            return
        entry_price = Decimal(str(observed_price))
        protective_stop_price = Decimal(str(decision.protective_stop_price))
        if entry_price <= protective_stop_price:
            return
        portfolio_value = Decimal(str(self.get_portfolio_value()))
        quantity = (portfolio_value * self.position_fraction / entry_price).quantize(
            QUANTITY_STEP,
            rounding=ROUND_DOWN,
        )
        if quantity <= 0:
            return
        self.tfb_state.initial_protective_stop_price = protective_stop_price
        self.tfb_state.active_protective_stop_price = protective_stop_price
        order = self.create_order(
            self.instrument,
            quantity,
            Order.OrderSide.BUY,
            time_in_force="day",
            custom_params={"client_order_id": self._create_order_id(OrderRole.ENTRY)},
        )
        submitted_order = self.submit_order(order)
        if submitted_order.status == Order.OrderStatus.ERROR:
            self.state.clear_strategy_position()
            self._save_state()
            return
        self._set_order(OrderRole.ENTRY, submitted_order)
        self._save_state()

    def _record_entry_fill(self, position: Position, price: float) -> None:
        entry_price = Decimal(str(position.avg_fill_price or price))
        self.tfb_state.entered_on = (
            self.tfb_state.entered_on or to_market_datetime(self.get_datetime()).date()
        )
        initial_protective_stop_price = self.tfb_state.initial_protective_stop_price
        if initial_protective_stop_price is None:
            self._flatten("initial protective stop state is missing", disable=True)
            return
        if entry_price <= initial_protective_stop_price:
            self._flatten("entry filled below the protective stop", disable=True)
            return
        self._replace_protective_stop(initial_protective_stop_price)

    def _manage_position(self, frame: pl.DataFrame) -> None:
        exit_signal = decide_exit(frame)
        if exit_signal is not None:
            self._flatten(exit_signal.value, disable=False)
            return
        entered_on = self.tfb_state.entered_on
        initial_protective_stop_price = self.tfb_state.initial_protective_stop_price
        active_protective_stop_price = self.tfb_state.active_protective_stop_price
        if (
            entered_on is None
            or initial_protective_stop_price is None
            or active_protective_stop_price is None
        ):
            self._flatten("tfb-50 position state is incomplete", disable=True)
            return
        swing_low = highest_confirmed_swing_low_since(
            frame,
            entered_on,
            swing_span=self.swing_span,
        )
        desired_protective_stop_price = initial_protective_stop_price
        if swing_low is not None:
            desired_protective_stop_price = max(
                desired_protective_stop_price,
                Decimal(str(swing_low)),
            )
        close_price = Decimal(str(normalize_price_bars(frame).item(-1, "close")))
        if close_price <= desired_protective_stop_price:
            self._flatten("close reached the protective stop", disable=False)
            return
        if desired_protective_stop_price > active_protective_stop_price:
            self._replace_protective_stop(desired_protective_stop_price)
        else:
            self._save_state()

    def _record_active_protective_stop_price(self, protective_stop_price: Decimal) -> None:
        self.tfb_state.active_protective_stop_price = protective_stop_price

    def _on_entry_order_failure(self, *, canceled: bool) -> None:
        if not canceled or self.state.position.direction is Direction.FLAT:
            self.state.clear_strategy_position()
