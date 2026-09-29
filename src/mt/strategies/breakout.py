from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import ClassVar

from pandas import DataFrame, DatetimeIndex, Timestamp

from mt.data.asset import Asset
from mt.exchange import TRADING_ZONE
from mt.frames import ranked, regular_session
from mt.indicators import latest_turnover_usd
from mt.rules.sections import BreakoutSection, BreakoutVariationSection
from mt.rules.shared import settings
from mt.sizing import Direction

from .base import Candidate, Holding, Ladder, Portfolio, Session, Strategy, trail_distance


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


def is_setup_ready(direction: Direction, high: float, low: float, close: float) -> bool:
    if high - low < settings.breakout.range_fraction_min * close:
        return False
    fraction = abs(close - range_stop(direction, high, low)) / close
    return settings.breakout.stop_fraction_min <= fraction <= settings.breakout.stop_fraction_max


def relative_volume(frame: DataFrame, session_on: date, clock: time) -> float | None:
    sessions = settings.breakout.lookback_sessions
    regular = regular_session(frame)
    index = DatetimeIndex(regular.index)
    stamps = index.normalize()
    current = Timestamp(session_on, tz=TRADING_ZONE)
    keep = (stamps <= current) & (index.time <= clock)
    daily = regular["volume"][keep].groupby(stamps[keep]).sum()
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
    rules: ClassVar[BreakoutVariationSection]  # pyright: ignore[reportIncompatibleVariableOverride]
    family_rules: ClassVar[BreakoutSection] = settings.breakout

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._scanned: set[Asset] = set()

    @classmethod
    def entry_window(cls, opens_at: datetime, closes_at: datetime) -> tuple[datetime, datetime]:
        return (
            opens_at + timedelta(minutes=cls.rules.opening_minutes),
            min(closes_at, opens_at + timedelta(minutes=cls.family_rules.scan_minutes)),
        )

    @classmethod
    def target_prices(cls, entry: float, stop: float, direction: Direction) -> tuple[float, ...]:
        return cls._targets(entry, abs(entry - stop), direction)

    def begin(self, session: Session) -> None:
        self._scanned.clear()

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        targets = self._targets(holding.entry, holding.stop_distance, holding.direction)
        return Ladder(quantity, targets, self.family_rules.target_fractions)

    def run(self, session: Session) -> None:
        now = session.now
        opening_end_at, _ = self.entry_window(session.opens_at, session.closes_at)
        if now.minute % self.rules.opening_minutes:
            return
        if self.is_capped(session):
            return
        assets = self._unscanned()
        if not assets:
            return
        frames = self.portfolio.frames(assets, session.opens_at, now, self.rules.opening_minutes)
        signals = self._signals(frames, session, opening_end_at)
        if not signals:
            return
        signals = ranked(
            signals,
            symbol=lambda found: str(found.asset),
            score=lambda found: self._turnover(found.asset),
        )
        histories = self.portfolio.frames(
            [found.asset for found in signals],
            now - timedelta(days=self.family_rules.confirm_lookback_days),
            now,
            self.rules.opening_minutes,
        )
        for found in signals:
            if self.is_capped(session):
                return
            frame = histories.get(found.asset)
            if frame is None:
                continue
            if not self._is_confirmed(frame.loc[: found.signal_at], now):
                continue
            price = self.portfolio.quote(found.asset)
            if price is None:
                continue
            if self._is_overextended(found, price):
                self.portfolio.record(
                    self,
                    f"entry.overextended.{found.asset}.{now.date()}",
                    "warning",
                    f"{found.asset} entry skipped: price is more than "
                    f"{self.rules.entry_extension_max:g} times the opening range size beyond "
                    "the breakout level",
                )
                continue
            stop = range_stop(found.direction, found.high, found.low)
            self.portfolio.enter(
                self, Candidate(found.asset, price, stop, found.direction), session
            )

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if now >= session.closes_at - timedelta(minutes=self.family_rules.close_lead_minutes):
            self.portfolio.exit(holding, "close")
            return
        price = self.portfolio.quote(holding.asset)
        if price is None:
            return
        holding.mark(price)
        ladder = holding.ladder
        if ladder is None:
            return
        take = ladder.try_take(price, holding.direction)
        if take is not None:
            reason, shares = take
            if shares is not None:
                holding.tighten_stop(holding.entry, "breakeven")
                if holding.breakeven_at is None:
                    holding.breakeven_at = now
            self.portfolio.exit(holding, reason, shares)
            return
        if ladder.stage == 0:
            return
        stop = self._trailed_stop(holding, now)
        if stop is not None:
            holding.tighten_stop(stop, "trail")
        self.portfolio.protect(holding)

    @classmethod
    def _targets(
        cls, entry: float, stop_distance: float, direction: Direction
    ) -> tuple[float, ...]:
        return tuple(
            entry + direction * stop_distance * multiple for multiple in cls.rules.target_multiples
        )

    def _trailed_stop(self, holding: Holding, now_at: datetime) -> float | None:
        recent = self.portfolio.frames(
            [holding.asset],
            now_at - timedelta(days=self.family_rules.trail_lookback_days),
            now_at,
            self.rules.opening_minutes,
        ).get(holding.asset)
        if recent is None or holding.breakeven_at is None:
            return None
        frame = regular_session(recent)
        if len(frame.loc[holding.breakeven_at :]) < self.family_rules.trail_bars_min:
            return None
        distance = trail_distance(
            frame, self.family_rules.trail_atr_multiple, settings.indicators.period_bars
        )
        if distance is None:
            return None
        anchor = holding.highest if holding.direction == 1 else holding.lowest
        return anchor - holding.direction * distance

    def _is_confirmed(self, frame: DataFrame, now: datetime) -> bool:
        if frame.empty:
            return False
        clock = frame.index[-1].time()
        ratio = relative_volume(frame, now.date(), clock)
        return ratio is not None and ratio >= self.rules.volume_multiple

    def _is_overextended(self, found: Signal, price: float) -> bool:
        limit = self.rules.entry_extension_max
        if limit is None:
            return False
        span = found.high - found.low
        if found.direction == 1:
            return price > found.high + limit * span
        return price < found.low - limit * span

    def _unscanned(self) -> list[Asset]:
        return [
            asset
            for asset in self.portfolio.assets()
            if asset not in self._scanned and not self.portfolio.is_taken(self, asset)
        ]

    def _turnover(self, asset: Asset) -> float:
        frame = self.portfolio.get_daily_frame(asset)
        return 0.0 if frame is None else latest_turnover_usd(frame)

    def _signals(
        self, frames: dict[Asset, DataFrame], session: Session, opening_end_at: datetime
    ) -> list[Signal]:
        signals: list[Signal] = []
        for asset, frame in frames.items():
            if frame.empty:
                continue
            index = DatetimeIndex(frame.index)
            inside = (index >= Timestamp(session.opens_at)) & (index < Timestamp(opening_end_at))
            opening = frame[inside]
            after = frame.loc[opening_end_at:]
            if opening.empty or after.empty:
                continue
            high = float(opening["high"].max())
            low = float(opening["low"].min())
            found = _first_break(after, high, low)
            if found is None:
                continue
            position, direction, close = found
            self._scanned.add(asset)
            if not is_setup_ready(direction, high, low, close):
                continue
            if len(after) - position > self.family_rules.signal_bars_max:
                continue
            signals.append(Signal(asset, direction, high, low, after.index[position]))
        return signals


class Breakout5m(Breakout):
    key = "breakout_5m"
    code = "o"
    rules = settings.breakout_5m


class Breakout10m(Breakout):
    key = "breakout_10m"
    code = "m"
    rules = settings.breakout_10m


class Breakout15m(Breakout):
    key = "breakout_15m"
    code = "f"
    rules = settings.breakout_15m


def _first_break(bars: DataFrame, high: float, low: float) -> tuple[int, Direction, float] | None:
    close = bars["close"]
    above = close > high
    below = close < low
    hit = above | below
    if not hit.any():
        return None
    index = int(hit.argmax())
    direction: Direction = 1 if above.iloc[index] else -1
    return index, direction, float(close.iloc[index])
