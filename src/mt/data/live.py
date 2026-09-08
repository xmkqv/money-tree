from dataclasses import dataclass
from typing import Any, Protocol, cast

from alpaca.common.enums import Sort
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus, QueryOrderStatus
from alpaca.trading.models import Order, Position
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest

from mt.config.settings import settings


@dataclass(frozen=True, slots=True)
class Listing:
    symbols: frozenset[str]
    shorts: frozenset[str]


class Live(Protocol):
    def listing(self) -> Listing: ...

    def positions(self) -> list[Position]: ...

    def tagged_orders(self, symbols: list[str]) -> list[Order]: ...


class BrokerLive:
    def __init__(self) -> None:
        self._api = TradingClient(
            settings.broker.api_key.get_secret_value(),
            settings.broker.api_secret.get_secret_value(),
            paper=settings.broker.mode == "paper",
        )

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

    def tagged_orders(self, symbols: list[str]) -> list[Order]:
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            symbols=symbols,
            limit=settings.portfolio.orders_per_request,
            direction=Sort.DESC,
        )
        return cast(list[Order], self._api.get_orders(filter=request))


class EngineLive:
    def __init__(self, symbols: list[str]) -> None:
        self._listing = frozenset(symbols)

    def listing(self) -> Listing:
        return Listing(self._listing, self._listing)

    def positions(self) -> list[Position]:
        return []

    def tagged_orders(self, symbols: list[str]) -> list[Order]:
        return []
