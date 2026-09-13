from collections.abc import Collection, Sequence
from math import isfinite, nan
from typing import Any, cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.trend.adx import adx as ta_adx
from pandas_ta_classic.volatility.atr import atr as ta_atr

from mt.frames import last_close


def daily_indicators(frame: DataFrame, lengths: Collection[int], period: int) -> DataFrame:
    close = frame["close"]
    columns: dict[str, object] = {
        f"SMA_{length}": ta_sma(close, length=length, talib=False) for length in lengths
    }
    columns[f"RSI_{period}"] = ta_rsi(close, length=period, talib=False)
    columns[f"ATRr_{period}"] = ta_atr(
        frame["high"], frame["low"], close, length=period, talib=False
    )
    directional = ta_adx(frame["high"], frame["low"], frame["close"], length=period, talib=False)
    columns[f"ADX_{period}"] = (
        directional[f"ADX_{period}"] if isinstance(directional, DataFrame) else nan
    )
    prepared: dict[str, Any] = {
        name: value if isinstance(value, Series) else nan for name, value in columns.items()
    }
    return frame.assign(**prepared)


def latest_atr(frame: DataFrame, period: int) -> float:
    name = f"ATRr_{period}"
    values = (
        frame[name]
        if name in frame.columns
        else ta_atr(frame["high"], frame["low"], frame["close"], length=period, talib=False)
    )
    latest = finite_value(values) if isinstance(values, Series) else None
    if latest is None:
        raise ValueError(f"ATR requires at least {period} price bars")
    return latest


def latest_turnover_usd(frame: DataFrame) -> float:
    if frame.empty:
        return 0.0
    volume = float(frame["volume"].iloc[-1])
    close = last_close(frame)
    if not isfinite(volume) or not isfinite(close) or volume < 0.0 or close < 0.0:
        return 0.0
    return volume * close


def average_turnover_usd(frame: DataFrame, sessions: int) -> float:
    closes = frame["close"].tail(sessions)
    volumes = frame["volume"].tail(sessions)
    if len(closes) < sessions or closes.count() < sessions or volumes.count() < sessions:
        return 0.0
    traded = float((closes * volumes).mean())
    return traded if isfinite(traded) and traded > 0.0 else 0.0


def finite_value(values: "Series[Any]", offset: int = -1) -> float | None:
    if len(values) < abs(offset):
        return None
    value = float(cast(float, values.iloc[offset]))
    return value if isfinite(value) else None


def finite_row(values: Sequence[float | None]) -> list[float] | None:
    return None if any(value is None for value in values) else cast(list[float], list(values))
