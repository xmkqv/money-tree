from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import isfinite
from typing import Any, ClassVar, cast

from pandas import DataFrame, DatetimeIndex, Series, Timestamp

from bot.config import settings
from bot.exchange import TRADING_ZONE
from bot.frames import frame_between, frame_since, frame_until, regular_session
from bot.indicators import latest_atr, latest_dollar_volume
from bot.sizing import next_stop
from bot.types import Direction, StrategyName
from bot.universe import UNIVERSE, millions, percent

from .base import Candidate, Holding, Ladder, Portfolio, Rule, Session, Strategy, ranked


@dataclass(frozen=True, slots=True)
class RangeMarks:
    high: float
    mid: float
    low: float


@dataclass(frozen=True, slots=True)
class SessionVolume:
    ratio: float
    turnover: float


@dataclass(frozen=True, slots=True)
class Break:
    symbol: str
    direction: Direction
    high: float
    low: float
    close: float
    at: Timestamp


def range_level(high: float, low: float, fraction: float) -> float:
    return low + (high - low) * fraction


def range_marks(high: float, low: float) -> RangeMarks:
    return RangeMarks(high, range_level(high, low, settings.breakout.mid_fraction), low)


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
    if direction is None or close < settings.universe.price_usd_min:
        return False
    if high - low < settings.breakout.range_fraction_min * close:
        return False
    fraction = abs(close - range_stop(direction, high, low)) / close
    return settings.breakout.stop_fraction_min <= fraction <= settings.breakout.stop_fraction_max


def session_volume(frame: DataFrame, day: date, clock: time) -> SessionVolume | None:
    sessions = settings.breakout.history_sessions
    regular = regular_session(frame)
    index = cast(DatetimeIndex, regular.index)
    pandas_index = cast(Any, index)
    session_dates = cast(DatetimeIndex, pandas_index.normalize())
    current_session = Timestamp(day, tz=TRADING_ZONE)
    volume = regular["volume"]
    aggregates = DataFrame(
        {
            "session_date": session_dates,
            "daily_turnover": volume * regular["close"],
            "cumulative_volume": cast(
                Series,
                cast(Any, volume).where(pandas_index.time <= clock, 0.0),
            ),
        },
        index=index,
    )
    columns = ["daily_turnover", "cumulative_volume"]
    relevant = cast(Any, session_dates) <= current_session
    grouped = cast(
        DataFrame,
        cast(Any, aggregates).loc[relevant].groupby("session_date", sort=True)[columns].sum(),
    )
    if current_session not in grouped.index:
        return None
    grouped_index = cast(Any, cast(DatetimeIndex, grouped.index))
    history = cast(
        DataFrame,
        cast(Any, grouped).loc[grouped_index < current_session].tail(sessions),
    )
    if len(history) != sessions:
        return None
    clock_average = float(cast(Any, history["cumulative_volume"]).mean())
    turnover = float(cast(Any, history["daily_turnover"]).mean())
    current = float(cast(Any, grouped).loc[current_session, "cumulative_volume"])
    if not all(isfinite(value) for value in (clock_average, turnover, current)):
        return None
    if clock_average <= 0:
        return None
    return SessionVolume(current / clock_average, turnover)


def is_relative_volume_ready(frame: DataFrame, day: date, clock: time, multiple: float) -> bool:
    if frame.empty:
        return False
    volume = session_volume(frame, day, clock)
    if volume is None:
        return False
    return volume.turnover >= settings.universe.turnover_usd_min and volume.ratio >= multiple


