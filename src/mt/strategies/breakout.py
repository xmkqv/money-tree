from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from mt.data.asset import Asset
from mt.exchange import TRADING_ZONE
from mt.frames import frame_between, frame_since, frame_until, regular_session
from mt.indicators import latest_atr, latest_turnover_usd
from mt.rules.shared import settings
from mt.rules.values import StrategyKey
from mt.sizing import Direction, next_stop, round_quantity

from .base import Candidate, Holding, Ladder, Portfolio, Session, Strategy, family_keys, ranked


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
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
    volume = regular["volume"]
    aggregates = DataFrame(
        {
            "session_date": session_dates,
            "cumulative_volume": cast(
                Series,
                cast(Any, volume).where(pandas_index.time <= clock, 0.0),
            ),
        },
        index=index,
    )
    columns = ["cumulative_volume"]
    relevant = cast(Any, session_dates) <= current_session
    grouped = cast(
        DataFrame,
        cast(Any, aggregates).loc[relevant].groupby("session_date", sort=True)[columns].sum(),
    )
    if current_session not in grouped.index:
        return None
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    volumes = cast(
        DataFrame,
        cast(Any, grouped).loc[grouped_index < current_session].tail(sessions),
    )
    if len(volumes) != sessions:
        return None
    clock_average = float(cast(Any, volumes["cumulative_volume"]).mean())
    current = float(cast(Any, grouped).loc[current_session, "cumulative_volume"])
    if not all(isfinite(value) for value in (clock_average, current)):
        return None
    if clock_average <= 0:
        return None
    return current / clock_average


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
    def cap_keys(cls) -> frozenset[StrategyKey]:
        return family_keys(cls.family)

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

    def begin(self, day: date) -> None:
        self._scanned.clear()

    def ladder(self, holding: Holding, quantity: float) -> Ladder | None:
        targets = self.target_prices(holding.entry, holding.stop, holding.direction)
        return Ladder(quantity, targets)

    def run(self, session: Session) -> None:
        now = session.now
        opening_end, scan_end = self.entry_window(session.opens, session.closes)
        if now.minute % self.opening_minutes or not opening_end <= now <= scan_end:
            return
        if self.is_capped():
            self.portfolio.record(
                self,
                f"entries.capped.{now.date()}",
                "info",
                f"{self.family.capitalize()} entries paused: "
                f"{self.holdings_max} holdings already open",
            )
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
            price = self._price(found)
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
            self.portfolio.exit(holding)
            return
        price = self.portfolio.last_price(holding.asset)
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
                self.portfolio.exit(holding)
                return
            quantity = round_quantity(
                Decimal(str(ladder.original_quantity)) * Decimal(str(fractions[ladder.stage])),
                whole=holding.direction == -1,
            )
            ladder.stage += 1
            holding.stop = next_stop(holding.direction, holding.stop, holding.entry)
            if quantity > 0:
                self.portfolio.exit(holding, float(quantity))
            self.portfolio.protect(holding)
            return
        if ladder.stage == 0:
            return
        holding.stop = next_stop(holding.direction, holding.stop, holding.entry)
        self.portfolio.protect(holding)
        recent = self.portfolio.minute_frames(
            [holding.asset],
            now - timedelta(days=settings.breakout.trail_lookback_days),
            now,
            self.opening_minutes,
        ).get(holding.asset)
        if recent is None:
            return
        frame = regular_session(recent)
        if len(frame) < settings.breakout.trail_bars_min:
            return
        trail = settings.breakout.trail_atr_multiple * latest_atr(frame, settings.indicators.period)
        candidate = (
            max(holding.entry, holding.highest - trail)
            if holding.direction == 1
            else min(holding.entry, holding.lowest + trail)
        )
        holding.stop = next_stop(holding.direction, holding.stop, candidate)
        self.portfolio.protect(holding)

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

    def _price(self, found: Signal) -> float:
        price = self.portfolio.last_price(found.asset)
        if not isfinite(price) or price <= 0:
            raise ValueError(f"current price for {found.asset} must be finite and positive")
        return price

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
        for index, value in enumerate(bars["close"].tolist()):
            close = float(value)
            direction = range_break(high, low, close)
            if direction is not None:
                return index, direction, close
        return None


class Breakout5m(Breakout):
    key = "breakout_5m"
    code = "o"


class Breakout10m(Breakout):
    key = "breakout_10m"
    code = "m"
