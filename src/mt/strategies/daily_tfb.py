from typing import ClassVar

from pandas import DataFrame

from mt.indicators import average_turnover_usd
from mt.rules.sections import DailyTfbSection
from mt.rules.shared import settings

from .daily import DailyAtr


class DailyTfb(DailyAtr):
    key = "daily_tfb"
    code = "t"
    rules: ClassVar[DailyTfbSection] = settings.daily_tfb  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def _does_enter(cls, frame: DataFrame) -> bool:
        turnover = average_turnover_usd(frame, cls.rules.turnover_sessions)
        if turnover <= settings.universe.turnover_usd_min:
            return False
        average = frame[f"SMA_{cls.rules.trend_sessions}"]
        signal = (
            (frame["close"] > average)
            & (average > average.shift(cls.rules.trend_lag_sessions))
            & (frame[f"ADX_{settings.indicators.period_bars}"] >= cls.rules.adx_min)
            & (frame["close"] > frame["high"].shift(1))
        )
        return bool(signal.iloc[-1])
