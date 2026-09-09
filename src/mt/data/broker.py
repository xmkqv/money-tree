from typing import Protocol, cast
from uuid import uuid4

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus, QueryOrderStatus
from alpaca.trading.models import Asset, Order, Position
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest

from mt.config.bot import settings


class Broker(Protocol):
    def cancel_orders(self) -> set[str]: ...

    def assets(self) -> dict[str, Asset]: ...

    def positions(self) -> list[Position]: ...


class BrokerAlpaca:
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

    def assets(self) -> dict[str, Asset]:
        request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        return {
            asset.symbol: asset
            for asset in cast(list[Asset], self._api.get_all_assets(request))
            if asset.tradable and asset.fractionable
        }

    def positions(self) -> list[Position]:
        return cast(list[Position], self._api.get_all_positions())


class BrokerEngine:
    def __init__(self, symbols: list[str]) -> None:
        self._assets = {
            symbol: Asset.model_validate(
                {**settings.backtest.asset_defaults, "id": uuid4(), "symbol": symbol}
            )
            for symbol in symbols
        }

    def cancel_orders(self) -> set[str]:
        return set()

    def assets(self) -> dict[str, Asset]:
        return self._assets

    def positions(self) -> list[Position]:
        return []
