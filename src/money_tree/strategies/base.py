from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar
from uuid import uuid4

from lumibot.entities import Asset, Order, Position
from lumibot.strategies import Strategy

from money_tree.model import Direction, OrderRole, StrategyName, TradingState
from money_tree.runtime import RuntimeLumibot
from money_tree.state import StateStore


@dataclass(frozen=True, slots=True)
class FillEvent:
    position: Position
    order: Order
    price: float
    quantity: float
    complete: bool


class TradingStrategy(Strategy):
    strategy_name: ClassVar[StrategyName]
    protective_stop_time_in_force: ClassVar[str]
    instrument: Asset
    runtime: RuntimeLumibot
    state_store: StateStore
    state: TradingState
    owned_orders: dict[OrderRole, Order]

    def _initialize_trading_state(self) -> None:
        self.runtime = RuntimeLumibot(self)
        parameters = self.runtime.parameters
        self.instrument = Asset(parameters.instrument)
        self.state_store = StateStore(
            parameters.state_path,
            strategy=self.strategy_name,
            instrument=parameters.instrument,
        )
        self.state = self.state_store.load()
        self.owned_orders = {}
        self._load_orders()

    def _start_session(self, session_date: date, *, keep_position: bool) -> None:
        self.state.start_session(session_date, keep_position=keep_position)
        self._save_state()

    def on_partially_filled_order(
        self,
        position: Position,
        order: Order,
        price: float,
        quantity: float,
        multiplier: float,
    ) -> None:
        self._handle_fill(FillEvent(position, order, price, quantity, complete=False))

    def on_filled_order(
        self,
        position: Position,
        order: Order,
        price: float,
        quantity: float,
        multiplier: float,
    ) -> None:
        self._handle_fill(FillEvent(position, order, price, quantity, complete=True))

    def on_canceled_order(self, order: Order) -> None:
        role = self._find_order_role(order)
        if role is None:
            return
        self._set_order(role, None)
        if (
            role is OrderRole.PROTECTIVE_STOP
            and self.state.position.direction is not Direction.FLAT
        ):
            self._flatten("protective stop canceled", disable=True)
            return
        if role is OrderRole.ENTRY:
            self._on_entry_order_failure(canceled=True)
        self._save_state()

    def on_error_order(self, order: Order, error: Exception | None = None) -> None:
        role = self._find_order_role(order)
        if role is None:
            return
        self._set_order(role, None)
        if role is OrderRole.PROTECTIVE_STOP:
            self._flatten(f"protective stop rejected: {error}", disable=True)
        elif role is OrderRole.FLATTEN:
            self._save_state()
            raise RuntimeError(f"flatten order rejected: {error}")
        else:
            self._on_entry_order_failure(canceled=False)
            self._save_state()

    def on_abrupt_closing(self) -> None:
        self._flatten("abrupt closing", disable=True)

    def _handle_fill(self, event: FillEvent) -> None:
        role = self._record_fill(event)
        if role is None:
            return
        if role is OrderRole.ENTRY:
            self.state.entered = True
            self._record_entry_fill(event.position, event.price)
        elif event.complete and self.state.position.direction is Direction.FLAT:
            self.state.clear_strategy_position()
        self._save_state()

    def _record_entry_fill(self, position: Position, price: float) -> None:
        raise NotImplementedError

    def _on_entry_order_failure(self, *, canceled: bool) -> None:
        return

    def _record_fill(self, event: FillEvent) -> OrderRole | None:
        role = self._find_order_role(event.order)
        if role is None:
            return None
        self.state.position.record_fill(
            self.runtime.order_side(event.order),
            Decimal(str(event.price)),
            Decimal(str(event.quantity)),
        )
        if event.complete:
            self._set_order(role, None)
        return role

    def _get_order(self, role: OrderRole) -> Order | None:
        return self.owned_orders.get(role)

    def _set_order(self, role: OrderRole, order: Order | None) -> None:
        if order is None:
            self.owned_orders.pop(role, None)
        else:
            self.owned_orders[role] = order
        identifier = None if order is None else str(order.identifier)
        self.state.orders.set_identifier(role, identifier)

    def _cancel_order(self, role: OrderRole) -> None:
        order = self._get_order(role)
        if order is not None and order.is_active():
            self.cancel_order(order)
        self._set_order(role, None)
        self._save_state()

    def _load_orders(self) -> None:
        for role in OrderRole:
            identifier = self.state.orders.get_identifier(role)
            if identifier is None:
                continue
            order = self.runtime.find_order(identifier)
            if order is None:
                if not self.runtime.is_backtesting:
                    raise RuntimeError(f"owned {role.value} order {identifier} could not be loaded")
                continue
            self._set_order(role, order)

    def _find_order_role(self, order: Order) -> OrderRole | None:
        identifier = str(order.identifier)
        for role in OrderRole:
            owned_order = self._get_order(role)
            if owned_order is order or identifier == self.state.orders.get_identifier(role):
                return role
        return None

    def _create_order_identifier(self, role: OrderRole) -> str:
        session_date = self.state.session_date
        if session_date is None:
            raise RuntimeError("trading session is not initialized")
        return (
            f"money-tree-{self.strategy_name.value}-{session_date:%Y%m%d}-"
            f"{role.value}-{uuid4().hex[:8]}"
        )

    def _closing_order_side(self) -> Order.OrderSide:
        match self.state.position.direction:
            case Direction.LONG:
                return Order.OrderSide.SELL
            case Direction.SHORT:
                return Order.OrderSide.BUY
            case Direction.FLAT:
                raise RuntimeError("a flat position has no closing order side")

    def _replace_protective_stop(self, protective_stop_price: Decimal) -> None:
        self._cancel_order(OrderRole.PROTECTIVE_STOP)
        if self.state.position.direction is Direction.FLAT:
            self._save_state()
            return
        if not self.runtime.is_backtesting and not self.runtime.wait_orders_clear():
            raise RuntimeError("protective stop did not clear before replacement")
        order = self.create_order(
            self.instrument,
            abs(self.state.position.quantity),
            self._closing_order_side(),
            stop_price=float(protective_stop_price),
            time_in_force=self.protective_stop_time_in_force,
            custom_params={
                "client_order_id": self._create_order_identifier(OrderRole.PROTECTIVE_STOP)
            },
        )
        submitted_order = self.submit_order(order)
        if submitted_order.status == Order.OrderStatus.ERROR:
            self._flatten("protective stop rejected", disable=True)
            return
        self._record_active_protective_stop_price(protective_stop_price)
        self._set_order(OrderRole.PROTECTIVE_STOP, submitted_order)
        self._save_state()

    def _record_active_protective_stop_price(self, protective_stop_price: Decimal) -> None:
        return

    def _flatten(self, reason: str, *, disable: bool) -> None:
        if disable:
            self.state.disabled = True
        self._cancel_order(OrderRole.ENTRY)
        if self.state.position.direction is Direction.FLAT:
            self._cancel_order(OrderRole.PROTECTIVE_STOP)
            self.state.clear_strategy_position()
            self._save_state()
            return
        if self._get_order(OrderRole.FLATTEN) is not None:
            self._save_state()
            return
        self.log_message(f"Flattening {self.instrument.symbol}: {reason}", color="red")
        self._cancel_order(OrderRole.PROTECTIVE_STOP)
        if not self.runtime.is_backtesting and not self.runtime.wait_orders_clear():
            raise RuntimeError("protective stop did not clear before flattening")
        order = self.create_order(
            self.instrument,
            abs(self.state.position.quantity),
            self._closing_order_side(),
            time_in_force="day",
            custom_params={"client_order_id": self._create_order_identifier(OrderRole.FLATTEN)},
        )
        submitted_order = self.submit_order(order)
        if submitted_order.status == Order.OrderStatus.ERROR:
            raise RuntimeError(f"could not flatten {self.instrument.symbol}: {reason}")
        self._set_order(OrderRole.FLATTEN, submitted_order)
        self._save_state()

    def _save_state(self) -> None:
        self.state_store.save(self.state)


