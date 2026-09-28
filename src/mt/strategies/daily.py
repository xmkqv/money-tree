from abc import abstractmethod
from datetime import date, datetime
from typing import Any, ClassVar

from pandas import DataFrame, Series
from pandas_ta_classic.utils import cross as ta_cross

from mt.data.asset import Asset
from mt.data.earnings import is_earnings_blocked, is_earnings_exit_due
from mt.exchange import TRADING_ZONE
from mt.frames import last_close
from mt.indicators import latest_atr, latest_turnover_usd
from mt.rules.sections import DailyAtrSection, DailyVariationSection
from mt.rules.shared import settings

from .base import Candidate, Holding, Portfolio, Session, Strategy, ranked


def is_market_favorable(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    signal = frame["close"] > frame[f"SMA_{settings.daily.average_sessions}"]
    return bool(signal.iloc[-1])


def does_signal_exit(frame: DataFrame) -> bool:
    if frame.empty:
        return False
    average = f"SMA_{settings.daily.average_sessions}"
    strength = f"RSI_{settings.indicators.period}"
    inputs = frame[["close", average, strength]]
    if inputs.iloc[-1].isna().any():
        return False
    signal = (frame["close"] < frame[average]) | (frame[strength] < settings.daily.exit_rsi_max)
    return bool(signal.iloc[-1])


def crossed_above_average(frame: DataFrame) -> Series[Any] | None:
    crossed = ta_cross(
        frame["close"], frame[f"SMA_{settings.daily.average_sessions}"], above=True, asint=False
    )
    return crossed if isinstance(crossed, Series) else None


class Daily(Strategy):
    rules: ClassVar[DailyVariationSection]

    @classmethod
    def sma_lengths(cls) -> tuple[int, ...]:
        return (settings.daily.average_sessions, cls.rules.trend_sessions)

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._candidates: list[Candidate] | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return opens, closes

    @classmethod
    @abstractmethod
    def does_enter(cls, frame: DataFrame) -> bool: ...

    @classmethod
    def does_clear(cls, frame: DataFrame) -> bool:
        return True

    def begin(self, session_on: date) -> None:
        self._candidates = None

    def run(self, session: Session) -> None:
        benchmark = self.portfolio.daily_frame(Asset.from_symbol(settings.benchmark_symbol))
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
            if self.portfolio.is_taken(self, candidate.asset):
                continue
            price = self.portfolio.quote(candidate.asset)
            if price is None:
                continue
            refreshed = self.refreshed(candidate, price)
            if refreshed is not None:
                self.portfolio.enter(self, refreshed, session)

    def candidates(self, session: Session) -> list[Candidate]:
        if self._candidates is None:
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
        return not (self.rules.does_heed_earnings and is_earnings_blocked(asset, day))

    def _atr_rules(self) -> DailyAtrSection:
        rules = self.rules
        if not isinstance(rules, DailyAtrSection):
            raise TypeError(f"{self.name()} needs an ATR-based stop rule")
        return rules

    def candidate(self, asset: Asset, frame: DataFrame) -> Candidate:
        last = last_close(frame)
        period = settings.indicators.period
        distance = self._atr_rules().stop_atr_multiple * latest_atr(frame, period)
        return Candidate(asset, last, last - distance)

    def refreshed(self, candidate: Candidate, price: float) -> Candidate | None:
        if price <= candidate.stop:
            return None
        distance = candidate.price - candidate.stop
        return Candidate(candidate.asset, price, price - distance, candidate.direction)

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if (
            self.rules.does_heed_earnings
            and session.opens <= now < session.closes
            and is_earnings_exit_due(holding.asset, now.date())
        ):
            self.portfolio.exit(holding, "earnings")
            return
        self._manage(holding, session)

    def _manage(self, holding: Holding, session: Session) -> None:
        frame = self.portfolio.daily_frame(holding.asset)
        if frame is None or len(frame) < settings.daily.average_sessions:
            return
        since = frame.loc[holding.entered_at.astimezone(TRADING_ZONE) :]
        last = last_close(frame)
        if len(since):
            holding.highest = max(holding.highest, float(since["close"].max()))
        period = settings.indicators.period
        distance = self._atr_rules().stop_atr_multiple * latest_atr(frame, period)
        holding.tighten_stop(holding.highest - distance, "trail")
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
            score=lambda row: latest_turnover_usd(row[1]),
        )
