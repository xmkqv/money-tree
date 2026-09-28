from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.data.asset import Asset
from mt.exchange import TRADING_ZONE
from mt.frames import frame_between, frame_since, frame_until, regular_session
from mt.indicators import latest_atr, latest_turnover_usd
from mt.rules.shared import settings
from mt.rules.values import TARGET_REASONS
from mt.sizing import Direction

from .base import Candidate, Holding, Ladder, Portfolio, Session, Strategy, ranked


@dataclass(frozen=True, slots=True)
class Signal:
    asset: Asset
    direction: Direction
    high: float
    low: float
    signal_at: Timestamp


def range_level(high: float, low: float, fraction: float) -> float:
    return low + (high - low) * fraction


def range_stop(direction: Direction, high: float, low: float) -> float:
    breakout = settings.breakout
    fraction = breakout.long_stop_fraction if direction == 1 else breakout.short_stop_fraction
    return range_level(high, low, fraction)


def range_break(high: float, low: float, close: float) -> Direction | None:
    if not all(isfinite(value) for value in (high, low, close)):
        return None
    return 1 if close > high else -1 if close < low else None


def is_setup_ready(high: float, low: float, close: float) -> bool:
    direction = range_break(high, low, close)
    if direction is None:
        return False
    if high - low < settings.breakout.range_fraction_min * close:
        return False
    fraction = abs(close - range_stop(direction, high, low)) / close
    return settings.breakout.stop_fraction_min <= fraction <= settings.breakout.stop_fraction_max


def relative_volume(frame: DataFrame, day: date, clock: time) -> float | None:
    sessions = settings.breakout.lookback_sessions
    regular = regular_session(frame)
    index = cast(DatetimeIndex, regular.index)
    current = Timestamp(day, tz=TRADING_ZONE)
    to_clock = regular[(index.normalize() <= current) & (index.time <= clock)]
    daily = to_clock["volume"].groupby(cast(DatetimeIndex, to_clock.index).normalize()).sum()
    if current not in daily.index:
        return None
    history = daily.iloc[:-1].tail(sessions)
    if len(history) != sessions:
        return None
    average = float(history.mean())
    if not isfinite(average) or average <= 0:
        return None
    value = float(daily.loc[current])
    return value / average if isfinite(value) else None


