from collections.abc import Collection
from datetime import UTC
from typing import cast

from pandas import DataFrame, DatetimeIndex
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
    index = frame.index
    localized = index if index.tz is not None else index.tz_localize(UTC)
    return frame.set_axis(localized.tz_convert(TRADING_ZONE)).sort_index()


def regular_session(frame: DataFrame) -> DataFrame:
    index = cast(DatetimeIndex, frame.index)
    inside = (index >= session_starts(index)) & (index < session_ends(index))
    return frame[inside]


def last_close(frame: DataFrame) -> float:
    return float(frame["close"].iloc[-1])
