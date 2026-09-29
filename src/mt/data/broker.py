from http import HTTPStatus
from typing import Protocol, cast
from uuid import uuid4

from alpaca.common.exceptions import APIError
from alpaca.common.types import RawData
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus, OrderSide, QueryOrderStatus
from alpaca.trading.models import Asset as BrokerAsset
from alpaca.trading.models import Order
from alpaca.trading.requests import GetAssetsRequest, GetOrdersRequest

from mt.rules.bot import settings as bot_settings
from mt.rules.shared import settings
from mt.rules.values import OrderReason
from mt.strategies.registry import find_order_reason

from .asset import Asset


LIQUIDATE_REASON: OrderReason = "limit"


class Broker(Protocol):
    def cancel_orders(self) -> set[Asset]: ...

    def assets(self) -> dict[Asset, BrokerAsset]: ...

    def find_closing_assets(self, positions: dict[Asset, float]) -> set[Asset]: ...


class BrokerAlpaca:
    def __init__(self) -> None:
        self._api = TradingClient(*settings.broker.key_pair, paper=settings.broker.is_paper)

    def cancel_orders(self) -> set[Asset]:
        orders = self._open_orders()
        closing: set[Asset] = set()
        for order in orders:
            if order.symbol is None or find_order_reason(order.client_order_id) != LIQUIDATE_REASON:
                try:
                    self._api.cancel_order_by_id(order.id)
                except APIError as error:
                    status_code = cast(int | None, error.status_code)  # pyright: ignore[reportUnknownMemberType]
                    if status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
                        raise
            else:
                closing.add(Asset.from_symbol(order.symbol))
        return closing

    def assets(self) -> dict[Asset, BrokerAsset]:
        request = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
        return {
            Asset.from_symbol(asset.symbol): asset
            for asset in _listed(self._api.get_all_assets(request))
            if asset.tradable and asset.fractionable
        }

    def find_closing_assets(self, positions: dict[Asset, float]) -> set[Asset]:
        closing: set[Asset] = set()
        for order in self._open_orders():
            if order.symbol is None or order.side is None:
                continue
            asset = Asset.from_symbol(order.symbol)
            quantity = positions.get(asset)
            if quantity is None:
                continue
            closing_side = OrderSide.SELL if quantity > 0 else OrderSide.BUY
            if order.side == closing_side:
                closing.add(asset)
        return closing

    def _open_orders(self) -> list[Order]:
        orders = _listed(
            self._api.get_orders(
                filter=GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    limit=bot_settings.portfolio.orders_per_request,
                )
            )
        )
        if len(orders) >= bot_settings.portfolio.orders_per_request:
            raise RuntimeError("open orders reach the request limit")
        return orders


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

    def find_closing_assets(self, positions: dict[Asset, float]) -> set[Asset]:
        return set()


def _listed[Item](result: list[Item] | RawData) -> list[Item]:
    if not isinstance(result, list):
        raise TypeError("the broker returned raw data instead of models")
    return result
