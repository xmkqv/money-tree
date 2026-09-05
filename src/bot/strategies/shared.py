from collections.abc import Collection, Sequence
from datetime import UTC, date, datetime
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
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.trend.adx import adx as ta_adx
from pandas_ta_classic.utils import cross as ta_cross
from pandas_ta_classic.volatility.atr import atr as ta_atr


yfinance = cast(Any, import_module("yfinance"))


type Direction = Literal[-1, 1]

PERIOD = 14
NOTIONAL_USD_MIN = 1.0
MARKET_SESSIONS = 20
MOMENTUM_SESSIONS = 200
MOMENTUM_RSI_MIN = 50.0
MOMENTUM_ADX_MIN = 25.0
TFB_ADX_MIN = 20.0
TFB_AVERAGE_LAG_SESSIONS = 4
EXIT_RSI_MAX = 50.0
EARNINGS_BLOCK_DAYS = 5
XNYS = exchange_calendars.get_calendar("XNYS")
TRADING_ZONE = ZoneInfo(LUMIBOT_DEFAULT_TIMEZONE)


def session_bounds(day: date) -> tuple[datetime, datetime] | None:
    return _bounds(day) if XNYS.is_session(day) else None


def upcoming_session_bounds(day: date) -> tuple[datetime, datetime]:
    return _bounds(XNYS.date_to_session(day, direction="next"))


def session_starts(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, cast(Any, XNYS).opens)


def session_ends(index: DatetimeIndex) -> DatetimeIndex:
    return _session_stamps(index, cast(Any, XNYS).closes)


def regular_session(frame: DataFrame) -> DataFrame:
    index = cast(DatetimeIndex, frame.index)
    inside = (cast(Any, index) >= session_starts(index)) & (cast(Any, index) < session_ends(index))
    return cast(DataFrame, frame[inside])


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


def latest_atr(frame: DataFrame, period: int = PERIOD) -> float:
    values = ta_atr(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        cast(Series, frame["close"]),
        length=period,
        talib=False,
    )
    indicator = _indicator_series(values, f"ATRr_{period}", 1)
    latest = None if indicator is None else _finite_value(indicator)
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
    if quantity * price < NOTIONAL_USD_MIN:
        return Decimal(0)
    return quantity_value(quantity, fractional_orders)


def quantity_value(quantity: float, fractional_orders: bool) -> Decimal:
    increment = Decimal("0.000000001" if fractional_orders else "1")
    return Decimal(str(quantity)).quantize(increment, rounding=ROUND_DOWN)


def is_fractional_allowed(direction: Direction, fractional_orders: bool) -> bool:
    return fractional_orders and direction == 1


def latest_dollar_volume(frame: DataFrame) -> float:
    if frame.empty or not {"close", "volume"}.issubset(frame.columns):
        return 0.0
    volume = float(cast(float, cast(Series, frame["volume"]).iloc[-1]))
    close = float(cast(float, cast(Series, frame["close"]).iloc[-1]))
    if not isfinite(volume) or not isfinite(close) or volume < 0.0 or close < 0.0:
        return 0.0
    return volume * close


def average_share_volume(frame: DataFrame, sessions: int) -> float:
    if sessions < 1 or "volume" not in frame.columns:
        return 0.0
    volumes = cast(Series, frame["volume"]).tail(sessions)
    if len(volumes) < sessions or volumes.count() < sessions:
        return 0.0
    traded = float(cast(Any, volumes).mean())
    return traded if isfinite(traded) and traded > 0.0 else 0.0


