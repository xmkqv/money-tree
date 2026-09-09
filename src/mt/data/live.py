from dataclasses import dataclass
from typing import Any, Protocol, cast

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus, QueryOrderStatus
from alpaca.trading.models import Order, Position
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest

from mt.config.bot import settings


@dataclass(frozen=True, slots=True)
class Listing:
    symbols: frozenset[str]
    shorts: frozenset[str]


class Live(Protocol):
    def cancel_orders(self) -> set[str]: ...

    def listing(self) -> Listing: ...

    def positions(self) -> list[Position]: ...


class BrokerLive:
    def __init__(self) -> None:
        self._api = TradingClient(
            settings.broker.api_key.get_secret_value(),
            settings.broker.api_secret.get_secret_value(),
            paper=settings.broker.mode == "paper",
        )

    def cancel_orders(self) -> set[str]:
        orders = cast(
            list[Order],
            self._api.get_orders(
                filter=GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    limit=settings.portfolio.orders_per_request,
                )
            ),
        )
        closing: set[str] = set()
        for order in orders:
            if str(order.client_order_id).startswith("mt-liquidate-"):
                closing.add(str(order.symbol))
            else:
                self._api.cancel_order_by_id(str(order.id))
        if len(orders) >= settings.portfolio.orders_per_request:
            raise RuntimeError("open orders reach the request limit")
        return closing

    def listing(self) -> Listing:
        request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        assets = [
            asset
            for asset in cast(list[Any], self._api.get_all_assets(request))
            if bool(asset.tradable) and bool(asset.fractionable)
        ]
        return Listing(
            frozenset(str(asset.symbol) for asset in assets),
            frozenset(str(asset.symbol) for asset in assets if bool(asset.shortable)),
        )

    def positions(self) -> list[Position]:
        return cast(list[Position], self._api.get_all_positions())


class EngineLive:
    def __init__(self, symbols: list[str]) -> None:
        self._listing = frozenset(symbols)

    def cancel_orders(self) -> set[str]:
        return set()

    def listing(self) -> Listing:
        return Listing(self._listing, self._listing)

    def positions(self) -> list[Position]:
        return []
