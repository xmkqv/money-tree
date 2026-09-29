from datetime import date, datetime, timedelta
from typing import ClassVar

from pandas import DataFrame

from mt.data.asset import Asset
from mt.data.company import is_large_enough
from mt.frames import last_close
from mt.rules.sections import Daily20SmaSection
from mt.rules.shared import settings

from .base import Candidate, Holding, Ladder, Session, trail_distance
from .daily import Daily, does_signal_exit, trend_signal


class Daily20Sma(Daily):
    key = "daily_20sma"
    code = "w"
    rules: ClassVar[Daily20SmaSection] = settings.daily_20sma  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def entry_window(cls, opens_at: datetime, closes_at: datetime) -> tuple[datetime, datetime]:
        return opens_at, min(closes_at, opens_at + timedelta(minutes=cls.rules.entry_minutes))

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        targets = tuple(holding.entry * (1 + gain) for gain in self.rules.target_gains)
        return Ladder(quantity, targets, self.rules.target_fractions)

    @classmethod
    def _does_enter(cls, frame: DataFrame) -> bool:
        rsi = frame[f"RSI_{settings.indicators.period_bars}"]
        signal = trend_signal(frame, cls.rules) & (rsi <= cls.rules.rsi_max)
        return bool(signal.iloc[-1])

    def _does_qualify(self, asset: Asset, frame: DataFrame, session_on: date) -> bool:
        return super()._does_qualify(asset, frame, session_on) and is_large_enough(
            asset, self.rules.market_cap_usd_min, session_on
        )

    def _candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        return Candidate(asset, last, last * (1 - self.rules.stop_fraction))

    def _refreshed(self, candidate: Candidate, price: float) -> Candidate:
        return Candidate(candidate.asset, price, price * (1 - self.rules.stop_fraction))

    def _manage(self, holding: Holding, session: Session) -> None:
        price = self.portfolio.quote(holding.asset)
        if price is None:
            return
        holding.mark(price)
        self._take_target(holding, price)
        self._tighten_stop(holding, session.now)
        if self._is_exit_due(holding, session):
            self.portfolio.exit(holding, "signal")

    def _take_target(self, holding: Holding, price: float) -> None:
        if holding.ladder is None:
            return
        take = holding.ladder.try_take(price, holding.direction)
        if take is not None:
            reason, shares = take
            self.portfolio.exit(holding, reason, shares)

    def _tighten_stop(self, holding: Holding, now_at: datetime) -> None:
        rules = self.rules
        if holding.highest < holding.entry * (1 + rules.breakeven_gain):
            return
        holding.tighten_stop(holding.entry, "breakeven")
        frame = self.portfolio.frames(
            [holding.asset],
            now_at - timedelta(days=rules.trail_lookback_days),
            now_at,
            rules.trail_hours * 60,
        ).get(holding.asset)
        if frame is None:
            return
        distance = trail_distance(frame, rules.trail_atr_multiple, settings.indicators.period_bars)
        if distance is not None:
            holding.tighten_stop(holding.highest - distance, "trail")

    def _is_exit_due(self, holding: Holding, session: Session) -> bool:
        opens_at, until_at = self.entry_window(session.opens_at, session.closes_at)
        if not opens_at <= session.now <= until_at:
            return False
        frame = self.portfolio.get_daily_frame(holding.asset)
        return frame is not None and does_signal_exit(frame)
