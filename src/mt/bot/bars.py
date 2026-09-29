import itertools
import re
from datetime import datetime, timedelta

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.models.bars import BarSet
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from pandas import DataFrame

from mt.data.asset import Asset
from mt.data.bars import feed_end, stock_feed
from mt.exchange import TRADING_ZONE
from mt.rules.shared import settings
from mt.rules.values import Timeframe


class Bars:
    def __init__(self) -> None:
        self._api = StockHistoricalDataClient(*settings.broker.key_pair)

    def bars(
        self, assets: list[Asset], timeframe: Timeframe, start: datetime, end: datetime
    ) -> dict[Asset, DataFrame]:
        match = re.fullmatch(r"(\d+)(Min|Hour|Day)", timeframe)
        if match is None:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        amount, unit = match.groups()
        feed = stock_feed(settings.bars, timeframe)
        end = feed_end(settings.bars, feed, end)
        if end < start:
            return {}
        by_symbol = {str(asset): asset for asset in assets}
        frames: dict[Asset, DataFrame] = {}
        for batch in itertools.batched(assets, settings.bars.symbols_per_request, strict=False):
            request = StockBarsRequest(
                symbol_or_symbols=[str(asset) for asset in batch],
                timeframe=TimeFrame(int(amount), TimeFrameUnit(unit)),
                start=start,
                end=end,
                feed=DataFeed(feed),
                adjustment=Adjustment.ALL,
            )
            bar_set = self._api.get_stock_bars(request)
            if not isinstance(bar_set, BarSet):
                raise TypeError(f"expected a BarSet, got {type(bar_set)}")
            frame = bar_set.df
            if frame.empty:
                continue
            for symbol, group in frame.groupby(level="symbol"):
                columns = group.droplevel("symbol")[["open", "high", "low", "close", "volume"]]
                frames[by_symbol[str(symbol)]] = columns.tz_convert(TRADING_ZONE).sort_index()
        return frames

    def quotes(self, assets: list[Asset], now: datetime) -> dict[Asset, float]:
        if not assets:
            return {}
        oldest = now - timedelta(seconds=settings.bars.trade_max_age_seconds)
        by_symbol = {str(asset): asset for asset in assets}
        prices: dict[Asset, float] = {}
        for batch in itertools.batched(assets, settings.bars.symbols_per_request, strict=False):
            request = StockLatestTradeRequest(
                symbol_or_symbols=[str(asset) for asset in batch],
                feed=DataFeed(settings.bars.intraday_feed),
            )
            for symbol, trade in self._api.get_stock_latest_trade(request).items():
                if trade.timestamp >= oldest and trade.price > 0:
                    prices[by_symbol[symbol]] = trade.price
        return prices
