from pandas import DataFrame, Series
from pandas_ta_classic.overlap.sma import sma as ta_sma

from mt.config.settings import settings
from mt.frames import last_close
from mt.indicators import (
    adx,
    average_turnover_usd,
    finite_row,
    finite_value,
    indicator_column,
)

from .daily import Daily


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    variation = "TFB"
    is_paused = settings.daily_tfb.is_paused
    positions_max = settings.daily_tfb.positions_max
    risk_fraction_max = settings.daily_tfb.risk_fraction_max
    stop_atr_multiple = settings.daily_tfb.stop_atr_multiple
    does_heed_earnings = settings.daily_tfb.does_heed_earnings

    @classmethod
    def does_clear(cls, frame: DataFrame) -> bool:
        if frame.empty:
            return False
        if last_close(frame) < settings.screen.price_usd_min:
            return False
        sessions = settings.daily_tfb.turnover_sessions
        return average_turnover_usd(frame, sessions) >= settings.screen.turnover_usd_min

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        daily_tfb = settings.daily_tfb
        period = settings.indicators.period
        close = frame["close"]
        average_trend = ta_sma(close, length=daily_tfb.trend_sessions, talib=False)
        directional = indicator_column(adx(frame), f"ADX_{period}", 1)
        if not isinstance(average_trend, Series) or directional is None:
            return False
        span = daily_tfb.trend_lag_sessions + 1
        if average_trend.tail(span).count() < span:
            return False
        row = finite_row(
            [
                finite_value(close),
                finite_value(average_trend),
                finite_value(average_trend, -span),
                finite_value(directional),
                finite_value(frame["high"], -2),
            ]
        )
        if row is None:
            return False
        latest, latest_average, lagged_average, directional_now, previous_high = row
        return (
            latest > latest_average
            and latest_average > lagged_average
            and directional_now >= daily_tfb.adx_min
            and latest > previous_high
        )