class TradingStrategyLong(TradingStrategy):
    def _restore_long_position(self) -> Position | None:
        position = self.get_position(self.instrument)
        if position is not None and float(position.quantity) < 0:
            raise RuntimeError(f"{self.strategy_name.value} supports long positions only")
        if self.state.position.direction is Direction.FLAT:
            return position
        if position is None:
            raise RuntimeError(f"broker position is missing during {self.strategy_name.value} trading")
        if (
            self._get_order(OrderRole.PROTECTIVE_STOP) is None
            and self._get_order(OrderRole.FLATTEN) is None
        ):
            protective_stop_price = self._restored_protective_stop_price()
            if protective_stop_price is None:
                self._flatten("protective stop state is missing", disable=True)
                return position
            self._replace_protective_stop(protective_stop_price)
        return position

    def _restored_protective_stop_price(self) -> Decimal | None:
        raise NotImplementedError

    def _can_submit_entry(self) -> bool:
        if any(self._get_order(role) is not None for role in OrderRole):
            return False
        if self.state.disabled or self.state.entered:
            return False
        self.state.clear_strategy_position()
        return True

    def _submit_long_entry_order(self, quantity: Decimal) -> Order | None:
        if quantity <= 0:
            return None
        order = self.create_order(
            self.instrument,
            quantity,
            Order.OrderSide.BUY,
            time_in_force="day",
            custom_params={"client_order_id": self._create_order_identifier(OrderRole.ENTRY)},
        )
        submitted_order = self.submit_order(order)
        if submitted_order.status == Order.OrderStatus.ERROR:
            self.state.clear_strategy_position()
            self._save_state()
            return None
        self._set_order(OrderRole.ENTRY, submitted_order)
        self._save_state()
        return submitted_order

    def _on_entry_order_failure(self, *, canceled: bool) -> None:
        if not canceled or self.state.position.direction is Direction.FLAT:
            self.state.clear_strategy_position()
