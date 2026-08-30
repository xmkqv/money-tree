from collections.abc import Collection
from datetime import UTC, date
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from importlib import import_module
from math import isfinite
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import exchange_calendars
import pandas.api.types as pandas_types
from lumibot.constants import LUMIBOT_DEFAULT_TIMEZONE
from pandas import DataFrame, DatetimeIndex, Series
from pandas_ta_classic.momentum.macd import macd as ta_macd
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.trend.adx import adx as ta_adx
from pandas_ta_classic.utils import cross as ta_cross
from pandas_ta_classic.volatility.atr import atr as ta_atr


type Direction = Literal[-1, 1]

PERIOD = 14
MIN_NOTIONAL_USD = 1.0
XNYS = exchange_calendars.get_calendar("XNYS")
TRADING_ZONE = ZoneInfo(LUMIBOT_DEFAULT_TIMEZONE)


def normalize_ohlcv(frame: DataFrame, required: Collection[str]) -> DataFrame:
    if not isinstance(frame.index, DatetimeIndex):
        raise ValueError("market data must use a DatetimeIndex")
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"market data is missing required columns: {', '.join(missing)}")
    non_numeric = sorted(
        column for column in required if not cast(Any, pandas_types).is_numeric_dtype(frame[column])
    )
    if non_numeric:
        raise ValueError(f"market data required columns must be numeric: {', '.join(non_numeric)}")
    if frame.index.has_duplicates:
        raise ValueError("market data timestamps must be unique")
    values = frame.copy(deep=True)
    index = cast(DatetimeIndex, values.index)
    pandas_index = cast(Any, index)
    if index.tz is None:
        pandas_index = pandas_index.tz_localize(UTC)
    values.index = cast(DatetimeIndex, pandas_index.tz_convert(TRADING_ZONE))
    return values.sort_index()


def _finite_value(values: Series, offset: int = -1) -> float | None:
    if len(values) < abs(offset):
        return None
    value = float(cast(float, values.iloc[offset]))
    return value if isfinite(value) else None


def _indicator_series(
    values: object,
    name: str,
    non_null_min: int,
) -> Series | None:
    if not isinstance(values, Series) or values.name != name or values.count() < non_null_min:
        return None
    return values


def _indicator_column(
    values: object,
    name: str,
    non_null_min: int,
) -> Series | None:
    if not isinstance(values, DataFrame) or name not in values.columns:
        return None
    column = cast(Series, values[name])
    return column if column.count() >= non_null_min else None


def latest_atr(frame: DataFrame, period: int = PERIOD) -> float:
    values = ta_atr(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        cast(Series, frame["close"]),
        length=period,
        talib=False,
    )
    indicator = _indicator_series(values, f"ATRr_{period}", 1)
    if indicator is None:
        raise ValueError(f"ATR requires at least {period} price bars")
    latest = _finite_value(indicator)
    if latest is None:
        raise ValueError(f"ATR requires at least {period} price bars")
    return latest


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_per_trade_max: float | None,
    fractional_orders: bool,
) -> Decimal:
    """Size a position from the notional cap, and from risk when a limit is set.

    A strategy whose register reads "risk per trade = not set" passes None, and
    is then sized by the notional cap alone. The stop still has to be a real
    distance: a non-positive one means the caller's levels are wrong.
    """
    if (
        not all(isfinite(value) for value in (equity, price, stop_distance))
        or equity <= 0
        or price <= 0
        or stop_distance <= 0
    ):
        return Decimal(0)
    quantity = equity * position_fraction_max / price
    if risk_per_trade_max is not None:
        quantity = min(quantity, equity * risk_per_trade_max / stop_distance)
    if quantity * price < MIN_NOTIONAL_USD:
        return Decimal(0)
    return quantity_value(quantity, fractional_orders)


def quantity_value(quantity: float, fractional_orders: bool) -> Decimal:
    increment = Decimal("0.000000001" if fractional_orders else "1")
    return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)


