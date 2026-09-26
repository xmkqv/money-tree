from datetime import datetime, timedelta
from decimal import Decimal
from typing import ClassVar

from pandas import DataFrame, Series
from pandas_ta_classic.utils import cross as ta_cross

from mt.data.company import is_large_enough
from mt.data.earnings import is_earnings_blocked
from mt.frames import last_close
from mt.indicators import finite_row, finite_value, latest_atr
from mt.rules.shared import settings
from mt.sizing import round_quantity

from .base import Candidate, Holding, Ladder, Session
from .daily import Daily, does_signal_exit


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
        close = frame["close"]
        crossed = ta_cross(
            close, frame[f"SMA_{settings.daily.average_sessions}"], above=True, asint=False
        )
        if not isinstance(crossed, Series):
            return False
        row = finite_row(
            [
                finite_value(close),
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
        now = session.now
        opens, until = self.entry_window(session.opens, session.closes)
        if not opens <= now <= until:
            return
        if self._scanned_at != now.date():
            self._scanned_at = now.date()
            self._candidates = self.scan(session)
        for candidate in self._candidates:
            if self.is_capped(now):
                return
            if self.portfolio.is_taken(self, candidate.asset, now.date()):
                continue
            price = self.price(candidate.asset)
            stop = price * (1 - self.stop_fraction)
            self.portfolio.enter(self, Candidate(candidate.asset, price, stop), session)

    def scan(self, session: Session) -> list[Candidate]:
        now = session.now
        candidates: list[Candidate] = []
        for asset, frame in self._ranked():
            if not self.does_enter(frame):
                continue
            if self.does_heed_earnings and is_earnings_blocked(asset, now.date()):
                continue
            if not is_large_enough(asset, self.market_cap_usd_min, now.date()):
                continue
            last = last_close(frame)
            candidates.append(Candidate(asset, last, last * (1 - self.stop_fraction)))
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{now.date()}",
                "info",
                f"{self.name()} found no candidate: no asset passed the universe and setup",
            )
        return candidates

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        return Ladder(quantity, tuple(holding.entry * (1 + gain) for gain in self.target_gains))

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        price = self.price(holding.asset)
        holding.highest = max(holding.highest, price)
        self._take(holding, price)
        holding.stop = max(holding.stop, self._raised_stop(holding, now))
        if price <= holding.stop or self._is_exit_due(holding, session):
            self.portfolio.exit(holding)

    def _take(self, holding: Holding, price: float) -> None:
        ladder = holding.ladder
        if ladder is None or ladder.stage >= len(self.target_fractions):
            return
        if price < ladder.targets[ladder.stage]:
            return
        share = self.target_fractions[ladder.stage]
        quantity = round_quantity(Decimal(str(ladder.original_quantity)) * Decimal(str(share)))
        ladder.stage += 1
        if quantity > 0:
            self.portfolio.exit(holding, float(quantity))

    def _raised_stop(self, holding: Holding, now: datetime) -> float:
        if holding.highest < holding.entry * (1 + self.breakeven_gain):
            return holding.stop
        trail = self._trail_distance(holding, now)
        if trail is None:
            return holding.entry
        return max(holding.entry, holding.highest - trail)

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
        if frame is None or len(frame) < settings.daily.average_sessions:
            return False
        return does_signal_exit(frame)
