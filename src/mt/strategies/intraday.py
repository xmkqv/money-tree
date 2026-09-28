from datetime import date, datetime, timedelta
from typing import ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.data.asset import Asset
from mt.exchange import TRADING_ZONE, session_starts
from mt.frames import regular_session
from mt.rules.sections import IntradayMimSection
from mt.rules.shared import settings

from .base import Candidate, Holding, Portfolio, Session, Strategy


def opening_moves(frame: DataFrame) -> Series[float]:
    regular = regular_session(frame)
    if regular.empty:
        return Series(dtype=float)
    index = cast(DatetimeIndex, regular.index)
    sessions = index.normalize()
    opening = index == session_starts(index)
    first = regular.loc[opening, "close"].set_axis(sessions[opening])
    last = regular["close"].groupby(sessions).last()
    prior = last.shift(1).reindex(first.index)
    return cast("Series[float]", (first / prior - 1.0).dropna())


class Intraday(Strategy):
    is_stop_resting = True
    rules: ClassVar[IntradayMimSection]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._signal: tuple[Asset | None, float] | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return (
            max(opens, closes - timedelta(minutes=cls.rules.entry_minutes_before_close)),
            closes - timedelta(minutes=cls.rules.close_lead_minutes),
        )

    def begin(self, session_on: date) -> None:
        self._signal = None

    def run(self, session: Session) -> None:
        now = session.now
        if self._signal is None:
            self._signal = self._read_signal(now)
        if self._signal is None:
            return
        asset, band = self._signal
        if asset is None or self.is_capped(now) or self.portfolio.is_taken(self, asset):
            return
        price = self.portfolio.quote(asset)
        if price is None:
            return
        stop = price * (1 - self.rules.stop_band_multiple * band)
        self.portfolio.enter(self, Candidate(asset, price, stop), session)

    def manage(self, holding: Holding, session: Session) -> None:
        if session.now >= session.closes - timedelta(minutes=self.rules.close_lead_minutes):
            self.portfolio.exit(holding, "close")

    def _read_signal(self, now: datetime) -> tuple[Asset | None, float] | None:
        day = now.date()
        long_asset = Asset.from_symbol(self.rules.long_symbol)
        frame = self.portfolio.frames(
            [long_asset],
            now - timedelta(days=self.rules.lookback_days),
            now,
            self.rules.first_minutes,
        ).get(long_asset)
        moves = Series(dtype=float) if frame is None else opening_moves(frame)
        today = Timestamp(day, tz=TRADING_ZONE)
        history = moves[moves.index < today].tail(self.rules.noise_sessions)
        if today not in moves.index or len(history) < self.rules.noise_sessions:
            self.portfolio.record(
                self,
                f"signal.unread.{day}",
                "warning",
                f"{self.name()} has no signal yet: {self.rules.long_symbol} lacks "
                f"{self.rules.noise_sessions} sessions of opening moves",
            )
            return None
        move = float(cast(float, moves[today]))
        band = float(history.abs().mean())
        if move == 0 or abs(move) < self.rules.noise_multiple * band:
            self.portfolio.record(
                self,
                f"signal.quiet.{day}",
                "info",
                f"{self.name()} skipped the session: the opening move {move:+.2%} "
                f"is inside the {self.rules.noise_multiple * band:.2%} noise band",
            )
            return None, band
        asset = long_asset if move > 0 else Asset.from_symbol(self.rules.short_symbol)
        self.portfolio.record(
            self,
            f"signal.read.{day}",
            "info",
            f"{self.name()} follows the opening move {move:+.2%} into {asset}",
        )
        return asset, band


class IntradayMim(Intraday):
    key = "intraday_mim"
    code = "i"
    rules: ClassVar[IntradayMimSection] = settings.intraday_mim
    holdings_max = rules.holdings_max
    is_paused = rules.is_paused
