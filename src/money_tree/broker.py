from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Asset, Order, Position, TradeAccount
from alpaca.trading.requests import GetOrdersRequest

from money_tree.risk import RiskState


@dataclass(frozen=True, slots=True)
class BrokerConfig:
    api_key: str
    api_secret: str
    paper: bool

    def lumibot(self) -> dict[str, str | bool]:
        return {
            "API_KEY": self.api_key,
            "API_SECRET": self.api_secret,
            "PAPER": self.paper,
        }


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    position_quantity: Decimal | None
    open_order_ids: frozenset[str]


def load_broker_config(*, paper: bool) -> BrokerConfig:
    prefix = "ALPACA_" if paper else "ALPACA_LIVE_"
    return BrokerConfig(
        api_key=os.environ[f"{prefix}API_KEY"],
        api_secret=os.environ[f"{prefix}API_SECRET"],
        paper=paper,
    )


def connect_trading_client(config: BrokerConfig) -> TradingClient:
    return TradingClient(config.api_key, config.api_secret, paper=config.paper)


def verify_account(client: TradingClient) -> None:
    account = cast(TradeAccount, client.get_account())
    if str(account.status).lower().split(".")[-1] != "active":
        raise RuntimeError(f"Alpaca account is not active: {account.status}")
    if account.trading_blocked:
        raise RuntimeError("Alpaca account is blocked from trading")


def verify_asset(client: TradingClient, symbol: str) -> None:
    asset = cast(Asset, client.get_asset(symbol))
    if not asset.tradable:
        raise RuntimeError(f"{symbol} is not tradable")
    if not asset.fractionable:
        raise RuntimeError(f"{symbol} does not support fractional long orders")
    if not asset.shortable:
        raise RuntimeError(f"{symbol} is not shortable")
    if not asset.easy_to_borrow:
        raise RuntimeError(f"{symbol} is not easy to borrow")


def get_account_snapshot(client: TradingClient, symbol: str) -> AccountSnapshot:
    positions = [
        position
        for position in cast(list[Position], client.get_all_positions())
        if position.symbol == symbol
    ]
    orders = cast(
        list[Order],
        client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])),
    )
    return AccountSnapshot(
        position_quantity=Decimal(positions[0].qty) if positions else None,
        open_order_ids=frozenset(str(order.id) for order in orders),
    )


def verify_account_snapshot(snapshot: AccountSnapshot, state: RiskState) -> None:
    unknown_orders = snapshot.open_order_ids - state.order_ids()
    if unknown_orders:
        raise RuntimeError("the configured symbol has open orders that money-tree does not own")
    if snapshot.position_quantity is None:
        if state.position_quantity != 0:
            state.position_quantity = Decimal("0")
            state.average_entry_price = Decimal("0")
            state.stop_price = None
            state.stop_order_id = None
        return
    if snapshot.position_quantity != state.position_quantity:
        raise RuntimeError("the configured symbol has a position that money-tree does not own")
