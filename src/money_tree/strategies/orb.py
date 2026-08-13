from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from lumibot.entities import Asset, Order, Position
from lumibot.strategies import Strategy

from money_tree.orb import (
    MARKET_TIMEZONE,
    Breakout,
    BreakoutSide,
    find_breakout,
    is_latest_breakout,
    should_close,
)
from money_tree.risk import size_position
from money_tree.state import StateStore

SYMBOL = "SPY"
MARKET = "NYSE"
TIMESTEP = "minute"
SLEEPTIME = "1M"
STATE_PATH = Path(".money-tree/orb-state.json")
N_HISTORY_BAR = 390


class OpeningRangeBreakout(Strategy):
    parameters: ClassVar[dict[str, object]] = {
        "symbol": SYMBOL,
        "state_path": STATE_PATH,
        "persist_state": True,
    }

    def initialize(self) -> None:
        self.sleeptime = SLEEPTIME
        self.minutes_before_closing = 5
        self.set_market(MARKET)
        self.asset = Asset(str(self.parameters["symbol"]))
        state_path = Path(str(self.parameters["state_path"]))
        self.state_store = StateStore(state_path if self.parameters["persist_state"] else None)
        self.state = self.state_store.load()
        self.entry_order: Order | None = None
        self.stop_order: Order | None = None
        self.exit_order: Order | None = None
        self._load_orders()

    def on_trading_iteration(self) -> None:
        moment = self._market_datetime(self.get_datetime())
        if not self._prepare_session(moment.date()):
            return
        if should_close(moment):
            self._flatten("end of session", disable=True)
            return
        if (
            self.state.position_quantity != 0
            and self.stop_order is None
            and self.exit_order is None
        ):
            self._replace_stop()
        mark_price = self.get_last_price(self.asset)
        if mark_price is not None and self.state.has_daily_loss(Decimal(str(mark_price))):
            self._flatten("daily loss reached", disable=True)
            return
        if self.state.disabled or self.state.traded:
            return
        if self.state.position_quantity != 0 or self.entry_order is not None:
            return
        bars = self.get_historical_prices(
            self.asset,
            N_HISTORY_BAR,
            TIMESTEP,
            include_after_hours=False,
        )
        if bars is None or bars.empty:
            return
        breakout = find_breakout(bars.pandas_df, moment.date(), moment)
        if breakout is None or not is_latest_breakout(
            bars.pandas_df, breakout, moment.date(), moment
        ):
            return
        self._submit_entry(breakout)

    def before_market_closes(self) -> None:
        self._flatten("end of session", disable=True)

    def on_partially_filled_order(
        self,
        position: Position,
        order: Order,
        price: float,
        quantity: float,
        multiplier: float,
    ) -> None:
        self._record_fill(order, price, quantity, complete=False)

    def on_filled_order(
        self,
        position: Position,
        order: Order,
        price: float,
        quantity: float,
        multiplier: float,
    ) -> None:
        self._record_fill(order, price, quantity, complete=True)

    def on_canceled_order(self, order: Order) -> None:
        role = self._order_role(order)
        if role == "entry":
            self.entry_order = None
            self.state.entry_order_id = None
            self._save_state()
        elif role == "stop" and self.state.position_quantity != 0:
            self._flatten("protective stop canceled", disable=True)

    def on_error_order(self, order: Order, error: Exception | None = None) -> None:
        role = self._order_role(order)
        if role == "entry":
            self.entry_order = None
            self.state.entry_order_id = None
            self._save_state()
        elif role == "stop":
            self._flatten(f"protective stop rejected: {error}", disable=True)
        elif role == "exit":
            raise RuntimeError(f"flatten order rejected: {error}")

    def on_abrupt_closing(self) -> None:
        self.sell_all(cancel_open_orders=True)

    def _prepare_session(self, trading_date: date) -> bool:
        if self.state.trading_date == trading_date:
            return True
        if self.state.position_quantity != 0:
            self._flatten("position carried into a new session", disable=True)
            return False
        self.state.reset(trading_date)
        self.entry_order = None
        self.stop_order = None
        self.exit_order = None
        self._save_state()
        return True

    def _submit_entry(self, breakout: Breakout) -> None:
        last_price = self.get_last_price(self.asset)
        if last_price is None:
            return
        entry_price = Decimal(str(last_price))
        stop_price = Decimal(str(round(breakout.stop, 2)))
        quantity = size_position(entry_price, stop_price, breakout.side)
        if quantity <= 0 or quantity * entry_price < Decimal("1"):
            self.log_message("Breakout skipped because no valid risk-sized quantity exists")
            return
        side = Order.OrderSide.BUY if breakout.side is BreakoutSide.LONG else Order.OrderSide.SELL
        order = self.create_order(
            self.asset,
            quantity,
            side,
            time_in_force="day",
            custom_params={"client_order_id": self._client_order_id("entry")},
        )
        submitted = self.submit_order(order)
        if submitted.status == Order.OrderStatus.ERROR:
            self.log_message("Broker rejected the breakout entry", color="red")
            return
        self.entry_order = submitted
        self.state.entry_order_id = str(submitted.identifier)
        self.state.stop_price = stop_price
        self._save_state()

    def _record_fill(
        self,
        order: Order,
        price: float,
        quantity: float,
        *,
        complete: bool,
    ) -> None:
        role = self._order_role(order)
        if role is None:
            return
        side = str(getattr(order.side, "value", order.side)).lower().split(".")[-1]
        self.state.record_fill(side, Decimal(str(price)), Decimal(str(quantity)))
        if role == "entry":
            self.state.traded = True
            if complete:
                self.state.entry_order_id = None
                self.entry_order = None
            self._replace_stop()
        elif role == "stop" and complete:
            self.state.stop_order_id = None
            self.stop_order = None
        elif role == "exit" and complete:
            self.state.exit_order_id = None
            self.exit_order = None
        self._save_state()

    def _replace_stop(self) -> None:
        self._clear_stop()
        if self.state.position_quantity == 0 or self.state.stop_price is None:
            return
        side = Order.OrderSide.SELL if self.state.position_quantity > 0 else Order.OrderSide.BUY
        order = self.create_order(
            self.asset,
            abs(self.state.position_quantity),
            side,
            stop_price=float(self.state.stop_price),
            time_in_force="day",
            custom_params={"client_order_id": self._client_order_id("stop")},
        )
        submitted = self.submit_order(order)
        if submitted.status == Order.OrderStatus.ERROR:
            self._flatten("protective stop rejected", disable=True)
            return
        self.stop_order = submitted
        self.state.stop_order_id = str(submitted.identifier)
        self._save_state()

    def _flatten(self, reason: str, *, disable: bool) -> None:
        if disable:
            self.state.disabled = True
        if self.state.position_quantity == 0:
            self._clear_stop()
            self._save_state()
            return
        if self.exit_order is not None:
            return
        self.log_message(f"Flattening {self.asset.symbol}: {reason}", color="red")
        self._clear_stop()
        if not self.broker.IS_BACKTESTING_BROKER:
            cleared = self.broker.wait_orders_clear(self.name)
            if not cleared:
                raise RuntimeError("protective stop did not clear before flattening")
        side = Order.OrderSide.SELL if self.state.position_quantity > 0 else Order.OrderSide.BUY
        order = self.create_order(
            self.asset,
            abs(self.state.position_quantity),
            side,
            time_in_force="day",
            custom_params={"client_order_id": self._client_order_id("exit")},
        )
        submitted = self.submit_order(order)
        if submitted.status == Order.OrderStatus.ERROR:
            raise RuntimeError(f"could not flatten {self.asset.symbol}: {reason}")
        self.exit_order = submitted
        self.state.exit_order_id = str(submitted.identifier)
        self._save_state()

    def _clear_stop(self) -> None:
        order = self.stop_order
        self.stop_order = None
        self.state.stop_order_id = None
        if order is not None and order.is_active():
            self.cancel_order(order)

    def _load_orders(self) -> None:
        if self.state.entry_order_id:
            self.entry_order = self._load_order(self.state.entry_order_id)
        if self.state.stop_order_id:
            self.stop_order = self._load_order(self.state.stop_order_id)
        if self.state.exit_order_id:
            self.exit_order = self._load_order(self.state.exit_order_id)

    def _load_order(self, identifier: str) -> Order | None:
        order = self.broker.get_tracked_order(identifier)
        if order is not None:
            return order
        if self.broker.IS_BACKTESTING_BROKER:
            return None
        return self.broker._pull_order(identifier, self.name)

    def _order_role(self, order: Order) -> str | None:
        identifier = str(order.identifier)
        if order is self.entry_order or identifier == self.state.entry_order_id:
            return "entry"
        if order is self.stop_order or identifier == self.state.stop_order_id:
            return "stop"
        if order is self.exit_order or identifier == self.state.exit_order_id:
            return "exit"
        return None

    def _client_order_id(self, role: str) -> str:
        trading_date = self.state.trading_date
        if trading_date is None:
            raise RuntimeError("trading date is not initialized")
        return f"money-tree-orb-{trading_date:%Y%m%d}-{role}-{uuid4().hex[:8]}"

    def _save_state(self) -> None:
        self.state_store.save(self.state)

    @staticmethod
    def _market_datetime(moment: datetime) -> datetime:
        if moment.tzinfo is None:
            return moment.replace(tzinfo=MARKET_TIMEZONE)
        return moment.astimezone(MARKET_TIMEZONE)
