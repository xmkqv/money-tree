from datetime import date, datetime, timedelta
from typing import ClassVar

from pandas import DataFrame

from mt.data.asset import Asset
from mt.data.company import is_large_enough
from mt.frames import last_close
from mt.indicators import latest_atr
from mt.rules.sections import Daily20SmaSection, DailyVariationSection
from mt.rules.shared import settings

from .base import Candidate, Holding, Ladder, Session
from .daily import Daily, crossed_above_average, does_signal_exit


class Daily20Sma(Daily):
    key = "daily_20sma"
    code = "w"
    variation = "20SMA"
    rules: ClassVar[DailyVariationSection] = settings.daily_20sma
    holdings_max = rules.holdings_max
    is_paused = rules.is_paused

    @classmethod
    def _rules(cls) -> Daily20SmaSection:
        rules = cls.rules
        if not isinstance(rules, Daily20SmaSection):
            raise TypeError(f"{cls.name()} needs its 20-SMA rules")
        return rules

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (*super().sma_lengths(), cls._rules().trend_sessions_long)

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return opens, min(closes, opens + timedelta(minutes=cls._rules().entry_minutes))

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        if frame.empty:
            return False
        rules = cls._rules()
        period = settings.indicators.period
        crossed = crossed_above_average(frame)
        close = frame["close"]
        trend = frame[f"SMA_{rules.trend_sessions}"]
        trend_long = frame[f"SMA_{rules.trend_sessions_long}"]
        rsi = frame[f"RSI_{period}"]
        signal = (
            crossed
            & (close > trend)
            & (trend > trend_long)
            & (rsi >= rules.rsi_min)
            & (rsi <= rules.rsi_max)
            & (frame[f"ADX_{period}"] >= rules.adx_min)
        )
        return bool(signal.iloc[-1])

    def does_qualify(self, asset: Asset, frame: DataFrame, day: date) -> bool:
        return super().does_qualify(asset, frame, day) and is_large_enough(
            asset, self._rules().market_cap_usd_min, day
        )

    def candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        return Candidate(asset, last, last * (1 - self._rules().stop_fraction))

    def refreshed(self, candidate: Candidate, price: float) -> Candidate | None:
        return Candidate(candidate.asset, price, price * (1 - self._rules().stop_fraction))

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        gains = self._rules().target_gains
        return Ladder(quantity, tuple(holding.entry * (1 + gain) for gain in gains))

    def _manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        price = self.portfolio.quote(holding.asset)
        if price is None:
            return
        holding.highest = max(holding.highest, price)
        self._take(holding, price)
        self._tighten_stop(holding, now)
        if price <= holding.stop:
            self.portfolio.exit(holding, holding.stop_reason)
        elif self._is_exit_due(holding, session):
            self.portfolio.exit(holding, "signal")

    def _take(self, holding: Holding, price: float) -> None:
        ladder = holding.ladder
        fractions = self._rules().target_fractions
        if ladder is None or ladder.stage >= len(fractions):
            return
        if price < ladder.targets[ladder.stage]:
            return
        quantity, reason = ladder.step(fractions[ladder.stage])
        if quantity > 0:
            self.portfolio.exit(holding, reason, float(quantity))

    def _tighten_stop(self, holding: Holding, now: datetime) -> None:
        rules = self._rules()
        if holding.highest < holding.entry * (1 + rules.breakeven_gain):
            return
        holding.tighten_stop(holding.entry, "breakeven")
        trail = self._trail_distance(holding, now)
        if trail is not None:
            holding.tighten_stop(holding.highest - trail, "trail")

    def _trail_distance(self, holding: Holding, now: datetime) -> float | None:
        rules = self._rules()
        period = settings.indicators.period
        frame = self.portfolio.frames(
            [holding.asset],
            now - timedelta(days=rules.trail_lookback_days),
            now,
            rules.trail_hours * 60,
        ).get(holding.asset)
        if frame is None or len(frame) <= period:
            return None
        return rules.trail_atr_multiple * latest_atr(frame, period)

    def _is_exit_due(self, holding: Holding, session: Session) -> bool:
        opens, until = self.entry_window(session.opens, session.closes)
        if not opens <= session.now <= until:
            return False
        frame = self.portfolio.daily_frame(holding.asset)
        return frame is not None and does_signal_exit(frame)
