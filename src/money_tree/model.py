from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import assert_never


class StrategyName(StrEnum):
    OPENING_RANGE = "opening-range"
    MOMENTUM_LONG = "momentum-long"
    TFB_50 = "tfb-50"


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class Direction(StrEnum):
    LONG = "long"
    FLAT = "flat"
    SHORT = "short"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderRole(StrEnum):
    ENTRY = "entry"
    PROTECTIVE_STOP = "protective-stop"
    FLATTEN = "flatten"


@dataclass(slots=True)
class PositionState:
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    realized_profit_and_loss: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        values = (
            self.quantity,
            self.average_entry_price,
            self.realized_profit_and_loss,
        )
        if not all(value.is_finite() for value in values):
            raise ValueError("position values must be finite")
        if self.average_entry_price < 0:
            raise ValueError("average entry price must not be negative")
        if self.quantity == 0 and self.average_entry_price != 0:
            raise ValueError("a flat position must have a zero average entry price")
        if self.quantity != 0 and self.average_entry_price <= 0:
            raise ValueError("an open position must have a positive average entry price")

    @property
    def direction(self) -> Direction:
        if self.quantity > 0:
            return Direction.LONG
        if self.quantity < 0:
            return Direction.SHORT
        return Direction.FLAT

    def record_fill(self, order_side: OrderSide, price: Decimal, quantity: Decimal) -> None:
        if not price.is_finite() or not quantity.is_finite() or price <= 0 or quantity <= 0:
            raise ValueError("fill price and quantity must be positive")
        signed_quantity = quantity if order_side is OrderSide.BUY else -quantity
        previous_quantity = self.quantity
        if previous_quantity == 0 or previous_quantity * signed_quantity > 0:
            total_quantity = abs(previous_quantity) + quantity
            self.average_entry_price = (
                self.average_entry_price * abs(previous_quantity) + price * quantity
            ) / total_quantity
            self.quantity += signed_quantity
            return
        closed_quantity = min(abs(previous_quantity), quantity)
        direction = Decimal("1") if previous_quantity > 0 else Decimal("-1")
        self.realized_profit_and_loss += (
            (price - self.average_entry_price) * closed_quantity * direction
        )
        self.quantity += signed_quantity
        if self.quantity == 0:
            self.average_entry_price = Decimal("0")
        elif previous_quantity * self.quantity < 0:
            self.average_entry_price = price

    def calculate_profit_and_loss(self, mark_price: Decimal) -> Decimal:
        if not mark_price.is_finite() or mark_price <= 0:
            raise ValueError("mark price must be positive")
        unrealized = (mark_price - self.average_entry_price) * self.quantity
        return self.realized_profit_and_loss + unrealized

    def set_flat(self) -> None:
        self.quantity = Decimal("0")
        self.average_entry_price = Decimal("0")


@dataclass(slots=True)
class OwnedOrderState:
    identifiers: dict[OrderRole, str] = field(default_factory=dict)

    @property
    def ids(self) -> set[str]:
        return set(self.identifiers.values())

    def get_id(self, role: OrderRole) -> str | None:
        return self.identifiers.get(role)

    def set_id(self, role: OrderRole, identifier: str | None) -> None:
        if identifier is None:
            self.identifiers.pop(role, None)
        else:
            self.identifiers[role] = identifier


@dataclass(slots=True)
class OpeningRangeState:
    protective_stop_price: Decimal | None = None


@dataclass(slots=True)
class MomentumLongState:
    entry_price: Decimal | None = None
    initial_protective_stop_price: Decimal | None = None
    active_protective_stop_price: Decimal | None = None
    trail_activation_price: Decimal | None = None
    highest_price: Decimal | None = None


@dataclass(slots=True)
class Tfb50State:
    entered_on: date | None = None
    initial_protective_stop_price: Decimal | None = None
    active_protective_stop_price: Decimal | None = None


type StrategyState = OpeningRangeState | MomentumLongState | Tfb50State


