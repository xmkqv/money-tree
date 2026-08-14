from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from lumibot.entities import Order, Position

from money_tree.model import Direction, OpeningRangeState, OrderRole, StrategyName
from money_tree.opening_range import Breakout, find_breakout, should_flatten, to_market_datetime
from money_tree.risk import has_reached_loss_limit, size_position
from money_tree.strategies.base import TradingStrategy

INSTRUMENT = "SPY"
MARKET = "NYSE"
BAR_INTERVAL = "minute"
SLEEP_INTERVAL = "1M"
STATE_PATH = Path(".money-tree/opening-range-live-state.json")
N_BAR_HISTORY = 390


class OpeningRangeStrategy(TradingStrategy):
    strategy_name = StrategyName.OPENING_RANGE
    protective_stop_time_in_force = "day"
    parameters: ClassVar[dict[str, object]] = {
        "instrument": INSTRUMENT,
        "state_path": STATE_PATH,
        "persisted": True,
    }

    @property
    def opening_range_state(self) -> OpeningRangeState:
        state = self.state.strategy_state
        if not isinstance(state, OpeningRangeState):
            raise RuntimeError("opening-range state is not initialized")
        return state

    def initialize(self) -> None:
        self.sleeptime = SLEEP_INTERVAL
        self.minutes_before_closing = 5
        self.set_market(MARKET)
        self._initialize_trading_state(
            instrument=str(self.parameters["instrument"]),
            state_path=Path(str(self.parameters["state_path"])),
            persisted=bool(self.parameters["persisted"]),
        )

    def on_trading_iteration(self) -> None:
        observed_at = to_market_datetime(self.get_datetime())
        if not self._try_start_session(observed_at.date()):
            return
        if should_flatten(observed_at):
            self._flatten("end of trading session", disable=True)
            return
        if (
            self.state.position.direction is not Direction.FLAT
            and self._get_order(OrderRole.PROTECTIVE_STOP) is None
            and self._get_order(OrderRole.FLATTEN) is None
        ):
            protective_stop_price = self.opening_range_state.protective_stop_price
            if protective_stop_price is None:
                self._flatten("protective stop price is missing", disable=True)
                return
            self._replace_protective_stop(protective_stop_price)
        mark_price = self.get_last_price(self.instrument)
        if mark_price is not None and has_reached_loss_limit(
            self.state.position,
            Decimal(str(mark_price)),
        ):
            self._flatten("session loss limit reached", disable=True)
            return
        if self.state.disabled or self.state.entered:
            return
        if (
            self.state.position.direction is not Direction.FLAT
            or self._get_order(OrderRole.ENTRY) is not None
        ):
            return
        bars = self.get_historical_prices(
            self.instrument,
            N_BAR_HISTORY,
            BAR_INTERVAL,
            include_after_hours=False,
        )
        if bars is None or bars.empty:
            return
        breakout = find_breakout(bars.polars_df, observed_at.date(), observed_at)
        if breakout is not None:
            self._submit_entry_order(breakout)

    def before_market_closes(self) -> None:
        self._flatten("end of trading session", disable=True)

    def _try_start_session(self, session_date: date) -> bool:
        if self.state.session_date == session_date:
            return True
        if self.state.position.direction is not Direction.FLAT:
            self._flatten("position carried into a new trading session", disable=True)
            return False
        for role in OrderRole:
            self._cancel_order(role)
        self.state.clear_strategy_position()
        self._start_session(session_date, keep_position=False)
        return True

    def _submit_entry_order(self, breakout: Breakout) -> None:
        observed_price = self.get_last_price(self.instrument)
        if observed_price is None:
            return
        entry_price = Decimal(str(observed_price))
        protective_stop_price = Decimal(str(round(breakout.protective_stop_price, 2)))
        quantity = size_position(entry_price, protective_stop_price, breakout.direction)
        if quantity <= 0 or quantity * entry_price < Decimal("1"):
            self.log_message("Breakout skipped because no valid quantity exists")
            return
        vendor_order_side = (
            Order.OrderSide.BUY if breakout.direction is Direction.LONG else Order.OrderSide.SELL
        )
        order = self.create_order(
            self.instrument,
            quantity,
            vendor_order_side,
            time_in_force="day",
            custom_params={"client_order_id": self._create_order_id(OrderRole.ENTRY)},
        )
        submitted_order = self.submit_order(order)
        if submitted_order.status == Order.OrderStatus.ERROR:
            self.log_message("Broker rejected the breakout entry order", color="red")
            return
        self.opening_range_state.protective_stop_price = protective_stop_price
        self._set_order(OrderRole.ENTRY, submitted_order)
        self._save_state()

    def _record_entry_fill(self, position: Position, price: float) -> None:
        protective_stop_price = self.opening_range_state.protective_stop_price
        if protective_stop_price is None:
            self._flatten("protective stop price is missing", disable=True)
            return
        self._replace_protective_stop(protective_stop_price)
