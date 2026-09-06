from typing import cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.utils import cross as ta_cross

from bot.config import settings
from bot.indicators import adx, finite_row, finite_value, indicator_column, indicator_series
from bot.universe import percent

from .daily import Daily


class DailySma(Daily):
    key = "daily_sma"
    code = "s"
    variation = "SMA"
    is_paused = settings.daily_sma.is_paused
    positions_max = settings.daily_sma.positions_max
    risk_fraction_max = settings.daily_sma.risk_fraction_max
    stop_atr_multiple = settings.daily_sma.stop_atr_multiple
    does_heed_earnings = settings.daily_sma.does_heed_earnings
    setup_rule = (
        f"The closing price crosses back above its {settings.daily.average_sessions}-day average "
        f"while the trend is already stacked underneath it: price above the "
        f"{settings.daily_sma.trend_sessions}-day average, and that average above the "
        f"{settings.daily_sma.trend_sessions_long}-day. Needs "
        f"{settings.daily_sma.trend_sessions_long} sessions of history."
    )
    confirmation_rule = (
        f"RSI ({settings.indicators.period}) at {settings.daily_sma.rsi_min:g} or above, and ADX "
        f"({settings.indicators.period}) at {settings.daily_sma.adx_min:g} or above."
    )
    entry_rule = (
        f"A three-day structure: one session closes below the "
        f"{settings.daily.average_sessions}-day average, the next closes back above it and "
        "higher than that first close, and the buy "
        "goes in at the open of the third. Market buy, retried every iteration until the close. "
        f"Skipped if the company reports earnings within {settings.earnings.block_days} days. A "
        "company with no earnings date on file can still be bought. A company whose calendar "
        "cannot be read at all is left for that session."
    )
    setup_source = "strategies/daily_sma.py · does_enter"
    entry_source = "strategies/daily_sma.py · does_enter, strategies/daily.py · run"

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        daily_sma = settings.daily_sma
        period = settings.indicators.period
        close = frame["close"]
        if close.count() < daily_sma.trend_sessions_long:
            return False
        average_20 = ta_sma(close, length=settings.daily.average_sessions, talib=False)
        average_50 = ta_sma(close, length=daily_sma.trend_sessions, talib=False)
        average_200 = ta_sma(close, length=daily_sma.trend_sessions_long, talib=False)
        strength = indicator_series(ta_rsi(close, length=period, talib=False), f"RSI_{period}", 1)
        directional = indicator_column(adx(frame), f"ADX_{period}", 1)
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
            and strength_now >= daily_sma.rsi_min
            and directional_now >= daily_sma.adx_min
        )

    @classmethod
    def risk_rule(cls, per_trade: float) -> str:
        return (
            "No per-trade risk limit is set for this strategy, so the size comes from the "
            f"position cap alone: never more than {percent(settings.risk.position_fraction_max)} "
            "of equity."
        )
