from typing import cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma
from pandas_ta_classic.utils import cross as ta_cross

from mt.config.settings import settings
from mt.indicators import adx, finite_row, finite_value, indicator_column, indicator_series

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

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        daily_sma = settings.daily_sma
        period = settings.indicators.period
        close = frame["close"]
        if close.count() < daily_sma.trend_sessions_long:
            return False
        average_signal = ta_sma(close, length=settings.daily.average_sessions, talib=False)
        average_trend = ta_sma(close, length=daily_sma.trend_sessions, talib=False)
        average_trend_long = ta_sma(close, length=daily_sma.trend_sessions_long, talib=False)
        strength = indicator_series(ta_rsi(close, length=period, talib=False), f"RSI_{period}", 1)
        directional = indicator_column(adx(frame), f"ADX_{period}", 1)
        averages = (average_signal, average_trend, average_trend_long)
        if not all(isinstance(value, Series) for value in averages):
            return False
        if strength is None or directional is None:
            return False
        crossed = ta_cross(close, cast(Series, average_signal), above=True, asint=False)
        if not isinstance(crossed, Series):
            return False
        row = finite_row(
            [
                finite_value(close),
                finite_value(close, -2),
                finite_value(cast(Series, average_trend)),
                finite_value(cast(Series, average_trend_long)),
                finite_value(crossed),
                finite_value(strength),
                finite_value(directional),
            ]
        )
        if row is None:
            return False
        latest, previous, trend, trend_long, crossing, strength_now, directional_now = row
        return (
            bool(crossing)
            and latest > previous
            and latest > trend > trend_long
            and strength_now >= daily_sma.rsi_min
            and directional_now >= daily_sma.adx_min
        )
