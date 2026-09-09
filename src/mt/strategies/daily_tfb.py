from typing import ClassVar

from pandas import DataFrame

from mt.config.settings import settings
from mt.indicators import average_turnover_usd, finite_row, finite_value

from .daily import Daily


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    turnover_sessions: ClassVar[int]
    trend_lag_sessions: ClassVar[int]

    @classmethod
    def does_clear(cls, frame: DataFrame) -> bool:
        turnover = average_turnover_usd(frame, cls.turnover_sessions)
        return turnover >= settings.screen.turnover_usd_min

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        average_trend = frame[f"SMA_{cls.trend_sessions}"]
        span = cls.trend_lag_sessions + 1
        row = finite_row(
            [
                finite_value(frame["close"]),
                finite_value(average_trend),
                finite_value(average_trend, -span),
                finite_value(frame[f"ADX_{settings.indicators.period}"]),
                finite_value(frame["high"], -2),
            ]
        )
        if row is None:
            return False
        latest, latest_average, lagged_average, directional_now, previous_high = row
        return (
            latest > latest_average
            and latest_average > lagged_average
            and directional_now >= cls.adx_min
            and latest > previous_high
        )