def market_is_rising(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    if close.count() < MARKET_SESSIONS:
        return False
    average = ta_sma(close, length=MARKET_SESSIONS, talib=False)
    if not isinstance(average, Series):
        return False
    row = _finite_row([_finite_value(close), _finite_value(average)])
    if row is None:
        return False
    latest, latest_average = row
    return latest > latest_average


def does_momentum_enter(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    if close.count() < MOMENTUM_SESSIONS:
        return False
    average_20 = ta_sma(close, length=MARKET_SESSIONS, talib=False)
    average_50 = ta_sma(close, length=50, talib=False)
    average_200 = ta_sma(close, length=MOMENTUM_SESSIONS, talib=False)
    strength = _indicator_series(ta_rsi(close, length=PERIOD, talib=False), f"RSI_{PERIOD}", 1)
    directional = _indicator_column(_adx(frame), f"ADX_{PERIOD}", 1)
    if not all(isinstance(value, Series) for value in (average_20, average_50, average_200)):
        return False
    if strength is None or directional is None:
        return False
    crossed = ta_cross(close, cast(Series, average_20), above=True, asint=False)
    if not isinstance(crossed, Series):
        return False
    row = _finite_row(
        [
            _finite_value(close),
            _finite_value(close, -2),
            _finite_value(cast(Series, average_50)),
            _finite_value(cast(Series, average_200)),
            _finite_value(crossed),
            _finite_value(strength),
            _finite_value(directional),
        ]
    )
    if row is None:
        return False
    latest, previous, latest_50, latest_200, crossing, strength_now, directional_now = row
    return (
        bool(crossing)
        and latest > previous
        and latest > latest_50 > latest_200
        and strength_now >= MOMENTUM_RSI_MIN
        and directional_now >= MOMENTUM_ADX_MIN
    )


def does_tfb_enter(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    average_50 = ta_sma(close, length=50, talib=False)
    directional = _indicator_column(_adx(frame), f"ADX_{PERIOD}", 1)
    if not isinstance(average_50, Series) or directional is None:
        return False
    if average_50.tail(TFB_AVERAGE_LAG_SESSIONS).count() < TFB_AVERAGE_LAG_SESSIONS:
        return False
    row = _finite_row(
        [
            _finite_value(close),
            _finite_value(average_50),
            _finite_value(average_50, -TFB_AVERAGE_LAG_SESSIONS),
            _finite_value(directional),
            _finite_value(cast(Series, frame["high"]), -2),
        ]
    )
    if row is None:
        return False
    latest, latest_average, lagged_average, directional_now, previous_high = row
    return (
        latest > latest_average
        and latest_average > lagged_average
        and directional_now >= TFB_ADX_MIN
        and latest > previous_high
    )


def does_signal_exit(frame: DataFrame) -> bool:
    close = cast(Series, frame["close"])
    if close.count() < MARKET_SESSIONS:
        return False
    average = ta_sma(close, length=MARKET_SESSIONS, talib=False)
    strength = _indicator_series(ta_rsi(close, length=PERIOD, talib=False), f"RSI_{PERIOD}", 1)
    if not isinstance(average, Series) or strength is None:
        return False
    row = _finite_row([_finite_value(close), _finite_value(average), _finite_value(strength)])
    if row is None:
        return False
    latest, latest_average, strength_now = row
    return latest < latest_average or strength_now < EXIT_RSI_MAX


def next_stop(direction: Direction, active: float, candidate: float) -> float:
    return max(active, candidate) if direction == 1 else min(active, candidate)


@lru_cache(maxsize=512)
def earnings_dates(symbol: str) -> tuple[date, ...]:
    values = yfinance.Ticker(symbol).get_earnings_dates(limit=24)
    if values is None:
        return ()
    return tuple(sorted({value.date() for value in values.index}))


def next_earnings(symbol: str, day: date) -> date | None:
    return next((value for value in earnings_dates(symbol) if value >= day), None)


def is_earnings_blocked(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    return upcoming is not None and 0 <= (upcoming - day).days <= EARNINGS_BLOCK_DAYS


def is_earnings_exit_due(symbol: str, day: date) -> bool:
    upcoming = next_earnings(symbol, day)
    if upcoming is None:
        return False
    session = XNYS.date_to_session(upcoming, direction="next")
    return day == XNYS.previous_session(session).date()


def _bounds(session: Any) -> tuple[datetime, datetime]:
    opens = cast(Any, XNYS.session_first_minute(session)).astimezone(TRADING_ZONE)
    closes = cast(Any, XNYS.session_close(session)).astimezone(TRADING_ZONE)
    return cast(datetime, opens.to_pydatetime()), cast(datetime, closes.to_pydatetime())


def _session_stamps(index: DatetimeIndex, table: Any) -> DatetimeIndex:
    sessions = cast(Any, index).tz_convert(TRADING_ZONE).normalize().tz_localize(None)
    stamps = DatetimeIndex(table.reindex(sessions).to_numpy(), tz=UTC)
    return cast(DatetimeIndex, cast(Any, stamps).tz_convert(TRADING_ZONE))


def _adx(frame: DataFrame) -> object:
    return ta_adx(
        cast(Series, frame["high"]),
        cast(Series, frame["low"]),
        cast(Series, frame["close"]),
        length=PERIOD,
        talib=False,
    )


def _finite_value(values: Series, offset: int = -1) -> float | None:
    if len(values) < abs(offset):
        return None
    value = float(cast(float, values.iloc[offset]))
    return value if isfinite(value) else None


def _finite_row(values: Sequence[float | None]) -> list[float] | None:
    return None if any(value is None for value in values) else cast(list[float], list(values))


def _indicator_series(values: object, name: str, non_null_min: int) -> Series | None:
    if not isinstance(values, Series) or values.name != name or values.count() < non_null_min:
        return None
    return values


def _indicator_column(values: object, name: str, non_null_min: int) -> Series | None:
    if not isinstance(values, DataFrame) or name not in values.columns:
        return None
    column = cast(Series, values[name])
    return column if column.count() >= non_null_min else None