class Breakout(Strategy):
    family = "breakout"
    kind = "Intraday breakout"
    is_stop_resting = True
    positions_max = settings.breakout.positions_max
    opening_minutes: ClassVar[int]
    volume_multiple: ClassVar[float]
    target_multiples: ClassVar[tuple[float, float, float]]
    entry_extension_max: ClassVar[float | None]

    def __init__(self, portfolio: Portfolio) -> None:
        super().__init__(portfolio)
        self._scanned: set[str] = set()
        self._data_failed_on: date | None = None

    @classmethod
    def cap_keys(cls) -> frozenset[StrategyName]:
        from .registry import family_keys

        return family_keys(cls.family)

    @classmethod
    def entry_window(cls, opens: datetime, closes: datetime) -> tuple[datetime, datetime]:
        return (
            opens + timedelta(minutes=cls.opening_minutes),
            opens + timedelta(minutes=settings.breakout.scan_minutes),
        )

    @classmethod
    def target_prices(
        cls, entry: float, stop: float, direction: Direction
    ) -> tuple[float, float, float]:
        risk = abs(entry - stop)
        first, second, third = cls.target_multiples
        return (
            entry + direction * risk * first,
            entry + direction * risk * second,
            entry + direction * risk * third,
        )

    def begin(self, day: date) -> None:
        self._scanned.clear()

    def ladder(self, holding: Holding, original: float, remaining: float) -> Ladder | None:
        fraction = remaining / original if original else 1.0
        stage = 0 if fraction > 0.5 else 1 if fraction > 0.25 else 2
        targets = self.target_prices(holding.entry, holding.stop, holding.direction)
        return Ladder(original, targets, stage)

    def run(self, session: Session) -> None:
        now = session.now
        opening_end, scan_end = self.entry_window(session.opens, session.closes)
        if now.minute % self.opening_minutes or not opening_end <= now <= scan_end:
            return
        if not self.portfolio.eligible_symbols():
            return
        if self.is_capped():
            self.portfolio.record(
                self,
                f"entries.capped.{now.date()}",
                "info",
                f"Breakout entries paused: {self.positions_max} positions already open",
            )
            return
        symbols = self._unscanned(now.date())
        if not symbols or self._data_failed_on == now.date():
            return
        try:
            frames = self.portfolio.minute_frames(symbols, session.opens, now, self.opening_minutes)
        except Exception as error:
            self._stand_down(now.date(), error)
            return
        breaks = self._breaks(frames, session, opening_end)
        if not breaks:
            return
        breaks = ranked(
            breaks,
            symbol=lambda found: found.symbol,
            turnover=lambda found: self._turnover(found.symbol, now),
        )
        try:
            histories = self.portfolio.minute_frames(
                [found.symbol for found in breaks],
                now - timedelta(days=settings.breakout.confirm_history_days),
                now,
                self.opening_minutes,
            )
        except Exception as error:
            self._stand_down(now.date(), error)
            return
        for found in breaks:
            if self.is_capped():
                return
            frame = histories.get(found.symbol)
            if frame is None:
                continue
            if not self.is_confirmed(frame_until(frame, found.at), now):
                continue
            price = self._price(found)
            if self.is_overextended(found, price):
                self.portfolio.record(
                    self,
                    f"entry.overextended.{found.symbol}.{now.date()}",
                    "warning",
                    f"{found.symbol} entry skipped: price is more than "
                    f"{self.entry_extension_max:g} of the opening range beyond the "
                    "breakout level",
                )
                continue
            stop = range_stop(found.direction, found.high, found.low)
            self.portfolio.enter(
                self, Candidate(found.symbol, price, stop, found.direction), session
            )

    def manage(self, holding: Holding, session: Session) -> None:
        now = session.now
        if now >= session.closes - timedelta(minutes=settings.breakout.close_lead_minutes):
            self.portfolio.exit(holding)
            return
        price = self.portfolio.last_price(holding.symbol)
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
            if ladder.stage == 0:
                quantity = ladder.original_quantity * 0.5
            elif ladder.stage == 1:
                quantity = ladder.original_quantity * 0.25
            else:
                self.portfolio.exit(holding)
                return
            ladder.stage += 1
            self.portfolio.exit(holding, quantity)
            return
        if ladder.stage == 0:
            return
        try:
            recent = self.portfolio.minute_frames(
                [holding.symbol],
                now - timedelta(days=settings.breakout.trail_history_days),
                now,
                self.opening_minutes,
            ).get(holding.symbol)
        except Exception as error:
            self.portfolio.record(
                self,
                f"trail.stalled.{holding.symbol}.{now.date()}",
                "warning",
                f"{holding.symbol} trailing stop not updated: {type(error).__name__}",
            )
            return
        if recent is None:
            return
        frame = regular_session(recent)
        if len(frame) < settings.breakout.trail_bars_min:
            return
        trail = settings.breakout.trail_atr_multiple * latest_atr(frame)
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
        return is_relative_volume_ready(
            frame,
            now.date(),
            cast(Timestamp, frame.index[-1]).time(),
            self.volume_multiple,
        )

    def is_overextended(self, found: Break, price: float) -> bool:
        limit = self.entry_extension_max
        if limit is None:
            return False
        span = found.high - found.low
        if found.direction == 1:
            return price > found.high + limit * span
        return price < found.low - limit * span

    def _unscanned(self, day: date) -> list[str]:
        return [
            symbol
            for symbol in self.portfolio.eligible_symbols()
            if symbol not in self._scanned and not self.portfolio.is_taken(self, symbol, day)
        ]

    def _turnover(self, symbol: str, now: datetime) -> float:
        frame = self.portfolio.daily_frame(symbol, now)
        return 0.0 if frame is None else latest_dollar_volume(frame)

    def _price(self, found: Break) -> float:
        price = self.portfolio.last_price(found.symbol)
        return price if isfinite(price) and price > 0 else found.close

    def _stand_down(self, day: date, error: Exception) -> None:
        self._data_failed_on = day
        detail = f"{type(error).__name__}: {error}"
        self.portfolio.record(
            self,
            f"scan.unavailable.{day}",
            "error",
            f"Breakout scan stood down for the day: no intraday bars ({detail[:200]})",
        )

    def _breaks(
        self, frames: dict[str, DataFrame], session: Session, opening_end: datetime
    ) -> list[Break]:
        breaks: list[Break] = []
        for symbol, frame in frames.items():
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
            signal = self._signal(after, high, low)
            if signal is None:
                continue
            position, direction, close = signal
            self._scanned.add(symbol)
            if not is_setup_ready(high, low, close):
                continue
            if len(after) - position > settings.breakout.signal_candles_max:
                continue
            breaks.append(
                Break(symbol, direction, high, low, close, cast(Timestamp, after.index[position]))
            )
        return breaks

    def _signal(
        self, candles: DataFrame, high: float, low: float
    ) -> tuple[int, Direction, float] | None:
        for position, value in enumerate(candles["close"].tolist()):
            close = float(value)
            if not isfinite(close):
                continue
            if close > high:
                return position, 1, close
            if close < low:
                return position, -1, close
        return None

    @classmethod
    def describe(cls, per_trade: float, opens: datetime, closes: datetime) -> list[Rule]:
        breakout = settings.breakout
        period = settings.indicators.period
        minutes = cls.opening_minutes
        risk_cap = per_trade if cls.risk_fraction_max is None else cls.risk_fraction_max
        opening_end = f"{opens + timedelta(minutes=minutes):%H:%M}"
        first_entry = f"{opens + timedelta(minutes=2 * minutes):%H:%M}"
        scan_end = f"{opens + timedelta(minutes=breakout.scan_minutes):%H:%M}"
        exit_at = f"{closes - timedelta(minutes=breakout.close_lead_minutes):%H:%M}"
        exit_before = f"{closes - timedelta(minutes=breakout.close_lead_minutes - 1):%H:%M}"

        confirmation = (
            f"Volume traded up to the signal candle's close is at least "
            f"{cls.volume_multiple:g}x the "
            f"{breakout.history_sessions}-session average at the same time of day, and that "
            f"average session turns over at least {millions(settings.universe.turnover_usd_min)}. "
            f"All {breakout.history_sessions} earlier sessions must be available to compare "
            "against. "
            "If fewer are available there is no confirmation, and the breakout is passed over. "
            "The reading is taken at the signal candle's close rather than at the moment the "
            "scan runs, so a breakout found a pass late is still confirmed on the volume that "
            "made it. Each session is measured between its own opening and closing bell, so a "
            "half day is compared as a half day."
        )

        first, second, third = cls.target_multiples
        multiples = f"{first:g}x, {second:g}x and {third:g}x"
        reward = f"{first:g}:1 at the first target, then {second:g}:1 and {third:g}:1."
        targets = (
            f"Targets are re-cut from the filled price: {multiples} the risk actually taken. A "
            "fill away from the signal price moves the targets with it."
        )

        extension = (
            ""
            if cls.entry_extension_max is None
            else f" It is also passed over if that live quote sits more than "
            f"{percent(cls.entry_extension_max)} of the opening range beyond the breakout "
            "level. The stop "
            "is a fixed distance inside the range, so a price further past the level risks more "
            "and leaves less of the move to collect."
        )

        return [
            Rule(field="Market", value=UNIVERSE, source="portfolio.py · _eligible_symbols"),
            Rule(
                field="Sentiment",
                value="None. This strategy takes signals whatever the wider market is doing.",
                source="strategies/breakout.py · run",
            ),
            Rule(
                field="Direction",
                value="Long and short. A short is skipped when the broker will not lend the "
                "stock. A short is sized in whole shares, because a broker lends whole shares "
                "only, so every order on a short leg is rounded down to a whole number. Longs "
                "use fractional quantities when the account allows them.",
                source="portfolio.py · enter, protect, exit",
            ),
            Rule(
                field="Range",
                value=f"The opening range is the first {minutes}-minute candle, from the "
                f"opening bell to {opening_end}. The last trade before {opening_end} closes "
                "it. Its high "
                "and low set the levels for the day. The bell is read from the exchange "
                "calendar, so a late open moves the range with it.",
                source="strategies/breakout.py · run, exchange.py · session_bounds",
            ),
            Rule(
                field="Setup",
                value=f"The first completed {minutes}-minute candle since the range that closes "
                "above the range high (long) or below the range low (short). A candle still "
                f"forming never signals. Checked every {minutes} minutes from {opening_end}, "
                f"when the opening candle closes, to {scan_end}, at most once per stock per "
                "day. Every "
                "pass re-reads the whole session since the range rather than only its newest "
                "candle, so a breakout whose bars reached the scan late still supplies the "
                "signal "
                f"candle. It must be one of the last {breakout.signal_candles_max} completed "
                f"candles, which is {breakout.signal_candles_max * minutes} minutes of the move. "
                "An older close "
                "has already run, and is passed over. Once either breakout strategy has traded "
                "a stock, both leave it alone for the rest of the session. The range itself "
                f"must be at least {percent(breakout.range_fraction_min)} of the price, and the "
                f"stop cut from it must fall between {percent(breakout.stop_fraction_min)} and "
                f"{percent(breakout.stop_fraction_max)} of the price. A narrower range puts the "
                "stop "
                "inside the spread.",
                source="strategies/breakout.py · run, is_setup_ready",
            ),
            Rule(
                field="Confirmation",
                value=confirmation,
                source="strategies/breakout.py · is_confirmed",
            ),
            Rule(
                field="Sorting",
                value="Ranked by the value traded in the last completed daily session, which is "
                "its close times its share volume, highest first. When more breakouts fire than "
                "there is room to hold, the busiest take the slots. This is a different question "
                "from the confirmation above, which measures each stock against its own history "
                "rather than against other stocks.",
                source="strategies/base.py · ranked",
            ),
            Rule(
                field="Entry",
                value="A market order goes in the moment the scan reads the breakout, and fills "
                f"at the next executable price. That is the open of the next {minutes}-minute "
                f"candle when the signal is read on its own boundary, and {first_entry} at the "
                "earliest, because the opening candle cannot break its own range. Good for the "
                "day only. The size is worked out from the live quote, and falls back to the "
                "breakout candle's close. The fill then sets the entry, the risk and the "
                "targets. "
                "The entry is passed over if another strategy already holds the stock, if the "
                "account is at its position cap or fully invested, if the size that fits the "
                "risk "
                f"limits comes to less than ${settings.risk.notional_usd_min:.0f}, or if that "
                "live quote has "
                f"already run back through the stop the breakout would have been given."
                f"{extension}",
                source="portfolio.py · on_trading_iteration, enter",
            ),
            Rule(
                field="Stop Loss",
                value=f"{percent(breakout.long_stop_fraction)} of the way back into "
                f"the opening range for a long, {percent(breakout.short_stop_fraction)} "
                "for a short. Once the first target is hit, the stop trails "
                f"{breakout.trail_atr_multiple:g}x the {period}-period ATR behind the best price "
                f"the trade has seen, and never moves back past the entry price. That "
                f"ATR({period}) "
                f"is calculated from {minutes}-minute candles across trading sessions, using "
                "prior-session bars where they are available, so overnight gaps contribute to "
                f"true range. At least {breakout.trail_bars_min} completed {minutes}-minute "
                "candles "
                "must be available. Prior sessions count towards that total, so the trade "
                "normally starts with enough. The level rests as a live order at the broker. It "
                "is replaced whenever it moves, and re-sent if it stops covering the whole "
                "position. A level the market has already reached cannot rest as an order. When "
                "the stop lands at or beyond the last price, the whole position is closed at "
                "market instead. The move to breakeven after the first target is the usual way "
                "this happens. Price back at the entry means the stop is hit, so the position "
                "leaves at market.",
                source="strategies/breakout.py · run, manage, portfolio.py · protect",
            ),
            Rule(
                field="Max Risk",
                value=f"{percent(risk_cap)} of account equity per trade"
                + (
                    ", which is the configured per-trade limit. This strategy states none "
                    "of its own."
                    if cls.risk_fraction_max is None
                    else f". This strategy states its own {percent(cls.risk_fraction_max)} in "
                    f"the spec, so that governs instead of the configured "
                    f"{percent(per_trade)}."
                )
                + f" A single position is never worth more than "
                f"{percent(settings.risk.position_fraction_max)} "
                "of equity.",
                source="portfolio.py · enter",
            ),
            Rule(
                field="Min. R:R",
                value=f"{reward} {targets}",
                source="portfolio.py · on_filled_order",
            ),
            Rule(
                field="Exit Rule",
                value="Scaled out in three: half the position as first filled at the first "
                "target, a quarter of it at the second, the remainder at the third. On a short "
                "each slice is rounded down to whole shares, and a slice worth less than a "
                "single "
                "share is skipped. The resting stop still covers the position, and the next "
                "target or the closing deadline takes it. The trailing stop takes whatever is "
                "left if price turns first.",
                source="strategies/breakout.py · manage",
            ),
            Rule(
                field="Emergency Exit",
                value=f"Everything is closed before {exit_before}. The exit is sent at "
                f"{exit_at}, "
                f"which is {breakout.close_lead_minutes} minutes before the closing bell the "
                "exchange "
                "calendar gives for the session, so the market order fills in time and a half "
                "day "
                "closes on its own clock. This strategy never holds overnight. The daily loss "
                "limit closes all positions and stops new entries for the rest of the day.",
                source="strategies/breakout.py · manage, portfolio.py · _is_daily_loss_reached",
            ),
        ]
