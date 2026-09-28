from typing import ClassVar

from pandas import DataFrame

from mt.rules.sections import DailySmaSection, DailyVariationSection
from mt.rules.shared import settings

from .daily import Daily, crossed_above_average


class DailySma(Daily):
    key = "daily_sma"
    code = "s"
    rules: ClassVar[DailyVariationSection] = settings.daily_sma
    holdings_max = rules.holdings_max
    is_paused = rules.is_paused

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (*super().sma_lengths(), cls._rules().trend_sessions_long)

    @classmethod
    def _rules(cls) -> DailySmaSection:
        rules = cls.rules
        if not isinstance(rules, DailySmaSection):
            raise TypeError(f"{cls.name()} needs its daily-SMA rules")
        return rules

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        if frame.empty:
            return False
        rules = cls._rules()
        period = settings.indicators.period
        crossed = crossed_above_average(frame)
        if crossed is None:
            return False
        close = frame["close"]
        signal = (
            crossed
            & (close > close.shift(1))
            & (close > frame[f"SMA_{rules.trend_sessions}"])
            & (frame[f"SMA_{rules.trend_sessions}"] > frame[f"SMA_{rules.trend_sessions_long}"])
            & (frame[f"RSI_{period}"] >= rules.rsi_min)
            & (frame[f"ADX_{period}"] >= rules.adx_min)
        )
        return bool(signal.iloc[-1])
