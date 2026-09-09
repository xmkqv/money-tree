from datetime import UTC, datetime
from typing import Any, cast

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from pandas import DataFrame

from mt.config.bot import settings
from mt.config.values import DataFeedName, Timeframe
from mt.frames import normalize_ohlcv

from .alpaca import bars_end_at


class BarsAlpaca:
    def __init__(self) -> None:
        self._bars = StockHistoricalDataClient(
            settings.broker.api_key.get_secret_value(),
            settings.broker.api_secret.get_secret_value(),
        )

    def bars(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        feed: DataFeedName,
    ) -> dict[str, DataFrame]:
        frames: dict[str, DataFrame] = {}
        page = settings.portfolio.symbols_per_request
        for offset in range(0, len(symbols), page):
            request = StockBarsRequest(
                symbol_or_symbols=symbols[offset : offset + page],
                start=start.astimezone(UTC),
                end=bars_end_at(end, feed, settings.bars.sip_delay_minutes).astimezone(UTC),
                timeframe=_timeframe(timeframe),
                adjustment=Adjustment.ALL,
                feed=DataFeed(feed),
            )
            values = cast(DataFrame, cast(Any, self._bars.get_stock_bars(request)).df)
            if values.empty:
                continue
            symbols_index = cast(
                list[object],
                cast(Any, values.index).get_level_values("symbol").unique().tolist(),
            )
            for symbol_value in symbols_index:
                symbol = str(symbol_value)
                frame = values.xs(symbol_value, level="symbol")
                if not isinstance(frame, DataFrame):
                    raise TypeError(f"bars for {symbol} are not a frame")
                frames[symbol] = normalize_ohlcv(frame, {"high", "low", "close", "volume"})
        return frames


def _timeframe(value: Timeframe) -> TimeFrame:
    unit = value.lstrip("0123456789")
    return TimeFrame(int(value.removesuffix(unit)), TimeFrameUnit(unit))
