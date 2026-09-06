from abc import abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, ClassVar, cast

from pandas import DataFrame, Series
from pandas_ta_classic.momentum.rsi import rsi as ta_rsi
from pandas_ta_classic.overlap.sma import sma as ta_sma

from bot.config import settings
from bot.earnings import is_earnings_blocked, is_earnings_exit_due
from bot.exchange import TRADING_ZONE
from bot.frames import frame_since, last_close
from bot.indicators import (
    finite_row,
    finite_value,
    indicator_series,
    latest_atr,
    latest_dollar_volume,
)
from bot.universe import UNIVERSE

from .base import Candidate, Holding, Portfolio, Rule, Session, Strategy, ranked


def is_market_rising(frame: DataFrame) -> bool:
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
    family = "daily"
    kind = "Daily trend"
    stop_atr_multiple: ClassVar[float]
    does_heed_earnings: ClassVar[bool]
    market_rule: ClassVar[str] = UNIVERSE
    market_source: ClassVar[str] = "portfolio.py · _eligible_symbols"
    setup_rule: ClassVar[str]
    confirmation_rule: ClassVar[str]
    entry_rule: ClassVar[str]
    setup_source: ClassVar[str]
    entry_source: ClassVar[str]
    risk_source: ClassVar[str] = "portfolio.py · enter"

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._candidates: list[Candidate] = []
        self._scanned_on: date | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return opens, closes

    @classmethod
    @abstractmethod
    def does_enter(cls, frame: DataFrame) -> bool: ...

    @classmethod
    def is_eligible(cls, frame: DataFrame) -> bool:
        return True

    @classmethod
    @abstractmethod
    def risk_rule(cls, per_trade: float) -> str: ...

    def begin(self, day: date) -> None:
        self._candidates = []
        self._scanned_on = None

    def run(self, session: Session) -> None:
        now = session.now
        market = self.portfolio.market_frame(now)
        if market is None:
            return
        if not is_market_rising(market):
            self.portfolio.record(
                self, "market.stalled", "warning", "SPX is not above its 20-day average"
            )
            return
        if self._scanned_on != now.date():
            self._scanned_on = now.date()
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
            self.portfolio.enter(self, candidate, session)

    def scan(self, session: Session) -> list[Candidate]:
        now = session.now
        candidates: list[Candidate] = []
        for symbol, frame in self._ranked(now):
            if not self.is_eligible(frame) or not self.does_enter(frame):
                continue
            if self.does_heed_earnings and not self._is_earnings_clear(symbol, now.date()):
                continue
            last = last_close(frame)
            stop = last - self.stop_atr_multiple * latest_atr(frame)
            candidates.append(Candidate(symbol, last, stop))
        if not candidates:
            self.portfolio.record(
                self,
                f"scan.emptied.{now.date()}",
                "info",
                f"{self.name()} found no candidate: no eligible name passed its screen and setup",
            )
        return candidates

    def manage(self, holding: Holding, session: Session) -> None:
        now, closes = session.now, session.closes
        if (
            self.does_heed_earnings
            and now >= closes - timedelta(minutes=settings.earnings.exit_lead_minutes)
            and self._is_earnings_exit_due(holding.symbol, now.date())
        ):
            self.portfolio.exit(holding)
            return
        frame = self.portfolio.daily_frame(holding.symbol, now)
        if frame is None or len(frame) < settings.daily.average_sessions:
            return
        since = frame_since(frame, holding.entered_at.astimezone(TRADING_ZONE))
        last = last_close(frame)
        if len(since):
            holding.highest = max(holding.highest, float(cast(Any, since["close"]).max()))
        holding.stop = max(
            holding.stop, holding.highest - self.stop_atr_multiple * latest_atr(frame)
        )
        if last < holding.stop or does_signal_exit(frame):
            self.portfolio.exit(holding)

    def _ranked(self, now: datetime) -> list[tuple[str, DataFrame]]:
        rows = [
            (symbol, frame)
            for symbol in self.portfolio.eligible_symbols()
            if (frame := self.portfolio.daily_frame(symbol, now)) is not None
        ]
        return ranked(
            rows,
            symbol=lambda row: row[0],
            turnover=lambda row: latest_dollar_volume(row[1]),
        )

    def _is_earnings_clear(self, symbol: str, day: date) -> bool:
        try:
            return not is_earnings_blocked(symbol, day)
        except Exception as error:
            self._earnings_unavailable(symbol, error)
            return False

    def _is_earnings_exit_due(self, symbol: str, day: date) -> bool:
        try:
            return is_earnings_exit_due(symbol, day)
        except Exception as error:
            self._earnings_unavailable(symbol, error)
            return False

    def _earnings_unavailable(self, symbol: str, error: Exception) -> None:
        self.portfolio.record(
            self,
            f"earnings.unavailable.{symbol}",
            "error",
            f"Earnings calendar unavailable for {symbol}: {type(error).__name__}",
        )

    @classmethod
    def describe(cls, per_trade: float, opens: datetime, closes: datetime) -> list[Rule]:
        lead_minutes = settings.earnings.exit_lead_minutes
        period = settings.indicators.period
        earnings_exit = f"{closes - timedelta(minutes=lead_minutes):%H:%M}"
        return [
            Rule(field="Market", value=cls.market_rule, source=cls.market_source),
            Rule(
                field="Sentiment",
                value="The S&P 500 must be trading above its own 20-day average. If it is not, "
                "no daily strategy takes a position that day.",
                source="strategies/daily.py · run",
            ),
            Rule(field="Direction", value="Long only.", source="portfolio.py · enter"),
            Rule(
                field="Range",
                value="Not used. This strategy reads daily candles and has no opening range.",
                source="strategies/daily.py · run",
            ),
            Rule(field="Setup", value=cls.setup_rule, source=cls.setup_source),
            Rule(field="Confirmation", value=cls.confirmation_rule, source=cls.setup_source),
            Rule(
                field="Sorting",
                value="Ranked by the value traded in the last completed session, which is its "
                "close times its share volume, highest first. When more symbols qualify on the "
                "same morning than there is room to hold, the busiest take the slots. A symbol "
                "whose session cannot be read ranks last but still trades.",
                source="strategies/daily.py · _ranked",
            ),
            Rule(field="Entry", value=cls.entry_rule, source=cls.entry_source),
            Rule(
                field="Stop Loss",
                value=f"{cls.stop_atr_multiple:g}x the {period}-period ATR below the entry "
                f"price, then trailing {cls.stop_atr_multiple:g}x ATR below the highest close "
                "reached since entry. The stop only ever moves up.",
                source="strategies/daily.py · manage",
            ),
            Rule(field="Max Risk", value=cls.risk_rule(per_trade), source=cls.risk_source),
            Rule(
                field="Min. R:R",
                value="No fixed target. The trade is held while the trend holds and closed on "
                "the exit rule below, so no reward-to-risk ratio is set in advance.",
                source="strategies/daily.py · manage",
            ),
            Rule(
                field="Exit Rule",
                value="Closed when the price falls through the trailing stop, or when the close "
                f"drops below its 20-day average, or RSI ({period}) falls under "
                f"{settings.daily.exit_rsi_max:g}. Either one is enough on its own.",
                source="strategies/daily.py · does_signal_exit",
            ),
            Rule(
                field="Emergency Exit",
                value=(
                    f"Closed {lead_minutes} minutes before the closing bell "
                    f"({earnings_exit} on a full session) on the session before the company "
                    "reports earnings, unless that calendar cannot be read, in which case the "
                    "position is left alone. The daily loss limit closes all positions and "
                    "stops new entries for the rest of the day."
                    if cls.does_heed_earnings
                    else "The daily loss limit closes all positions and stops new entries for "
                    "the rest of the day. Earnings do not close a position for this strategy. "
                    "It holds through the report and leaves on its threshold or its exit rule."
                ),
                source="strategies/daily.py · manage, portfolio.py · _is_daily_loss_reached",
            ),
        ]
