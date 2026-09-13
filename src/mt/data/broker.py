from typing import Protocol, cast
from uuid import uuid4

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetStatus, QueryOrderStatus
from alpaca.trading.models import Asset as BrokerAsset
from alpaca.trading.models import Order
from alpaca.trading.models import Position as BrokerPosition
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest

from mt.rules.bot import settings as bot_settings
from mt.rules.shared import settings

from .asset import Asset


class Broker(Protocol):
    def cancel_orders(self) -> set[Asset]: ...

    def assets(self) -> dict[Asset, BrokerAsset]: ...

    def positions(self) -> list[BrokerPosition]: ...


class BrokerAlpaca:
    def __init__(self) -> None:
        self._api = TradingClient(*settings.broker.key_pair, paper=settings.broker.is_paper)

    def cancel_orders(self) -> set[Asset]:
        orders = cast(
            list[Order],
            self._api.get_orders(
                filter=GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    limit=bot_settings.portfolio.orders_per_request,
                )
            ),
        )
        closing: set[Asset] = set()
        for order in orders:
            if str(order.client_order_id).startswith("mt-liquidate-"):
                closing.add(Asset.from_symbol(str(order.symbol)))
            else:
                self._api.cancel_order_by_id(str(order.id))
        if len(orders) >= bot_settings.portfolio.orders_per_request:
            raise RuntimeError("open orders reach the request limit")
        return closing

    def assets(self) -> dict[Asset, BrokerAsset]:
        request = GetAssetsRequest(status=AssetStatus.ACTIVE)
        return {
            Asset.from_symbol(asset.symbol): asset
            for asset in cast(list[BrokerAsset], self._api.get_all_assets(request))
            if asset.tradable and asset.fractionable
        }

    def positions(self) -> list[BrokerPosition]:
        return cast(list[BrokerPosition], self._api.get_all_positions())


class BrokerEngine:
    def __init__(self, assets: list[Asset]) -> None:
        self._assets = {
            asset: BrokerAsset.model_validate(
                {**bot_settings.backtest.asset_defaults, "id": uuid4(), "symbol": str(asset)}
            )
            for asset in assets
        }

    def cancel_orders(self) -> set[Asset]:
        return set()

    def assets(self) -> dict[Asset, BrokerAsset]:
        return self._assets

    def positions(self) -> list[BrokerPosition]:
        return []
