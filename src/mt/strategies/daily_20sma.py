from datetime import date, datetime, timedelta
from typing import ClassVar

from pandas import DataFrame

from mt.data.asset import Asset
from mt.data.company import is_large_enough
from mt.frames import last_close
from mt.indicators import finite_row, finite_value, latest_atr
from mt.rules.shared import settings

from .base import Candidate, Holding, Ladder, Session
from .daily import Daily, crossed_above_average, does_signal_exit


class Daily20Sma(Daily):
    key = "daily_20sma"
    code = "w"
    variation = "20SMA"
    trend_sessions_long: ClassVar[int]
    rsi_min: ClassVar[float]
    rsi_max: ClassVar[float]
    market_cap_usd_min: ClassVar[float]
    entry_minutes: ClassVar[int]
    stop_fraction: ClassVar[float]
    breakeven_gain: ClassVar[float]
    target_gains: ClassVar[tuple[float, float]]
    target_fractions: ClassVar[tuple[float, float]]
    trail_atr_multiple: ClassVar[float]
    trail_hours: ClassVar[int]
    trail_lookback_days: ClassVar[int]

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (*super().sma_lengths(), cls.trend_sessions_long)

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return opens, min(closes, opens + timedelta(minutes=cls.entry_minutes))

    @classmethod
    def does_enter(cls, frame: DataFrame) -> bool:
        period = settings.indicators.period
        crossed = crossed_above_average(frame)
        if crossed is None:
            return False
        row = finite_row(
            [
                finite_value(frame["close"]),
                finite_value(frame[f"SMA_{cls.trend_sessions}"]),
                finite_value(frame[f"SMA_{cls.trend_sessions_long}"]),
                finite_value(crossed),
                finite_value(frame[f"RSI_{period}"]),
                finite_value(frame[f"ADX_{period}"]),
            ]
        )
        if row is None:
            return False
        latest, trend, trend_long, crossing, strength_now, directional_now = row
        return (
            bool(crossing)
            and latest > trend > trend_long
            and cls.rsi_min <= strength_now <= cls.rsi_max
            and directional_now >= cls.adx_min
        )

    def run(self, session: Session) -> None:
        opens, until = self.entry_window(session.opens, session.closes)
        if opens <= session.now <= until:
            self.enter_candidates(session)

    def does_qualify(self, asset: Asset, frame: DataFrame, day: date) -> bool:
        return super().does_qualify(asset, frame, day) and is_large_enough(
            asset, self.market_cap_usd_min, day
        )

    def candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        return Candidate(asset, last, last * (1 - self.stop_fraction))

    def refreshed(self, candidate: Candidate, price: float) -> Candidate | None:
        return Candidate(candidate.asset, price, price * (1 - self.stop_fraction))

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        return Ladder(quantity, tuple(holding.entry * (1 + gain) for gain in self.target_gains))

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        price = self.price(holding.asset)
        if price is None:
            return
        holding.highest = max(holding.highest, price)
        self._take(holding, price)
        self._raise_stop(holding, now)
        if price <= holding.stop:
            self.portfolio.exit(holding, holding.stop_reason)
        elif self._is_exit_due(holding, session):
            self.portfolio.exit(holding, "signal")

    def _take(self, holding: Holding, price: float) -> None:
        ladder = holding.ladder
        if ladder is None or ladder.stage >= len(self.target_fractions):
            return
        if price < ladder.targets[ladder.stage]:
            return
        quantity, reason = ladder.step(self.target_fractions[ladder.stage])
        if quantity > 0:
            self.portfolio.exit(holding, reason, float(quantity))

    def _raise_stop(self, holding: Holding, now: datetime) -> None:
        if holding.highest < holding.entry * (1 + self.breakeven_gain):
            return
        holding.raise_stop(holding.entry, "breakeven")
        trail = self._trail_distance(holding, now)
        if trail is not None:
            holding.raise_stop(holding.highest - trail, "trail")

    def _trail_distance(self, holding: Holding, now: datetime) -> float | None:
        period = settings.indicators.period
        frame = self.portfolio.hour_frames(
            [holding.asset],
            now - timedelta(days=self.trail_lookback_days),
            now,
            self.trail_hours,
        ).get(holding.asset)
        if frame is None or len(frame) <= period:
            return None
        return self.trail_atr_multiple * latest_atr(frame, period)

    def _is_exit_due(self, holding: Holding, session: Session) -> bool:
        opens, until = self.entry_window(session.opens, session.closes)
        if not opens <= session.now <= until:
            return False
        frame = self.portfolio.daily_frame(holding.asset)
        return frame is not None and does_signal_exit(frame)
