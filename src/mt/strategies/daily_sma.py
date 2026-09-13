from typing import ClassVar

from pandas import DataFrame, Series
from pandas_ta_classic.utils import cross as ta_cross

from mt.indicators import finite_row, finite_value
from mt.rules.shared import settings

from .daily import Daily


class DailySma(Daily):
    key = "daily_sma"
    code = "s"
    trend_sessions_long: ClassVar[int]
    rsi_min: ClassVar[float]

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (*super().sma_lengths(), cls.trend_sessions_long)

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        period = settings.indicators.period
        close = frame["close"]
        crossed = ta_cross(
            close, frame[f"SMA_{settings.daily.average_sessions}"], above=True, asint=False
        )
        if not isinstance(crossed, Series):
            return False
        row = finite_row(
            [
                finite_value(close),
                finite_value(close, -2),
                finite_value(frame[f"SMA_{cls.trend_sessions}"]),
                finite_value(frame[f"SMA_{cls.trend_sessions_long}"]),
                finite_value(crossed),
                finite_value(frame[f"RSI_{period}"]),
                finite_value(frame[f"ADX_{period}"]),
            ]
        )
        if row is None:
            return False
        latest, previous, trend, trend_long, crossing, strength_now, directional_now = row
        return (
            bool(crossing)
            and latest > previous
            and latest > trend > trend_long
            and strength_now >= cls.rsi_min
            and directional_now >= cls.adx_min
        )
