from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any, cast

import pandas.api.types as pandas_types
from pandas import DataFrame, DatetimeIndex

from mt.exchange import TRADING_ZONE, session_ends, session_starts


def normalize_ohlcv(frame: DataFrame, required: Collection[str]) -> DataFrame:
    if not isinstance(frame.index, DatetimeIndex):
        raise ValueError("bars must use a DatetimeIndex")
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"bars are missing required columns: {', '.join(missing)}")
    non_numeric = sorted(
        column for column in required if not cast(Any, pandas_types).is_numeric_dtype(frame[column])
    )
    if non_numeric:
        raise ValueError(f"bar columns must be numeric: {', '.join(non_numeric)}")
    if frame.index.has_duplicates:
        raise ValueError("bar timestamps must be unique")
    values = frame.copy(deep=True)
    index = cast(DatetimeIndex, values.index)
    pandas_index = cast(Any, index)
    if index.tz is None:
        pandas_index = pandas_index.tz_localize(UTC)
    values.index = cast(DatetimeIndex, pandas_index.tz_convert(TRADING_ZONE))
    return values.sort_index()


def regular_session(frame: DataFrame) -> DataFrame:
    index = cast(DatetimeIndex, frame.index)
    timestamps = _time_index(frame)
    inside = (timestamps >= session_starts(index)) & (timestamps < session_ends(index))
    return cast(DataFrame, frame[inside])


def _time_index(frame: DataFrame) -> Any:
    return cast(Any, frame.index)


def last_close(frame: DataFrame) -> float:
    return float(frame["close"].iloc[-1])


def frame_since(frame: DataFrame, start: datetime) -> DataFrame:
    return cast(DataFrame, frame[_time_index(frame) >= start])


def frame_until(frame: DataFrame, cutoff: datetime) -> DataFrame:
    return cast(DataFrame, frame[_time_index(frame) <= cutoff])


def frame_between(frame: DataFrame, start: datetime, end: datetime) -> DataFrame:
    index = _time_index(frame)
    return cast(DataFrame, frame[(index >= start) & (index < end)])
