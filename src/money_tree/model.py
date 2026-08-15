from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class EntryDecision:
    protective_stop_price: float


def _require_positive_prices(*prices: Decimal | None) -> None:
    if any(price is not None and (not price.is_finite() or price <= 0) for price in prices):
        raise ValueError("strategy prices must be positive and finite")


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


@dataclass(slots=True)
class OwnedOrderState:
    identifier_by_role: dict[OrderRole, str] = field(default_factory=dict)

    @property
    def identifiers(self) -> set[str]:
        return set(self.identifier_by_role.values())

    def get_identifier(self, role: OrderRole) -> str | None:
        return self.identifier_by_role.get(role)

    def set_identifier(self, role: OrderRole, identifier: str | None) -> None:
        if identifier is None:
            self.identifier_by_role.pop(role, None)
            return
        self.identifier_by_role[role] = identifier

    def validate(self) -> None:
        if len(self.identifiers) != len(self.identifier_by_role):
            raise ValueError("owned order identifiers must be distinct")
        if (
            self.get_identifier(OrderRole.PROTECTIVE_STOP) is not None
            and self.get_identifier(OrderRole.FLATTEN) is not None
        ):
            raise ValueError("protective stop and flatten orders cannot both be active")


@dataclass(slots=True)
class OpeningRangeState:
    protective_stop_price: Decimal | None = None

    def validate(self, position: PositionState) -> None:
        _require_positive_prices(self.protective_stop_price)
        if position.direction is not Direction.FLAT and self.protective_stop_price is None:
            raise ValueError("an opening-range position requires a protective stop price")

    def clear(self) -> None:
        self.protective_stop_price = None


@dataclass(slots=True)
class MomentumLongState:
    entry_price: Decimal | None = None
    initial_protective_stop_price: Decimal | None = None
    active_protective_stop_price: Decimal | None = None
    trail_activation_price: Decimal | None = None
    highest_price: Decimal | None = None

    def validate(self, position: PositionState) -> None:
        _require_positive_prices(
            self.entry_price,
            self.initial_protective_stop_price,
            self.active_protective_stop_price,
            self.trail_activation_price,
            self.highest_price,
        )
        if position.direction is Direction.SHORT:
            raise ValueError("momentum-long position must not be short")
        if position.direction is Direction.LONG and None in (
            self.entry_price,
            self.initial_protective_stop_price,
            self.active_protective_stop_price,
            self.trail_activation_price,
            self.highest_price,
        ):
            raise ValueError("a momentum-long position requires complete protection state")

    def clear(self) -> None:
        self.entry_price = None
        self.initial_protective_stop_price = None
        self.active_protective_stop_price = None
        self.trail_activation_price = None
        self.highest_price = None


@dataclass(slots=True)
class Tfb50State:
    entered_on: date | None = None
    initial_protective_stop_price: Decimal | None = None
    active_protective_stop_price: Decimal | None = None

    def validate(self, position: PositionState) -> None:
        _require_positive_prices(
            self.initial_protective_stop_price,
            self.active_protective_stop_price,
        )
        if position.direction is Direction.SHORT:
            raise ValueError("tfb-50 position must not be short")
        if position.direction is Direction.LONG and None in (
            self.entered_on,
            self.initial_protective_stop_price,
            self.active_protective_stop_price,
        ):
            raise ValueError("a tfb-50 position requires complete protection state")

    def clear(self) -> None:
        self.entered_on = None
        self.initial_protective_stop_price = None
        self.active_protective_stop_price = None


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


def _require_strategy_state(strategy: StrategyName, state: StrategyState) -> None:
    expected = {
        StrategyName.OPENING_RANGE: OpeningRangeState,
        StrategyName.MOMENTUM_LONG: MomentumLongState,
        StrategyName.TFB_50: Tfb50State,
    }[strategy]
    if not isinstance(state, expected):
        raise ValueError(f"{strategy.value} trading state has an incorrect strategy state")


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
        _require_strategy_state(self.strategy, self.strategy_state)

    def validate(self) -> None:
        self.__post_init__()
        self.position.validate()
        self.orders.validate()
        if self.strategy_state is None:
            raise RuntimeError("strategy state is not initialized")
        self.strategy_state.validate(self.position)

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
        if self.strategy_state is None:
            raise RuntimeError("strategy state is not initialized")
        self.strategy_state.clear()