class Breakout(Strategy):
    is_stop_resting = True
    opening_minutes: ClassVar[int]
    volume_multiple: ClassVar[float]
    target_multiples: ClassVar[tuple[float, float, float]]
    entry_extension_max: ClassVar[float | None]
    scan_minutes: ClassVar[int] = settings.breakout.scan_minutes

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._scanned: set[Asset] = set()

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return (
            opens + timedelta(minutes=cls.opening_minutes),
            min(closes, opens + timedelta(minutes=cls.scan_minutes)),
        )

    @classmethod
    def target_prices(
        cls, entry: float, stop: float, direction: Direction
    ) -> tuple[float, float, float]:
        stop_distance = abs(entry - stop)
        first, second, third = cls.target_multiples
        return (
            entry + direction * stop_distance * first,
            entry + direction * stop_distance * second,
            entry + direction * stop_distance * third,
        )

    def begin(self, session_on: date) -> None:
        self._scanned.clear()

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        targets = self.target_prices(holding.entry, holding.stop, holding.direction)
        return Ladder(quantity, targets)

    def run(self, session: Session) -> None:
        now = session.now
        opening_end, scan_end = self.entry_window(session.opens, session.closes)
        if now.minute % self.opening_minutes or not opening_end <= now <= scan_end:
            return
        if self.is_capped(now):
            return
        assets = self._unscanned(now.date())
        if not assets:
            return
        frames = self.portfolio.minute_frames(assets, session.opens, now, self.opening_minutes)
        signals = self._signals(frames, session, opening_end)
        if not signals:
            return
        signals = ranked(
            signals,
            symbol=lambda found: str(found.asset),
            turnover=lambda found: self._turnover(found.asset),
        )
        histories = self.portfolio.minute_frames(
            [found.asset for found in signals],
            now - timedelta(days=settings.breakout.confirm_lookback_days),
            now,
            self.opening_minutes,
        )
        for found in signals:
            if self.is_capped():
                return
            frame = histories.get(found.asset)
            if frame is None:
                continue
            if not self.is_confirmed(frame_until(frame, found.signal_at), now):
                continue
            price = self.price(found.asset)
            if price is None:
                continue
            if self.is_overextended(found, price):
                self.portfolio.record(
                    self,
                    f"entry.overextended.{found.asset}.{now.date()}",
                    "warning",
                    f"{found.asset} entry skipped: price is more than "
                    f"{self.entry_extension_max:g} times the opening range size beyond "
                    "the breakout level",
                )
                continue
            stop = range_stop(found.direction, found.high, found.low)
            self.portfolio.enter(
                self, Candidate(found.asset, price, stop, found.direction), session
            )

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if now >= session.closes - timedelta(minutes=settings.breakout.close_lead_minutes):
            self.portfolio.exit(holding, "close")
            return
        price = self.price(holding.asset)
        if price is None:
            return
        holding.highest = max(holding.highest, price)
        holding.lowest = min(holding.lowest, price)
        ladder = holding.ladder
        if ladder is None:
            return
        reached = (
            price >= ladder.targets[ladder.stage]
            if holding.direction == 1
            else price <= ladder.targets[ladder.stage]
        )
        if reached:
            fractions = settings.breakout.target_fractions
            if ladder.stage == len(fractions) - 1:
                self.portfolio.exit(holding, TARGET_REASONS[ladder.stage])
                return
            quantity, reason = ladder.step(fractions[ladder.stage], whole=holding.direction == -1)
            holding.raise_stop(holding.entry, "breakeven")
            if quantity > 0:
                self.portfolio.exit(holding, reason, float(quantity))
            self.portfolio.protect(holding)
            return
        if ladder.stage == 0:
            return
        holding.raise_stop(self._trailed_stop(holding, now), "trail")
        self.portfolio.protect(holding)

    def _trailed_stop(self, holding: Holding, now: datetime) -> float:
        recent = self.portfolio.minute_frames(
            [holding.asset],
            now - timedelta(days=settings.breakout.trail_lookback_days),
            now,
            self.opening_minutes,
        ).get(holding.asset)
        frame = None if recent is None else regular_session(recent)
        if frame is None or len(frame) < settings.breakout.trail_bars_min:
            return holding.entry
        trail = settings.breakout.trail_atr_multiple * latest_atr(frame, settings.indicators.period)
        if holding.direction == 1:
            return max(holding.entry, holding.highest - trail)
        return min(holding.entry, holding.lowest + trail)

    def is_confirmed(self, frame: DataFrame, now: datetime) -> bool:
        if frame.empty:
            return False
        clock = cast(Timestamp, frame.index[-1]).time()
        ratio = relative_volume(frame, now.date(), clock)
        return ratio is not None and ratio >= self.volume_multiple

    def is_overextended(self, found: Signal, price: float) -> bool:
        limit = self.entry_extension_max
        if limit is None:
            return False
        span = found.high - found.low
        if found.direction == 1:
            return price > found.high + limit * span
        return price < found.low - limit * span

    def _unscanned(self, day: date) -> list[Asset]:
        return [
            asset
            for asset in self.portfolio.assets()
            if asset not in self._scanned and not self.portfolio.is_taken(self, asset, day)
        ]

    def _turnover(self, asset: Asset) -> float:
        frame = self.portfolio.daily_frame(asset)
        return 0.0 if frame is None else latest_turnover_usd(frame)

    def _signals(
        self, frames: dict[Asset, DataFrame], session: Session, opening_end: datetime
    ) -> list[Signal]:
        signals: list[Signal] = []
        for asset, frame in frames.items():
            if frame.empty:
                continue
            opening = frame_between(frame, session.opens, opening_end)
            after = frame_since(frame, opening_end)
            if opening.empty or after.empty:
                continue
            high = float(cast(Any, opening["high"]).max())
            low = float(cast(Any, opening["low"]).min())
            if not all(isfinite(value) for value in (high, low)):
                continue
            found = self._first_break(after, high, low)
            if found is None:
                continue
            index, direction, close = found
            self._scanned.add(asset)
            if not is_setup_ready(high, low, close):
                continue
            if len(after) - index > settings.breakout.signal_bars_max:
                continue
            signals.append(Signal(asset, direction, high, low, cast(Timestamp, after.index[index])))
        return signals

    def _first_break(
        self, bars: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
        close = bars["close"]
        above = cast(Series, close > high)
        below = cast(Series, close < low)
        hit = above | below
        if not hit.any():
            return None
        index = int(hit.to_numpy().argmax())
        direction: Direction = 1 if above.iloc[index] else -1
        return index, direction, float(close.iloc[index])


class Breakout5m(Breakout):
    key = "breakout_5m"
    code = "o"


class Breakout10m(Breakout):
    key = "breakout_10m"
    code = "m"


class Breakout15m(Breakout):
    key = "breakout_15m"
    code = "f"
