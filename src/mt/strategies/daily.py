from abc import abstractmethod
from datetime import date, datetime
from typing import Any, ClassVar, cast

from pandas import DataFrame, Series
from pandas_ta_classic.utils import cross as ta_cross

from mt.data.asset import Asset
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.exchange import TRADING_ZONE
from mt.frames import frame_since, last_close
from mt.indicators import finite_row, finite_value, latest_atr, latest_turnover_usd
from mt.rules.shared import settings

from .base import Candidate, Holding, Portfolio, Session, Strategy, ranked


def is_market_favorable(frame: DataFrame) -> bool:
    row = finite_row(
        [
            finite_value(frame["close"]),
            finite_value(frame[f"SMA_{settings.daily.average_sessions}"]),
        ]
    )
    return row is not None and row[0] > row[1]


def does_signal_exit(frame: DataFrame) -> bool:
    row = finite_row(
        [
            finite_value(frame["close"]),
            finite_value(frame[f"SMA_{settings.daily.average_sessions}"]),
            finite_value(frame[f"RSI_{settings.indicators.period}"]),
        ]
    )
    if row is None:
        return False
    latest, latest_average, strength_now = row
    return latest < latest_average or strength_now < settings.daily.exit_rsi_max


def crossed_above_average(frame: DataFrame) -> Series[Any] | None:
    crossed = ta_cross(
        frame["close"], frame[f"SMA_{settings.daily.average_sessions}"], above=True, asint=False
    )
    return crossed if isinstance(crossed, Series) else None


class Daily(Strategy):
    stop_atr_multiple: ClassVar[float]
    does_heed_earnings: ClassVar[bool]
    trend_sessions: ClassVar[int]
    adx_min: ClassVar[float]

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (settings.daily.average_sessions, cls.trend_sessions)

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._candidates: list[Candidate] = []
        self._scanned_at: date | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return opens, closes

    @classmethod
    @abstractmethod
    def does_enter(cls, frame: DataFrame) -> bool: ...

    @classmethod
    def does_clear(cls, frame: DataFrame) -> bool:
        return True

    def run(self, session: Session) -> None:
        if not session.opens <= session.now < session.closes:
            return
        benchmark = self.portfolio.benchmark_frame()
        if benchmark is None:
            return
        if not is_market_favorable(benchmark):
            self.portfolio.record(
                self,
                "benchmark.blocked",
                "warning",
                f"{settings.benchmark_symbol} is not above its "
                f"{settings.daily.average_sessions}-day average",
            )
            return
        self.enter_candidates(session)

    def enter_candidates(self, session: Session) -> None:
        now = session.now
        for candidate in self.candidates(session):
            if self.is_capped(now):
                return
            if self.portfolio.is_taken(self, candidate.asset, now.date()):
                continue
            price = self.price(candidate.asset)
            if price is None:
                continue
            refreshed = self.refreshed(candidate, price)
            if refreshed is not None:
                self.portfolio.enter(self, refreshed, session)

    def candidates(self, session: Session) -> list[Candidate]:
        day = session.now.date()
        if self._scanned_at != day:
            self._scanned_at = day
            self._candidates = self.scan(session)
        return self._candidates

    def scan(self, session: Session) -> list[Candidate]:
        day = session.now.date()
        candidates = [
            self.candidate(asset, frame)
            for asset, frame in self._ranked()
            if self.does_qualify(asset, frame, day)
        ]
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{day}",
                "info",
                f"{self.name()} found no candidate: no asset passed the universe and setup",
            )
        return candidates

    def does_qualify(self, asset: Asset, frame: DataFrame, day: date) -> bool:
        if not self.does_clear(frame) or not self.does_enter(frame):
            return False
        return not (self.does_heed_earnings and is_earnings_blocked(asset, day))

    def candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        distance = self.stop_atr_multiple * latest_atr(frame, settings.indicators.period)
        return Candidate(asset, last, last - distance)

    def refreshed(self, candidate: Candidate, price: float) -> Candidate | None:
        if price <= candidate.stop:
            return None
        distance = candidate.price - candidate.stop
        return Candidate(candidate.asset, price, price - distance, candidate.direction)

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if (
            self.does_heed_earnings
            and session.opens <= now < session.closes
            and is_earnings_exit_due(holding.asset, now.date())
        ):
            self.portfolio.exit(holding, "earnings")
            return
        frame = self.portfolio.daily_frame(holding.asset)
        if frame is None or len(frame) < settings.daily.average_sessions:
            return
        since = frame_since(frame, holding.entered_at.astimezone(TRADING_ZONE))
        last = last_close(frame)
        if len(since):
            holding.highest = max(holding.highest, float(cast(Any, since["close"]).max()))
        distance = self.stop_atr_multiple * latest_atr(frame, settings.indicators.period)
        holding.raise_stop(holding.highest - distance, "trail")
        if last < holding.stop:
            self.portfolio.exit(holding, holding.stop_reason)
        elif does_signal_exit(frame):
            self.portfolio.exit(holding, "signal")

    def _ranked(self) -> list[tuple[Asset, DataFrame]]:
        rows = [
            (asset, frame)
            for asset in self.portfolio.assets()
            if (frame := self.portfolio.daily_frame(asset)) is not None
        ]
        return ranked(
            rows,
            symbol=lambda row: str(row[0]),
            turnover=lambda row: latest_turnover_usd(row[1]),
        )
