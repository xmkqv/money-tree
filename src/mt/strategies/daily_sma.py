from typing import ClassVar

from pandas import DataFrame

from mt.rules.sections import DailySmaSection
from mt.rules.shared import settings

from .daily import DailyAtr, trend_signal


class DailySma(DailyAtr):
    key = "daily_sma"
    code = "s"
    rules: ClassVar[DailySmaSection] = settings.daily_sma  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def _does_enter(cls, frame: DataFrame) -> bool:
        close = frame["close"]
        signal = trend_signal(frame, cls.rules) & (close > close.shift(1))
        return bool(signal.iloc[-1])
