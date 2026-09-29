import itertools
from datetime import datetime, timedelta

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.models.bars import BarSet
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from pandas import DataFrame, DatetimeIndex

from mt.data.asset import Asset
from mt.data.bars import check_supported_asset, feed_end, stock_feed
from mt.exchange import TRADING_ZONE
from mt.frames import OHLCV_COLUMNS
from mt.rules.shared import settings


class Bars:
    def __init__(self) -> None:
        self._api = StockHistoricalDataClient(*settings.broker.key_pair)

    def bars(
        self, assets: list[Asset], timeframe: TimeFrame, start: datetime, end: datetime
    ) -> dict[Asset, DataFrame]:
        for asset in assets:
            check_supported_asset(asset)
        frames = {asset: _empty_frame() for asset in assets}
        feed = stock_feed(settings.bars, timeframe.value)
        end = feed_end(settings.bars, feed, end)
        if end < start:
            return frames
        by_symbol = {str(asset): asset for asset in assets}
        for batch in itertools.batched(assets, settings.bars.symbols_per_request, strict=False):
            request = StockBarsRequest(
                symbol_or_symbols=[str(asset) for asset in batch],
                timeframe=timeframe,
                start=start,
                end=end,
                feed=DataFeed(feed),
                adjustment=Adjustment.ALL,
            )
            bar_set = self._api.get_stock_bars(request)
            if not isinstance(bar_set, BarSet):
                raise TypeError(f"expected a BarSet, got {type(bar_set)}")
            if bar_set.df.empty:
                continue
            for symbol, group in bar_set.df.groupby(level="symbol"):
                columns = group.droplevel("symbol")[list(OHLCV_COLUMNS)]
                frames[by_symbol[str(symbol)]] = columns.tz_convert(TRADING_ZONE).sort_index()
        return frames

    def quotes(self, assets: list[Asset], now_at: datetime) -> dict[Asset, float]:
        oldest_at = now_at - timedelta(seconds=settings.bars.trade_max_age_seconds)
        by_symbol = {str(asset): asset for asset in assets}
        prices: dict[Asset, float] = {}
        for batch in itertools.batched(assets, settings.bars.symbols_per_request, strict=False):
            request = StockLatestTradeRequest(
                symbol_or_symbols=[str(asset) for asset in batch],
                feed=DataFeed(settings.bars.intraday_feed),
            )
            for symbol, trade in self._api.get_stock_latest_trade(request).items():
                if trade.timestamp >= oldest_at and trade.price > 0:
                    prices[by_symbol[symbol]] = trade.price
        return prices


def _empty_frame() -> DataFrame:
    return DataFrame(
        columns=list(OHLCV_COLUMNS), index=DatetimeIndex([], tz=TRADING_ZONE), dtype=float
    )
