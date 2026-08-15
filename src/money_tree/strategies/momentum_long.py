from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import ClassVar

import polars as pl
from lumibot.entities import Order, Position

from money_tree.indicators import calculate_indicators
from money_tree.indicators import indicator_plan as _indicator_plan
from money_tree.model import Direction, MomentumLongState, OrderRole, StrategyName
from money_tree.opening_range import to_market_datetime
from money_tree.strategies.base import TradingStrategy

INSTRUMENT = "SPY"
MARKET = "NYSE"
BAR_INTERVAL = "day"
SLEEP_INTERVAL = "1D"
STATE_PATH = Path(".money-tree/momentum-long-live-state.json")
N_BAR_HISTORY = 260
RSI_MIN = 50.0
RSI_MAX = 70.0
ADX_MIN = 25.0
POSITION_FRACTION = Decimal("0.10")
REWARD_RISK_MIN = 2.0
ATR_MULTIPLIER = 1.5
SWING_SPAN = 2
USD_PRICE_TICK = 0.01
QUANTITY_STEP = Decimal("1")


@dataclass(frozen=True, slots=True)
class EntryDecision:
    protective_stop_price: float


def _floor_price(value: float, price_tick: float) -> float:
    tick = Decimal(str(price_tick))
    units = (Decimal(str(value)) / tick).to_integral_value(rounding=ROUND_DOWN)
    return float(units * tick)


def _swing_low_condition(span: int) -> pl.Expr:
    low = pl.col("low")
    return pl.all_horizontal(
        low < low.shift(offset) for offset in range(-span, span + 1) if offset != 0
    )


def decide_entry(
    frame: pl.DataFrame,
    *,
    swing_span: int = SWING_SPAN,
    price_tick: float = USD_PRICE_TICK,
) -> EntryDecision | None:
    if price_tick <= 0:
        raise ValueError("price tick must be positive")
    if swing_span <= 0:
        raise ValueError("swing span must be positive")
    summary = (
        _indicator_plan(frame)
        .select(
            previous_close=pl.col("close").slice(-2, 1).first(),
            previous_sma_20=pl.col("sma_20").slice(-2, 1).first(),
            close=pl.col("close").last(),
            sma_20=pl.col("sma_20").last(),
            sma_50=pl.col("sma_50").last(),
            sma_200=pl.col("sma_200").last(),
            rsi_14=pl.col("rsi_14").last(),
            adx_14=pl.col("adx_14").last(),
            swing_low=pl.col("low").filter(_swing_low_condition(swing_span)).last(),
        )
        .filter(
            pl.all_horizontal(pl.all().is_not_null())
            & (pl.col("previous_close") < pl.col("previous_sma_20"))
            & (pl.col("close") > pl.col("sma_20"))
            & (pl.col("close") > pl.col("sma_50"))
            & (pl.col("sma_50") > pl.col("sma_200"))
            & pl.col("rsi_14").is_between(RSI_MIN, RSI_MAX, closed="both")
            & (pl.col("adx_14") > ADX_MIN)
        )
        .collect()
    )
    if summary.is_empty():
        return None
    current = summary.row(0, named=True)
    protective_stop_price = _floor_price(float(current["swing_low"]) - price_tick, price_tick)
    close_price = float(current["close"])
    if protective_stop_price <= 0 or protective_stop_price >= close_price:
        return None
    return EntryDecision(protective_stop_price=protective_stop_price)


def should_flatten(frame: pl.DataFrame) -> bool:
    return bool(
        _indicator_plan(frame)
        .select(
            ((pl.col("close") < pl.col("sma_20")) & (pl.col("rsi_14") < RSI_MIN))
            .last()
            .fill_null(False)
        )
        .collect()
        .item()
    )


def calculate_trailing_stop_price(
    highest_price: float,
    average_true_range: float,
    initial_protective_stop_price: float,
    *,
    multiplier: float = ATR_MULTIPLIER,
    price_tick: float = USD_PRICE_TICK,
) -> float:
    if highest_price <= 0 or average_true_range <= 0 or initial_protective_stop_price <= 0:
        raise ValueError("prices and average true range must be positive")
    if multiplier <= 0 or price_tick <= 0:
        raise ValueError("trailing-stop settings must be positive")
    candidate = max(
        initial_protective_stop_price,
        highest_price - multiplier * average_true_range,
    )
    return _floor_price(candidate, price_tick)


