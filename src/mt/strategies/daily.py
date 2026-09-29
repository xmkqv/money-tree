from abc import abstractmethod
from datetime import date, datetime
from typing import ClassVar, Protocol

from pandas import DataFrame, Series

from mt.data.asset import Asset
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.exchange import TRADING_ZONE
from mt.frames import last_close, ranked
from mt.indicators import latest_atr, latest_turnover_usd
from mt.rules.sections import DailyAtrSection
from mt.rules.shared import settings

from .base import Candidate, Holding, Portfolio, Session, Strategy


class TrendRules(Protocol):
    @property
    def trend_sessions(self) -> int: ...

    @property
    def trend_sessions_long(self) -> int: ...

    @property
    def rsi_min(self) -> float: ...

    @property
    def adx_min(self) -> float: ...


def does_signal_exit(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    average = f"SMA_{settings.daily.average_sessions}"
    strength = f"RSI_{settings.indicators.period_bars}"
    last = frame[["close", average, strength]].iloc[-1]
    if last.isna().any():
        return False
    return bool(last["close"] < last[average] or last[strength] < settings.daily.exit_rsi_max)


def trend_signal(frame: DataFrame, rules: TrendRules) -> Series[bool]:
    period_bars = settings.indicators.period_bars
    close = frame["close"]
    trend = frame[f"SMA_{rules.trend_sessions}"]
    return (
        _crossed_above_average(frame)
        & (close > trend)
        & (trend > frame[f"SMA_{rules.trend_sessions_long}"])
        & (frame[f"RSI_{period_bars}"] >= rules.rsi_min)
        & (frame[f"ADX_{period_bars}"] >= rules.adx_min)
    )


class Daily(Strategy):
    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        trends = (value for name, value in cls.rules if name.startswith("trend_sessions"))
        return (settings.daily.average_sessions, *trends)

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._found: list[Candidate] | None = None

    @classmethod
    def entry_window(cls, opens_at: datetime, closes_at: datetime) -> tuple[datetime, datetime]:
        return opens_at, closes_at

    def begin(self, session: Session) -> None:
        self._found = None

    def run(self, session: Session) -> None:
        benchmark = self.portfolio.get_daily_frame(Asset.from_symbol(settings.benchmark_symbol))
        if benchmark is None:
            return
        if not _is_market_favorable(benchmark):
            self.portfolio.record(
                self,
                "benchmark.blocked",
                "warning",
                f"{settings.benchmark_symbol} is not above its "
                f"{settings.daily.average_sessions}-day average",
            )
            return
        self._enter_candidates(session)

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if session.opens_at <= now < session.closes_at and is_earnings_exit_due(
            holding.asset, now.date()
        ):
            self.portfolio.exit(holding, "earnings")
            return
        self._manage(holding, session)

    @classmethod
    @abstractmethod
    def _does_enter(cls, frame: DataFrame) -> bool: ...

    @abstractmethod
    def _candidate(self, asset: Asset, frame: DataFrame) -> Candidate: ...

    @abstractmethod
    def _refreshed(self, candidate: Candidate, price: float) -> Candidate: ...

    @abstractmethod
    def _manage(self, holding: Holding, session: Session) -> None: ...

    def _does_qualify(self, asset: Asset, frame: DataFrame, session_on: date) -> bool:
        if frame.empty or not self._does_enter(frame):
            return False
        return not is_earnings_blocked(asset, session_on)

    def _enter_candidates(self, session: Session) -> None:
        for candidate in self._candidates(session):
            if self.is_capped(session):
                return
            if self.portfolio.is_taken(self, candidate.asset):
                continue
            price = self.portfolio.quote(candidate.asset)
            if price is None:
                continue
            self.portfolio.enter(self, self._refreshed(candidate, price), session)

    def _candidates(self, session: Session) -> list[Candidate]:
        if self._found is None:
            self._found = self._scan(session)
        return self._found

    def _scan(self, session: Session) -> list[Candidate]:
        session_on = session.now.date()
        candidates = [
            self._candidate(asset, frame)
            for asset, frame in self._ranked()
            if self._does_qualify(asset, frame, session_on)
        ]
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{session_on}",
                "info",
                f"{self.name()} found no candidate: no asset passed the universe and setup",
            )
        return candidates

    def _ranked(self) -> list[tuple[Asset, DataFrame]]:
        rows = [
            (asset, frame)
            for asset in self.portfolio.assets()
            if (frame := self.portfolio.get_daily_frame(asset)) is not None
        ]
        return ranked(
            rows,
            symbol=lambda row: str(row[0]),
            score=lambda row: latest_turnover_usd(row[1]),
        )


class DailyAtr(Daily):
    rules: ClassVar[DailyAtrSection]  # pyright: ignore[reportIncompatibleVariableOverride]

    def _candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        return Candidate(asset, last, last - self._stop_distance(frame))

    def _refreshed(self, candidate: Candidate, price: float) -> Candidate:
        distance = candidate.price - candidate.stop
        return Candidate(candidate.asset, price, price - distance, candidate.direction)

    def _manage(self, holding: Holding, session: Session) -> None:
        frame = self.portfolio.get_daily_frame(holding.asset)
        if frame is None or len(frame) < settings.daily.average_sessions:
            return
        since = frame.loc[holding.entered_at.astimezone(TRADING_ZONE) :]
        if not since.empty:
            highest_close = float(since["close"].max())
            holding.mark(highest_close)
            holding.tighten_stop(highest_close - self._stop_distance(frame), "trail")
        if does_signal_exit(frame):
            self.portfolio.exit(holding, "signal")

    def _stop_distance(self, frame: DataFrame) -> float:
        return self.rules.stop_atr_multiple * latest_atr(frame, settings.indicators.period_bars)


def _is_market_favorable(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    signal = frame["close"] > frame[f"SMA_{settings.daily.average_sessions}"]
    return bool(signal.iloc[-1])


def _crossed_above_average(frame: DataFrame) -> Series[bool]:
    average = frame[f"SMA_{settings.daily.average_sessions}"]
    close = frame["close"]
    return (close > average) & (close.shift(1) < average.shift(1))
