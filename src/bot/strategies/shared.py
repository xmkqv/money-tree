from datetime import date
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from importlib import import_module
from typing import Any, Literal, cast

import exchange_calendars
from pandas import DataFrame, Series
from pandas_ta_classic import adx as ta_adx
from pandas_ta_classic import atr as ta_atr
from pandas_ta_classic import cross as ta_cross
from pandas_ta_classic import macd as ta_macd
from pandas_ta_classic import rsi as ta_rsi
from pandas_ta_classic import sma as ta_sma


type Direction = Literal[-1, 1]

PERIOD = 14
MIN_NOTIONAL_USD = 1.0
XNYS = exchange_calendars.get_calendar("XNYS")


def latest_atr(frame: DataFrame, period: int = PERIOD) -> float:
    values = ta_atr(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        cast(Series, frame["close"]),
        length=period,
        talib=False,
    )
    if values is None or values.dropna().empty:
        raise ValueError(f"ATR requires at least {period} price bars")
    return float(values.dropna().iloc[-1])


def entry_quantity(
    equity: float,
    price: float,
    stop_distance: float,
    position_fraction_max: float,
    risk_per_trade_max: float,
    fractional_orders: bool,
) -> Decimal:
    if equity <= 0 or price <= 0 or stop_distance <= 0:
        return Decimal(0)
    quantity = min(
        equity * position_fraction_max / price,
        equity * risk_per_trade_max / stop_distance,
    )
    if quantity * price < MIN_NOTIONAL_USD:
        return Decimal(0)
    return quantity_value(quantity, fractional_orders)


def quantity_value(quantity: float, fractional_orders: bool) -> Decimal:
    increment = Decimal("0.000000001" if fractional_orders else "1")
    return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)


def market_is_rising(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    average = ta_sma(close, length=20, talib=False)
    if average is None:
        return False
    return float(close.iloc[-1]) > float(average.iloc[-1])


def momentum_entry(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
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
    if (
        average_20 is None
        or average_50 is None
        or average_200 is None
        or not isinstance(strength, Series)
        or directional is None
    ):
        return False
    crossed = ta_cross(close, average_20, above=True, asint=False)
    if crossed is None:
        return False
    last = float(close.iloc[-1])
    trend = last > float(average_50.iloc[-1]) > float(average_200.iloc[-1])
    return (
        bool(crossed.iloc[-1])
        and trend
        and 50.0 <= float(strength.iloc[-1]) <= 70.0
        and float(directional["ADX_14"].iloc[-1]) >= 25.0
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
    if average_50 is None or directional is None:
        return False
    return (
        float(close.iloc[-1]) > float(average_50.iloc[-1])
        and float(average_50.iloc[-1]) > float(average_50.iloc[-4])
        and float(directional["ADX_14"].iloc[-1]) >= 20.0
        and float(close.iloc[-1]) > float(cast(Any, frame["high"]).iloc[-2])
    )


def signal_exit(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    average_20 = ta_sma(close, length=20, talib=False)
    strength = ta_rsi(close, length=PERIOD, talib=False)
    if average_20 is None or not isinstance(strength, Series):
        return False
    return (
        float(close.iloc[-1]) < float(average_20.iloc[-1])
        and float(strength.iloc[-1]) < 50.0
    )


def does_macd_confirm(close: Series, direction: Direction) -> bool:
    values = ta_macd(close, fast=12, slow=26, signal=9, talib=False)
    if values is None:
        return False
    line = values["MACD_12_26_9"]
    return len(line) >= 2 and (
        float(line.iloc[-1]) > float(line.iloc[-2])
    ) == (direction == 1)


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