class MomentumLongStrategy(TradingStrategy):
    strategy_name = StrategyName.MOMENTUM_LONG
    protective_stop_time_in_force = "gtc"
    parameters: ClassVar[dict[str, object]] = {
        "instrument": INSTRUMENT,
        "state_path": STATE_PATH,
        "persisted": True,
        "position_fraction": POSITION_FRACTION,
        "reward_risk_min": REWARD_RISK_MIN,
        "atr_multiplier": ATR_MULTIPLIER,
        "swing_span": SWING_SPAN,
    }

    @property
    def momentum_state(self) -> MomentumLongState:
        state = self.state.strategy_state
        if not isinstance(state, MomentumLongState):
            raise RuntimeError("momentum-long state is not initialized")
        return state

    def initialize(self) -> None:
        self.sleeptime = SLEEP_INTERVAL
        self.set_market(MARKET)
        self.position_fraction = Decimal(str(self.parameters["position_fraction"]))
        self.reward_risk_min = float(str(self.parameters["reward_risk_min"]))
        self.atr_multiplier = float(str(self.parameters["atr_multiplier"]))
        self.swing_span = int(Decimal(str(self.parameters["swing_span"])))
        if not Decimal("0") < self.position_fraction <= Decimal("1"):
            raise ValueError("position fraction must be greater than zero and at most one")
        if self.reward_risk_min <= 0 or self.atr_multiplier <= 0 or self.swing_span <= 0:
            raise ValueError("strategy parameters must be positive")
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
            raise RuntimeError("momentum-long supports long positions only")
        if self.state.position.direction is not Direction.FLAT:
            if position is None:
                raise RuntimeError("broker position is missing during momentum-long trading")
            if (
                self._get_order(OrderRole.PROTECTIVE_STOP) is None
                and self._get_order(OrderRole.FLATTEN) is None
            ):
                protective_stop_price = (
                    self.momentum_state.active_protective_stop_price
                    or self.momentum_state.initial_protective_stop_price
                )
                if protective_stop_price is None:
                    self._flatten("protective stop state is missing", disable=True)
                    return
                self._replace_protective_stop(protective_stop_price)
        bars = self.get_historical_prices(
            self.instrument,
            N_BAR_HISTORY,
            BAR_INTERVAL,
            include_after_hours=False,
        )
        if bars is None or bars.empty:
            return
        frame = bars.polars_df
        if position is not None and float(position.quantity) > 0:
            self._manage_position(frame, position)
            return
        if any(self._get_order(role) is not None for role in OrderRole):
            return
        if self.state.disabled or self.state.entered:
            return
        self.state.clear_strategy_position()
        decision = decide_entry(frame, swing_span=self.swing_span)
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
        risk = entry_price - protective_stop_price
        self.momentum_state.entry_price = entry_price
        self.momentum_state.initial_protective_stop_price = protective_stop_price
        self.momentum_state.active_protective_stop_price = protective_stop_price
        self.momentum_state.trail_activation_price = (
            entry_price + Decimal(str(self.reward_risk_min)) * risk
        )
        self.momentum_state.highest_price = entry_price
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
        initial_protective_stop_price = self.momentum_state.initial_protective_stop_price
        if initial_protective_stop_price is None:
            self._flatten("initial protective stop state is missing", disable=True)
            return
        risk = entry_price - initial_protective_stop_price
        if risk <= 0:
            self._flatten("entry filled below the protective stop", disable=True)
            return
        self.momentum_state.entry_price = entry_price
        self.momentum_state.highest_price = max(
            self.momentum_state.highest_price or entry_price,
            entry_price,
        )
        self.momentum_state.trail_activation_price = (
            entry_price + Decimal(str(self.reward_risk_min)) * risk
        )
        self._replace_protective_stop(initial_protective_stop_price)

    def _manage_position(self, frame: pl.DataFrame, position: Position) -> None:
        values = calculate_indicators(frame)
        current = values.row(-1, named=True)
        if should_flatten(values):
            self._flatten("close below 20 SMA with RSI below 50", disable=False)
            return
        average_true_range = current["atr_14"]
        if average_true_range is None:
            return
        entry_price = self.momentum_state.entry_price
        initial_protective_stop_price = self.momentum_state.initial_protective_stop_price
        if entry_price is None or initial_protective_stop_price is None:
            self._flatten("momentum position state is incomplete", disable=True)
            return
        trail_activation_price = self.momentum_state.trail_activation_price
        if trail_activation_price is None:
            trail_activation_price = entry_price + Decimal(str(self.reward_risk_min)) * (
                entry_price - initial_protective_stop_price
            )
            self.momentum_state.trail_activation_price = trail_activation_price
        high_price = Decimal(str(current["high"]))
        self.momentum_state.highest_price = max(
            self.momentum_state.highest_price or entry_price,
            high_price,
        )
        desired_protective_stop_price = initial_protective_stop_price
        if self.momentum_state.highest_price >= trail_activation_price:
            desired_protective_stop_price = Decimal(
                str(
                    calculate_trailing_stop_price(
                        float(self.momentum_state.highest_price),
                        float(average_true_range),
                        float(initial_protective_stop_price),
                        multiplier=self.atr_multiplier,
                    )
                )
            )
        if Decimal(str(current["close"])) <= desired_protective_stop_price:
            self._flatten("close reached the protective stop", disable=False)
            return
        active_protective_stop_price = self.momentum_state.active_protective_stop_price
        if (
            active_protective_stop_price is None
            or desired_protective_stop_price
            >= active_protective_stop_price + Decimal(str(USD_PRICE_TICK))
        ):
            self._replace_protective_stop(desired_protective_stop_price)
        else:
            self._save_state()

    def _record_active_protective_stop_price(self, protective_stop_price: Decimal) -> None:
        self.momentum_state.active_protective_stop_price = protective_stop_price

    def _on_entry_order_failure(self, *, canceled: bool) -> None:
        if not canceled or self.state.position.direction is Direction.FLAT:
            self.state.clear_strategy_position()
