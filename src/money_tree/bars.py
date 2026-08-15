from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl

MARKET = "NYSE"
MARKET_TIMEZONE = ZoneInfo("America/New_York")
PRICE_COLUMNS = ("high", "low", "close")


def normalize_price_bars(frame: pl.DataFrame) -> pl.DataFrame:
    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"price data is missing columns: {names}")
    values = frame.with_columns(
        pl.col(*PRICE_COLUMNS).cast(pl.Float64, strict=True).fill_nan(None),
    )
    invalid_range = values.select((pl.col("high") < pl.col("low")).fill_null(False).any()).item()
    if invalid_range:
        raise ValueError("a price bar has a high below its low")
    return values


def market_datetime_expression(
    frame: pl.DataFrame,
    column: str = "datetime",
) -> pl.Expr:
    datetime_dtype = frame.schema.get(column)
    if not isinstance(datetime_dtype, pl.Datetime):
        raise TypeError(f"bar {column} column must use a datetime type")
    moment = pl.col(column)
    if datetime_dtype.time_zone is None:
        return moment.dt.replace_time_zone(MARKET_TIMEZONE.key)
    return moment.dt.convert_time_zone(MARKET_TIMEZONE.key)


def to_market_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        moment = datetime.fromisoformat(value)
    else:
        raise TypeError(f"unsupported timestamp {value!r}")
    if moment.tzinfo is None:
        return moment.replace(tzinfo=MARKET_TIMEZONE)
    return moment.astimezone(MARKET_TIMEZONE)
