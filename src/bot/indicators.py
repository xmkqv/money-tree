from collections.abc import Sequence
from math import isfinite
from typing import Any, cast

from pandas import DataFrame, Series
from pandas_ta_classic.trend.adx import adx as ta_adx
from pandas_ta_classic.volatility.atr import atr as ta_atr

from .frames import last_close


PERIOD = 14


def latest_atr(frame: DataFrame, period: int = PERIOD) -> float:
    values = ta_atr(
        frame["high"],
        frame["low"],
        frame["close"],
        length=period,
        talib=False,
    )
    indicator = indicator_series(values, f"ATRr_{period}", 1)
    latest = None if indicator is None else finite_value(indicator)
    if latest is None:
        raise ValueError(f"ATR requires at least {period} price bars")
    return latest


def latest_dollar_volume(frame: DataFrame) -> float:
    if frame.empty or not {"close", "volume"}.issubset(frame.columns):
        return 0.0
    volume = float(frame["volume"].iloc[-1])
    close = last_close(frame)
    if not isfinite(volume) or not isfinite(close) or volume < 0.0 or close < 0.0:
        return 0.0
    return volume * close


def average_dollar_volume(frame: DataFrame, sessions: int) -> float:
    if sessions < 1 or not {"close", "volume"}.issubset(frame.columns):
        return 0.0
    closes = frame["close"].tail(sessions)
    volumes = frame["volume"].tail(sessions)
    if len(closes) < sessions or closes.count() < sessions or volumes.count() < sessions:
        return 0.0
    traded = float((closes * volumes).mean())
    return traded if isfinite(traded) and traded > 0.0 else 0.0


def adx(frame: DataFrame) -> object:
    return ta_adx(
        frame["high"],
        frame["low"],
        frame["close"],
        length=PERIOD,
        talib=False,
    )


def finite_value(values: "Series[Any]", offset: int = -1) -> float | None:
    if len(values) < abs(offset):
        return None
    value = float(cast(float, values.iloc[offset]))
    return value if isfinite(value) else None


def finite_row(values: Sequence[float | None]) -> list[float] | None:
    return None if any(value is None for value in values) else cast(list[float], list(values))


def indicator_series(values: object, name: str, non_null_min: int) -> "Series[Any] | None":
    if not isinstance(values, Series):
        return None
    series = cast("Series[Any]", values)
    if series.name != name or series.count() < non_null_min:
        return None
    return series


def indicator_column(values: object, name: str, non_null_min: int) -> "Series[Any] | None":
    if not isinstance(values, DataFrame) or name not in values.columns:
        return None
    column = values[name]
    return column if column.count() >= non_null_min else None
