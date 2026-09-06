from typing import Any, Protocol, cast

from alpaca.common.enums import Sort
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Order, Position
from alpaca.trading.requests import GetOrdersRequest

from mt.config.settings import settings


class Live(Protocol):
    def is_shortable(self, symbol: str) -> bool: ...

    def listing(self) -> frozenset[str]: ...

    def positions(self) -> list[Position]: ...

    def tagged_orders(self, symbols: list[str]) -> list[Order]: ...


class BrokerLive:
    def __init__(self) -> None:
        self._api = TradingClient(
            settings.broker.api_key.get_secret_value(),
            settings.broker.api_secret.get_secret_value(),
            paper=settings.broker.mode == "paper",
        )

    def is_shortable(self, symbol: str) -> bool:
        return bool(cast(Any, self._api.get_asset(symbol)).shortable)

    def listing(self) -> frozenset[str]:
        return frozenset(
            str(asset.symbol)
            for asset in cast(list[Any], self._api.get_all_assets())
            if bool(asset.tradable) and bool(asset.fractionable)
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

    def is_shortable(self, symbol: str) -> bool:
        return symbol in self._listing

    def listing(self) -> frozenset[str]:
        return self._listing

    def positions(self) -> list[Position]:
        return []

    def tagged_orders(self, symbols: list[str]) -> list[Order]:
        return []
