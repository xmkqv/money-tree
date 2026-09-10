from abc import abstractmethod
from datetime import date, datetime
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame

from mt.config.shared import settings
from mt.data.asset import Asset
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.exchange import TRADING_ZONE
from mt.frames import frame_since, last_close
from mt.indicators import finite_row, finite_value, latest_atr, latest_turnover_usd

from .base import Candidate, Portfolio, Position, Session, Strategy, ranked


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

    def begin(self, day: date) -> None:
        self._candidates = []
        self._scanned_at = None

    def run(self, session: Session) -> None:
        now = session.now
        if not session.opens <= now < session.closes:
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
        if self._scanned_at != now.date():
            self._scanned_at = now.date()
            self._candidates = self.scan(session)
        for candidate in self._candidates:
            if self.is_capped():
                self.portfolio.record(
                    self,
                    f"entries.capped.{now.date()}",
                    "info",
                    f"{self.name()} entries paused: {self.positions_max} positions already open",
                )
                return
            if self.portfolio.is_taken(self, candidate.asset, now.date()):
                continue
            price = self.portfolio.last_price(candidate.asset)
            if not isfinite(price) or price <= 0:
                raise ValueError(f"current price for {candidate.asset} must be finite and positive")
            if price <= candidate.stop:
                continue
            distance = candidate.price - candidate.stop
            refreshed = Candidate(candidate.asset, price, price - distance, candidate.direction)
            self.portfolio.enter(self, refreshed, session)

    def scan(self, session: Session) -> list[Candidate]:
        now = session.now
        candidates: list[Candidate] = []
        for asset, frame in self._ranked():
            if not self.does_clear(frame) or not self.does_enter(frame):
                continue
            if self.does_heed_earnings and is_earnings_blocked(asset, now.date()):
                continue
            last = last_close(frame)
            stop = last - self.stop_atr_multiple * latest_atr(frame, settings.indicators.period)
            candidates.append(Candidate(asset, last, stop))
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{now.date()}",
                "info",
                f"{self.name()} found no candidate: no asset passed its screen and setup",
            )
        return candidates

    def manage(self, position: Position, session: Session) -> None:
        now = session.now
        if (
            self.does_heed_earnings
            and session.opens <= now < session.closes
            and is_earnings_exit_due(position.asset, now.date())
        ):
            self.portfolio.exit(position)
            return
        frame = self.portfolio.daily_frame(position.asset)
        if frame is None or len(frame) < settings.daily.average_sessions:
            return
        since = frame_since(frame, position.entered_at.astimezone(TRADING_ZONE))
        last = last_close(frame)
        if len(since):
            position.highest = max(position.highest, float(cast(Any, since["close"]).max()))
        distance = self.stop_atr_multiple * latest_atr(frame, settings.indicators.period)
        position.stop = max(position.stop, position.highest - distance)
        if last < position.stop or does_signal_exit(frame):
            self.portfolio.exit(position)

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
