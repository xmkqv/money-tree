from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Asset, Order, Position, TradeAccount
from alpaca.trading.requests import GetOrdersRequest

from money_tree.model import Direction, OrderRole, TradingMode, TradingState


@dataclass(frozen=True, slots=True)
class BrokerConfig:
    api_key: str
    api_secret: str
    mode: TradingMode

    def to_lumibot(self) -> dict[str, str | bool]:
        return {
            "API_KEY": self.api_key,
            "API_SECRET": self.api_secret,
            "PAPER": self.mode is TradingMode.PAPER,
        }


@dataclass(frozen=True, slots=True)
class InstrumentRequirements:
    fractional: bool
    short: bool


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    position_quantity: Decimal | None
    position_average_entry_price: Decimal | None
    open_order_ids: frozenset[str]


def load_broker_config(mode: TradingMode) -> BrokerConfig:
    prefix = "ALPACA_" if mode is TradingMode.PAPER else "ALPACA_LIVE_"
    key_name = f"{prefix}API_KEY"
    secret_name = f"{prefix}API_SECRET"
    api_key = os.environ.get(key_name)
    api_secret = os.environ.get(secret_name)
    if not api_key or not api_secret:
        raise RuntimeError(f"missing {key_name} or {secret_name}")
    return BrokerConfig(api_key=api_key, api_secret=api_secret, mode=mode)


def connect_broker(config: BrokerConfig) -> TradingClient:
    return TradingClient(
        config.api_key,
        config.api_secret,
        paper=config.mode is TradingMode.PAPER,
    )


def verify_account(client: TradingClient) -> None:
    account = cast(TradeAccount, client.get_account())
    if str(account.status).lower().split(".")[-1] != "active":
        raise RuntimeError(f"alpaca account is not active: {account.status}")
    if account.trading_blocked:
        raise RuntimeError("alpaca account is blocked from trading")


def verify_instrument(
    client: TradingClient,
    instrument: str,
    requirements: InstrumentRequirements,
) -> None:
    vendor_instrument = cast(Asset, client.get_asset(instrument))
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
        for position in cast(list[Position], client.get_all_positions())
        if position.symbol == instrument
    ]
    orders = cast(
        list[Order],
        client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[instrument])
        ),
    )
    position = positions[0] if positions else None
    return AccountSnapshot(
        position_quantity=Decimal(position.qty) if position is not None else None,
        position_average_entry_price=(
            Decimal(position.avg_entry_price) if position is not None else None
        ),
        open_order_ids=frozenset(str(order.id) for order in orders),
    )


def reconcile_account(snapshot: AccountSnapshot, state: TradingState) -> None:
    unknown_order_ids = snapshot.open_order_ids - state.orders.ids
    if unknown_order_ids:
        raise RuntimeError("the selected instrument has a broker order that is not an owned order")
    for role in OrderRole:
        identifier = state.orders.get_id(role)
        if identifier is not None and identifier not in snapshot.open_order_ids:
            state.orders.set_id(role, None)
    if snapshot.position_quantity is None:
        if state.position.direction is not Direction.FLAT:
            raise RuntimeError("broker position is missing from the selected trading state")
        if any(
            state.orders.get_id(role) is not None
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
