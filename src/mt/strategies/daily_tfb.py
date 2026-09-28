from typing import ClassVar

from pandas import DataFrame

from mt.indicators import average_turnover_usd
from mt.rules.sections import DailyTfbSection, DailyVariationSection
from mt.rules.shared import settings

from .daily import Daily


class DailyTfb(Daily):
    key = "daily_tfb"
    code = "t"
    rules: ClassVar[DailyVariationSection] = settings.daily_tfb
    holdings_max = rules.holdings_max
    is_paused = rules.is_paused

    @classmethod
    def _rules(cls) -> DailyTfbSection:
        rules = cls.rules
        if not isinstance(rules, DailyTfbSection):
            raise TypeError(f"{cls.name()} needs its turnover-following rules")
        return rules

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        if frame.empty:
            return False
        rules = cls._rules()
        turnover = average_turnover_usd(frame, rules.turnover_sessions)
        if turnover <= settings.universe.turnover_usd_min:
            return False
        average = frame[f"SMA_{rules.trend_sessions}"]
        signal = (
            (frame["close"] > average)
            & (average > average.shift(rules.trend_lag_sessions))
            & (frame[f"ADX_{settings.indicators.period}"] >= rules.adx_min)
            & (frame["close"] > frame["high"].shift(1))
        )
        return bool(signal.iloc[-1])