def market_is_rising(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    if close.count() < 20:
        return False
    average = ta_sma(close, length=20, talib=False)
    if not isinstance(average, Series):
        return False
    latest = _finite_value(close)
    latest_average = _finite_value(average)
    return latest is not None and latest_average is not None and latest > latest_average


def momentum_entry(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    if close.count() < 200:
        return False
    average_20 = ta_sma(close, length=20, talib=False)
    average_50 = ta_sma(close, length=50, talib=False)
    average_200 = ta_sma(close, length=200, talib=False)
    strength = ta_rsi(close, length=PERIOD, talib=False)
    directional = ta_adx(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        close,
        length=PERIOD,
        talib=False,
    )
    strength_values = _indicator_series(strength, f"RSI_{PERIOD}", 1)
    directional_values = _indicator_column(directional, f"ADX_{PERIOD}", 1)
    if not all(isinstance(value, Series) for value in (average_20, average_50, average_200)):
        return False
    if strength_values is None or directional_values is None:
        return False
    average_20 = cast(Series, average_20)
    average_50 = cast(Series, average_50)
    average_200 = cast(Series, average_200)
    crossed = ta_cross(close, average_20, above=True, asint=False)
    if not isinstance(crossed, Series):
        return False
    latest = _finite_value(close)
    previous = _finite_value(close, -2)
    latest_20 = _finite_value(average_20)
    latest_50 = _finite_value(average_50)
    latest_200 = _finite_value(average_200)
    latest_cross = _finite_value(crossed)
    latest_strength = _finite_value(strength_values)
    latest_directional = _finite_value(directional_values)
    if None in {
        latest,
        previous,
        latest_20,
        latest_50,
        latest_200,
        latest_cross,
        latest_strength,
        latest_directional,
    }:
        return False
    assert latest is not None
    assert previous is not None
    assert latest_20 is not None
    assert latest_50 is not None
    assert latest_200 is not None
    assert latest_cross is not None
    assert latest_strength is not None
    assert latest_directional is not None
    trend = latest > latest_50 > latest_200
    # The cross settles day 1 below and day 2 above the 20-day average. Day 2
    # must also close up on day 1, so the reclaim is carried by the buyer rather
    # than by an average drifting down onto a flat price.
    return (
        bool(latest_cross)
        and latest > previous
        and trend
        and latest_strength >= 50.0
        and latest_directional >= 25.0
    )


def tfb_entry(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    average_50 = ta_sma(close, length=50, talib=False)
    directional = ta_adx(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        close,
        length=PERIOD,
        talib=False,
    )
    directional_values = _indicator_column(directional, f"ADX_{PERIOD}", 1)
    if not isinstance(average_50, Series) or directional_values is None:
        return False
    recent_average = cast(Series, average_50.iloc[-4:])
    if len(recent_average) < 4 or recent_average.count() < 4:
        return False
    latest = _finite_value(close)
    latest_average = _finite_value(average_50)
    lagged_average = _finite_value(average_50, -4)
    latest_directional = _finite_value(directional_values)
    previous_high = _finite_value(cast(Series, frame["high"]), -2)
    if None in {latest, latest_average, lagged_average, latest_directional, previous_high}:
        return False
    assert latest is not None
    assert latest_average is not None
    assert lagged_average is not None
    assert latest_directional is not None
    assert previous_high is not None
    return (
        latest > latest_average
        and latest_average > lagged_average
        and latest_directional >= 20.0
        and latest > previous_high
    )


def signal_exit(frame: DataFrame) -> bool:
    """Momentum has given out: the close is under its average and RSI is weak."""
    close = cast(Series, frame["close"])
    if close.count() < 20:
        return False
    average = ta_sma(close, length=20, talib=False)
    strength = ta_rsi(close, length=PERIOD, talib=False)
    strength_values = _indicator_series(strength, f"RSI_{PERIOD}", 1)
    if not isinstance(average, Series) or strength_values is None:
        return False
    latest = _finite_value(close)
    latest_average = _finite_value(average)
    latest_strength = _finite_value(strength_values)
    return (
        latest is not None
        and latest_average is not None
        and latest_strength is not None
        and latest < latest_average
        and latest_strength < 50.0
    )


def does_macd_confirm(close: Series, direction: Direction) -> bool:
    values = ta_macd(close, fast=12, slow=26, signal=9, talib=False)
    line = _indicator_column(values, "MACD_12_26_9", 2)
    if line is None:
        return False
    latest = _finite_value(line)
    previous = _finite_value(line, -2)
    return latest is not None and previous is not None and (latest > previous) == (direction == 1)


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


@lru_cache(maxsize=2048)
def security_is_eligible(symbol: str) -> bool:
    finance = cast(Any, import_module("yfinance"))
    market_cap = finance.Ticker(symbol).fast_info.market_cap
    return market_cap is not None and float(market_cap) >= 500_000_000


@lru_cache(maxsize=512)
def earnings_dates(symbol: str) -> tuple[date, ...]:
    finance = cast(Any, import_module("yfinance"))
    values = finance.Ticker(symbol).get_earnings_dates(limit=24)
    if values is None:
        return ()
    return tuple(sorted({value.date() for value in values.index}))


def next_earnings(symbol: str, day: date) -> date | None:
    return next((value for value in earnings_dates(symbol) if value >= day), None)


def earnings_blocked(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    return upcoming is None or 0 <= (upcoming - day).days <= 5


def earnings_exit_due(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    if upcoming is None:
        return False
    session = XNYS.date_to_session(upcoming, direction="next")
    return day == XNYS.previous_session(session).date()
