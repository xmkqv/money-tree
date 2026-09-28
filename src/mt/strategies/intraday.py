from datetime import date, datetime, timedelta
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.data.asset import Asset
from mt.exchange import TRADING_ZONE, session_starts
from mt.frames import regular_session

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
    long_symbol: ClassVar[str]
    short_symbol: ClassVar[str]
    first_minutes: ClassVar[int]
    entry_minutes_before_close: ClassVar[int]
    close_lead_minutes: ClassVar[int]
    noise_sessions: ClassVar[int]
    noise_multiple: ClassVar[float]
    stop_band_multiple: ClassVar[float]
    lookback_days: ClassVar[int]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._signal: tuple[date, Asset | None, float] | None = None

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return (
            max(opens, closes - timedelta(minutes=cls.entry_minutes_before_close)),
            closes - timedelta(minutes=cls.close_lead_minutes),
        )

    def run(self, session: Session) -> None:
        now = session.now
        start, until = self.entry_window(session.opens, session.closes)
        if not start <= now < until:
            return
        if self._signal is None or self._signal[0] != now.date():
            self._signal = self._read_signal(now)
        if self._signal is None:
            return
        day, asset, band = self._signal
        if asset is None or self.is_capped(now) or self.portfolio.is_taken(self, asset, day):
            return
        price = self.price(asset)
        if price is None:
            return
        stop = price * (1 - self.stop_band_multiple * band)
        self.portfolio.enter(self, Candidate(asset, price, stop), session)

    def manage(self, holding: Holding, session: Session) -> None:
        if session.now >= session.closes - timedelta(minutes=self.close_lead_minutes):
            self.portfolio.exit(holding, "close")

    def _read_signal(self, now: datetime) -> tuple[date, Asset | None, float] | None:
        day = now.date()
        long_asset = Asset.from_symbol(self.long_symbol)
        frame = self.portfolio.minute_frames(
            [long_asset], now - timedelta(days=self.lookback_days), now, self.first_minutes
        ).get(long_asset)
        moves = Series(dtype=float) if frame is None else opening_moves(frame)
        today = Timestamp(day, tz=TRADING_ZONE)
        history = cast("Series[float]", moves[cast(Any, moves.index) < today]).tail(
            self.noise_sessions
        )
        if today not in moves.index or len(history) < self.noise_sessions:
            self.portfolio.record(
                self,
                f"signal.unread.{day}",
                "warning",
                f"{self.name()} has no signal yet: {self.long_symbol} lacks "
                f"{self.noise_sessions} sessions of opening moves",
            )
            return None
        move = float(cast(float, moves[today]))
        band = float(cast(Any, history).abs().mean())
        if move == 0 or abs(move) < self.noise_multiple * band:
            self.portfolio.record(
                self,
                f"signal.quiet.{day}",
                "info",
                f"{self.name()} skipped the session: the opening move {move:+.2%} "
                f"is inside the {self.noise_multiple * band:.2%} noise band",
            )
            return day, None, band
        asset = long_asset if move > 0 else Asset.from_symbol(self.short_symbol)
        self.portfolio.record(
            self,
            f"signal.read.{day}",
            "info",
            f"{self.name()} follows the opening move {move:+.2%} into {asset}",
        )
        return day, asset, band


class IntradayMim(Intraday):
    key = "intraday_mim"
    code = "i"
