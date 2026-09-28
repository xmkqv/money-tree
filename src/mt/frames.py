from collections.abc import Collection
from datetime import UTC, datetime
from typing import cast

from pandas import DataFrame, DatetimeIndex, Timestamp
from pandas.api.types import is_numeric_dtype

from mt.exchange import TRADING_ZONE, session_ends, session_starts


def normalize_ohlcv(frame: DataFrame, required: Collection[str]) -> DataFrame:
    if not isinstance(frame.index, DatetimeIndex):
        raise ValueError("bars must use a DatetimeIndex")
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"bars are missing required columns: {', '.join(missing)}")
    non_numeric = sorted(column for column in required if not is_numeric_dtype(frame[column]))
    if non_numeric:
        raise ValueError(f"bar columns must be numeric: {', '.join(non_numeric)}")
    if frame.index.has_duplicates:
        raise ValueError("bar timestamps must be unique")
    values = frame.copy(deep=True)
    index = cast(DatetimeIndex, values.index)
    localized = index if index.tz is not None else index.tz_localize(UTC)
    values.index = localized.tz_convert(TRADING_ZONE)
    return values.sort_index()


def regular_session(frame: DataFrame) -> DataFrame:
    index = cast(DatetimeIndex, frame.index)
    inside = (index >= session_starts(index)) & (index < session_ends(index))
    return frame[inside]


def last_close(frame: DataFrame) -> float:
    return float(frame["close"].iloc[-1])


def frame_since(frame: DataFrame, start: datetime) -> DataFrame:
    return frame.loc[start:]


def frame_until(frame: DataFrame, cutoff: datetime) -> DataFrame:
    return frame.loc[:cutoff]


def frame_between(frame: DataFrame, start: datetime, end: datetime) -> DataFrame:
    index = cast(DatetimeIndex, frame.index)
    inside = (index >= Timestamp(start)) & (index < Timestamp(end))
    return frame[inside]
