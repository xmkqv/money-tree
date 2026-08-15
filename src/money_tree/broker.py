from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Asset, Order, Position, TradeAccount
from alpaca.trading.requests import GetOrdersRequest

from money_tree.model import Direction, OrderRole, TradingMode, TradingState

API_KEY_VARIABLE = "ALPACA_API_KEY"
API_SECRET_VARIABLE = "ALPACA_API_SECRET"


@dataclass(frozen=True, slots=True)
class BrokerConfiguration:
    api_key: str
    api_secret: str
    trading_mode: TradingMode

    @property
    def lumibot_values(self) -> dict[str, str | bool]:
        return {
            "API_KEY": self.api_key,
            "API_SECRET": self.api_secret,
            "PAPER": self.trading_mode is TradingMode.PAPER,
        }


@dataclass(frozen=True, slots=True)
class InstrumentRequirements:
    fractional: bool
    short: bool


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    position_quantity: Decimal | None
    position_average_entry_price: Decimal | None
    open_order_identifiers: frozenset[str]


def load_broker_configuration(trading_mode: TradingMode) -> BrokerConfiguration:
    api_key = os.environ.get(API_KEY_VARIABLE)
    api_secret = os.environ.get(API_SECRET_VARIABLE)
    if not api_key or not api_secret:
        raise RuntimeError(f"missing {API_KEY_VARIABLE} or {API_SECRET_VARIABLE}")
    return BrokerConfiguration(
        api_key=api_key,
        api_secret=api_secret,
        trading_mode=trading_mode,
    )


def connect_broker(configuration: BrokerConfiguration) -> TradingClient:
    return TradingClient(
        configuration.api_key,
        configuration.api_secret,
        paper=configuration.trading_mode is TradingMode.PAPER,
    )


def _require_type[Value](value: object, expected: type[Value], name: str) -> Value:
    if not isinstance(value, expected):
        raise TypeError(f"Alpaca {name} response has an invalid type")
    return value


def _require_list[Value](values: object, expected: type[Value], name: str) -> list[Value]:
    if not isinstance(values, list) or not all(isinstance(value, expected) for value in values):
        raise TypeError(f"Alpaca {name} response has an invalid type")
    return values


def require_active_account(client: TradingClient) -> None:
    account = _require_type(client.get_account(), TradeAccount, "account")
    if str(account.status).lower().split(".")[-1] != "active":
        raise RuntimeError(f"Alpaca account is not active: {account.status}")
    if account.trading_blocked:
        raise RuntimeError("Alpaca account is blocked from trading")


def require_instrument_capabilities(
    client: TradingClient,
    instrument: str,
    requirements: InstrumentRequirements,
) -> None:
    vendor_instrument = _require_type(client.get_asset(instrument), Asset, "asset")
    if not vendor_instrument.tradable:
        raise RuntimeError(f"{instrument} is not tradable")
    if requirements.fractional and not vendor_instrument.fractionable:
        raise RuntimeError(f"{instrument} does not support fractional orders")
    if requirements.short and not vendor_instrument.shortable:
        raise RuntimeError(f"{instrument} is not shortable")
    if requirements.short and not vendor_instrument.easy_to_borrow:
        raise RuntimeError(f"{instrument} is not easy to borrow")


def get_account_snapshot(client: TradingClient, instrument: str) -> AccountSnapshot:
    positions = [
        position
        for position in _require_list(client.get_all_positions(), Position, "positions")
        if position.symbol == instrument
    ]
    orders = _require_list(
        client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[instrument])
        ),
        Order,
        "orders",
    )
    position = positions[0] if positions else None
    return AccountSnapshot(
        position_quantity=Decimal(position.qty) if position is not None else None,
        position_average_entry_price=(
            Decimal(position.avg_entry_price) if position is not None else None
        ),
        open_order_identifiers=frozenset(str(order.id) for order in orders),
    )


def reconcile_account(snapshot: AccountSnapshot, state: TradingState) -> None:
    unknown_identifiers = snapshot.open_order_identifiers - state.orders.identifiers
    if unknown_identifiers:
        raise RuntimeError("the selected instrument has a broker order that is not an owned order")
    for role in OrderRole:
        identifier = state.orders.get_identifier(role)
        if identifier is not None and identifier not in snapshot.open_order_identifiers:
            state.orders.set_identifier(role, None)
    if snapshot.position_quantity is None:
        if state.position.direction is not Direction.FLAT:
            raise RuntimeError("broker position is missing from the selected trading state")
        if any(
            state.orders.get_identifier(role) is not None
            for role in (OrderRole.PROTECTIVE_STOP, OrderRole.FLATTEN)
        ):
            raise RuntimeError("a position order exists without a broker position")
        return
    if (
        snapshot.position_quantity != state.position.quantity
        or snapshot.position_average_entry_price != state.position.average_entry_price
    ):
        raise RuntimeError(
            "the selected instrument has a broker position that is not an owned position"
        )
