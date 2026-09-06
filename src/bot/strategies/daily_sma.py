from typing import cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.utils import cross as ta_cross

from bot.indicators import PERIOD, adx, finite_row, finite_value, indicator_column, indicator_series
from bot.types import POSITION_FRACTION_CAP
from bot.universe import percent

from .daily import AVERAGE_SESSIONS, Daily


TREND_SESSIONS = 50
MOMENTUM_SESSIONS = 200
RSI_MIN = 50.0
ADX_MIN = 25.0


class DailySma(Daily):
    key = "daily_sma"
    code = "s"
    variation = "SMA"
    stop_atr_multiple = 1.5
    does_heed_earnings = True
    setup_rule = (
        "The closing price crosses back above its 20-day average while the trend is "
        "already stacked underneath it: price above the 50-day average, and that "
        "average above the 200-day. Needs 200 sessions of history."
    )
    confirmation_rule = f"RSI ({PERIOD}) at 50 or above, and ADX ({PERIOD}) at 25 or above."
    entry_rule = (
        "A three-day structure: one session closes below the 20-day average, the next "
        "closes back above it and higher than that first close, and the buy goes in at "
        "the open of the third. Market buy, retried every iteration until the close. "
        "Skipped if "
        "the company reports earnings within 5 days. A company with no earnings date on "
        "file can still be bought. A company whose calendar cannot be read at all is left "
        "for that session."
    )
    setup_source = "strategies/daily_sma.py · does_enter"
    entry_source = "strategies/daily_sma.py · does_enter, strategies/daily.py · run"

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        close = frame["close"]
        if close.count() < MOMENTUM_SESSIONS:
            return False
        average_20 = ta_sma(close, length=AVERAGE_SESSIONS, talib=False)
        average_50 = ta_sma(close, length=TREND_SESSIONS, talib=False)
        average_200 = ta_sma(close, length=MOMENTUM_SESSIONS, talib=False)
        strength = indicator_series(ta_rsi(close, length=PERIOD, talib=False), f"RSI_{PERIOD}", 1)
        directional = indicator_column(adx(frame), f"ADX_{PERIOD}", 1)
        if not all(isinstance(value, Series) for value in (average_20, average_50, average_200)):
            return False
        if strength is None or directional is None:
            return False
        crossed = ta_cross(close, cast(Series, average_20), above=True, asint=False)
        if not isinstance(crossed, Series):
            return False
        row = finite_row(
            [
                finite_value(close),
                finite_value(close, -2),
                finite_value(cast(Series, average_50)),
                finite_value(cast(Series, average_200)),
                finite_value(crossed),
                finite_value(strength),
                finite_value(directional),
            ]
        )
        if row is None:
            return False
        latest, previous, latest_50, latest_200, crossing, strength_now, directional_now = row
        return (
            bool(crossing)
            and latest > previous
            and latest > latest_50 > latest_200
            and strength_now >= RSI_MIN
            and directional_now >= ADX_MIN
        )

    @classmethod
    def risk_rule(cls, per_trade: float) -> str:
        return (
            "No per-trade risk limit is set for this strategy, so the size comes from the "
            f"position cap alone: never more than {percent(POSITION_FRACTION_CAP)} of equity."
        )
