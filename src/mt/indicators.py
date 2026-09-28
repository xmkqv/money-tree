from collections.abc import Collection
from math import isfinite, nan
from typing import Any

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.trend.adx import adx as ta_adx
from pandas_ta_classic.volatility.atr import atr as ta_atr

from mt.frames import last_close


def daily_indicators(frame: DataFrame, lengths: Collection[int], period: int) -> DataFrame:
    close = frame["close"]
    rsi = ta_rsi(close, length=period, talib=False)
    atr = ta_atr(frame["high"], frame["low"], close, length=period, talib=False)
    directional = ta_adx(frame["high"], frame["low"], frame["close"], length=period, talib=False)
    columns: dict[str, Series | float] = {
        f"SMA_{length}": close.rolling(length).mean() for length in lengths
    }
    columns[f"RSI_{period}"] = rsi if isinstance(rsi, Series) else nan
    columns[f"ATRr_{period}"] = atr if isinstance(atr, Series) else nan
    columns[f"ADX_{period}"] = (
        directional[f"ADX_{period}"] if isinstance(directional, DataFrame) else nan
    )
    return frame.assign(**columns)


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
    traded = (frame["close"] * frame["volume"]).tail(sessions)
    if traded.count() < sessions:
        return 0.0
    average = float(traded.mean())
    return average if isfinite(average) and average > 0.0 else 0.0


def finite_value(values: Series[Any]) -> float | None:
    if values.empty:
        return None
    value = float(values.iloc[-1])
    return value if isfinite(value) else None
