from abc import abstractmethod
from datetime import date, datetime
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma

from mt.config.settings import settings
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.exchange import TRADING_ZONE
from mt.frames import frame_since, last_close
from mt.indicators import (
    finite_row,
    finite_value,
    indicator_series,
    latest_atr,
    latest_turnover_usd,
)

from .base import Candidate, Portfolio, Position, Session, Strategy, ranked


def is_market_favorable(frame: DataFrame) -> bool:
    close = frame["close"]
    if close.count() < settings.daily.average_sessions:
        return False
    average = ta_sma(close, length=settings.daily.average_sessions, talib=False)
    if not isinstance(average, Series):
        return False
    row = finite_row([finite_value(close), finite_value(average)])
    if row is None:
        return False
    latest, latest_average = row
    return latest > latest_average


def does_signal_exit(frame: DataFrame) -> bool:
    close = frame["close"]
    if close.count() < settings.daily.average_sessions:
        return False
    average = ta_sma(close, length=settings.daily.average_sessions, talib=False)
    period = settings.indicators.period
    strength = indicator_series(ta_rsi(close, length=period, talib=False), f"RSI_{period}", 1)
    if not isinstance(average, Series) or strength is None:
        return False
    row = finite_row([finite_value(close), finite_value(average), finite_value(strength)])
    if row is None:
        return False
    latest, latest_average, strength_now = row
    return latest < latest_average or strength_now < settings.daily.exit_rsi_max


class Daily(Strategy):
    stop_atr_multiple: ClassVar[float]
    does_heed_earnings: ClassVar[bool]

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
        benchmark = self.portfolio.benchmark_frame(now)
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
            if self.portfolio.is_taken(self, candidate.symbol, now.date()):
                continue
            price = self.portfolio.last_price(candidate.symbol)
            if not isfinite(price) or price <= 0:
                raise ValueError(
                    f"current price for {candidate.symbol} must be finite and positive"
                )
            if price <= candidate.stop:
                continue
            distance = candidate.price - candidate.stop
            refreshed = Candidate(candidate.symbol, price, price - distance, candidate.direction)
            self.portfolio.enter(self, refreshed, session)

    def scan(self, session: Session) -> list[Candidate]:
        now = session.now
        candidates: list[Candidate] = []
        for symbol, frame in self._ranked(now):
            if not self.does_clear(frame) or not self.does_enter(frame):
                continue
            if self.does_heed_earnings and is_earnings_blocked(symbol, now.date()):
                continue
            last = last_close(frame)
            stop = last - self.stop_atr_multiple * latest_atr(frame, settings.indicators.period)
            candidates.append(Candidate(symbol, last, stop))
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{now.date()}",
                "info",
                f"{self.name()} found no candidate: no symbol passed its screen and setup",
            )
        return candidates

    def manage(self, position: Position, session: Session) -> None:
        now = session.now
        if (
            self.does_heed_earnings
            and session.opens <= now < session.closes
            and is_earnings_exit_due(position.symbol, now.date())
        ):
            self.portfolio.exit(position)
            return
        frame = self.portfolio.daily_frame(position.symbol, now)
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

    def _ranked(self, now: datetime) -> list[tuple[str, DataFrame]]:
        rows = [
            (symbol, frame)
            for symbol in self.portfolio.symbols()
            if (frame := self.portfolio.daily_frame(symbol, now)) is not None
        ]
        return ranked(
            rows,
            symbol=lambda row: row[0],
            turnover=lambda row: latest_turnover_usd(row[1]),
        )