def create_strategy_state(strategy: StrategyName) -> StrategyState:
    match strategy:
        case StrategyName.OPENING_RANGE:
            return OpeningRangeState()
        case StrategyName.MOMENTUM_LONG:
            return MomentumLongState()
        case StrategyName.TFB_50:
            return Tfb50State()
    assert_never(strategy)


@dataclass(slots=True)
class TradingState:
    strategy: StrategyName
    instrument: str
    session_date: date | None = None
    entered: bool = False
    disabled: bool = False
    position: PositionState = field(default_factory=PositionState)
    orders: OwnedOrderState = field(default_factory=OwnedOrderState)
    strategy_state: StrategyState | None = None

    def __post_init__(self) -> None:
        if not self.instrument:
            raise ValueError("instrument must not be blank")
        if self.strategy_state is None:
            self.strategy_state = create_strategy_state(self.strategy)
        if self.strategy is StrategyName.OPENING_RANGE and not isinstance(
            self.strategy_state, OpeningRangeState
        ):
            raise ValueError("opening-range trading state requires opening-range state")
        if self.strategy is StrategyName.MOMENTUM_LONG and not isinstance(
            self.strategy_state, MomentumLongState
        ):
            raise ValueError("momentum-long trading state requires momentum-long state")
        if self.strategy is StrategyName.TFB_50 and not isinstance(self.strategy_state, Tfb50State):
            raise ValueError("tfb-50 trading state requires tfb-50 state")

    def validate(self) -> None:
        self.__post_init__()
        self.position.validate()
        if len(self.orders.ids) != len(self.orders.identifiers):
            raise ValueError("owned order identifiers must be distinct")
        if (
            self.orders.get_id(OrderRole.PROTECTIVE_STOP) is not None
            and self.orders.get_id(OrderRole.FLATTEN) is not None
        ):
            raise ValueError("protective stop and flatten orders cannot both be active")
        strategy_state = self.strategy_state
        if isinstance(strategy_state, OpeningRangeState):
            if (
                self.position.direction is not Direction.FLAT
                and strategy_state.protective_stop_price is None
            ):
                raise ValueError("an opening-range position requires a protective stop price")
        elif isinstance(strategy_state, MomentumLongState):
            if self.position.direction is Direction.SHORT:
                raise ValueError("momentum-long position must not be short")
            if self.position.direction is Direction.LONG and any(
                getattr(strategy_state, item.name) is None for item in fields(strategy_state)
            ):
                raise ValueError("a momentum-long position requires complete protection state")
        elif isinstance(strategy_state, Tfb50State):
            if self.position.direction is Direction.SHORT:
                raise ValueError("tfb-50 position must not be short")
            if self.position.direction is Direction.LONG and any(
                getattr(strategy_state, item.name) is None for item in fields(strategy_state)
            ):
                raise ValueError("a tfb-50 position requires complete protection state")
            if strategy_state.entered_on is not None and not isinstance(
                strategy_state.entered_on, date
            ):
                raise ValueError("tfb-50 entry date must use a date value")
        else:
            raise RuntimeError("strategy state is not initialized")
        strategy_prices = tuple(
            getattr(strategy_state, item.name)
            for item in fields(strategy_state)
            if item.name.endswith("_price")
        )
        if any(
            value is not None
            and (not isinstance(value, Decimal) or not value.is_finite() or value <= 0)
            for value in strategy_prices
        ):
            raise ValueError("strategy prices must be positive and finite")

    def start_session(self, session_date: date, *, keep_position: bool) -> None:
        if self.session_date == session_date:
            return
        if not keep_position and self.position.direction is not Direction.FLAT:
            raise RuntimeError("cannot start a new session while a position is open")
        self.session_date = session_date
        self.entered = False
        self.disabled = False
        self.position.realized_profit_and_loss = Decimal("0")

    def clear_strategy_position(self) -> None:
        strategy_state = self.strategy_state
        if strategy_state is None:
            raise RuntimeError("strategy state is not initialized")
        for item in fields(strategy_state):
            setattr(strategy_state, item.name, None)
