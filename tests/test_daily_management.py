"""Replay the daily engines' position management against a built price history.

The trailing stop is the rule that decides when a daily trade dies, and it is
the one that reads the widest slice of state, so it is exercised here against a
real frame and real indicators rather than asserted from the source text.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from pandas import DataFrame, DatetimeIndex, Series

from bot import portfolio
from bot.portfolio import Holding, OrbCandidate, Strategy
from bot.strategies import daily, shared, sma, tfb_50
from bot.strategies.shared import TRADING_ZONE, average_dollar_volume, normalize_ohlcv
from bot.strategies.tfb_50 import (
    TFB_POSITIONS_MAX,
    TFB_PRICE_MIN,
    TFB_TURNOVER_MIN,
    TFB_TURNOVER_SESSIONS,
    tfb_market_ready,
)


NOW = datetime(2025, 1, 2, 9, 31, tzinfo=UTC).astimezone(TRADING_ZONE)


def price_history() -> DataFrame:
    """A stock that topped out months ago, sold off, and is climbing again.

    The distant high is the point: a stop anchored to it instead of to the
    trade's own entry sits far above the current price.
    """
    closes = (
        [100.0 + offset for offset in range(100)]  # up to 199, the old high
        + [199.0 - offset for offset in range(80)]  # back down to 120
        + [120.0 + offset * 0.5 for offset in range(80)]  # recovering to 159.5
    )
    index = DatetimeIndex(
        [
            NOW.astimezone(UTC) - timedelta(days=len(closes) - offset)
            for offset in range(len(closes))
        ]
    )
    return normalize_ohlcv(
        DataFrame(
            {
                "open": [value - 0.3 for value in closes],
                "high": [value + 0.9 for value in closes],
                "low": [value - 0.9 for value in closes],
                "close": closes,
                "volume": [1_000_000.0] * len(closes),
            },
            index=index,
        ),
        {"high", "low", "close", "volume"},
    )


class FakeStrategy(Strategy):
    """A composer with the broker removed, so _manage_daily can be replayed."""

    def __init__(self, frame: DataFrame) -> None:  # noqa: D107 - bypasses StrategyBase.__init__
        self._daily_frames = {"AAA": frame}
        self._eligible_symbols = ["AAA"]
        self._events = set()
        self.exporter = None
        self.exited: list[Holding] = []

    def _exit(self, holding: Holding, quantity: float | None = None) -> None:
        self.exited.append(holding)


def holding(entered_at: datetime, entry: float, highest: float | None = None) -> Holding:
    return Holding(
        engine="sma",
        signal="AAA",
        asset="AAA",
        entry=entry,
        stop=entry - 5.0,
        risk=5.0,
        highest=entry if highest is None else highest,
        entered_at=entered_at.astimezone(UTC),
    )


@pytest.fixture(autouse=True)
def _no_earnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portfolio, "earnings_exit_due", lambda symbol, day: False)


def test_a_position_opened_today_is_not_stopped_out_by_a_high_set_months_ago() -> None:
    frame = price_history()
    strategy = FakeStrategy(frame)
    open_today = holding(NOW, entry=float(frame["close"].iloc[-1]))

    strategy._manage_daily(open_today, NOW)

    assert strategy.exited == [], "the entry-day stop trailed a high the trade never saw"
    assert open_today.highest == pytest.approx(float(frame["close"].iloc[-1]))
    assert open_today.stop < float(frame["close"].iloc[-1])


def test_the_stop_trails_the_highest_close_made_since_entry() -> None:
    frame = price_history()
    strategy = FakeStrategy(frame)
    entered = NOW - timedelta(days=10)
    since = frame[frame.index >= entered.astimezone(TRADING_ZONE)]
    held = holding(entered, entry=float(since["close"].iloc[0]) - 5.0)

    strategy._manage_daily(held, NOW)

    assert held.highest == pytest.approx(float(since["close"].max()))
    assert strategy.exited == []


def test_a_close_below_the_trailing_stop_exits() -> None:
    frame = price_history()
    strategy = FakeStrategy(frame)
    held = holding(NOW - timedelta(days=10), entry=100.0, highest=400.0)

    strategy._manage_daily(held, NOW)

    assert strategy.exited == [held]


def session_frame(volume: float, price_scale: float = 1.0) -> DataFrame:
    """One symbol's history, with the last completed session's tape set."""
    frame = price_history().copy(deep=True)
    for column in ("open", "high", "low", "close"):
        frame[column] = frame[column] * price_scale
    frame.iloc[-1, frame.columns.get_loc("volume")] = volume
    return frame


def ranked(frames: dict[str, DataFrame]) -> list[str]:
    strategy = FakeStrategy(price_history())
    strategy._daily_frames = frames
    strategy._eligible_symbols = sorted(frames)
    return [symbol for symbol, _ in strategy._ranked(NOW)]


def test_candidates_are_taken_by_traded_value_not_alphabetically() -> None:
    """The position cap decides who misses out, so the order has to mean something."""
    order = ranked(
        {
            "AAA": session_frame(1_000_000.0),
            "MMM": session_frame(9_000_000.0),
            "ZZZ": session_frame(4_000_000.0),
        }
    )

    assert order == ["MMM", "ZZZ", "AAA"]


def test_a_higher_priced_name_outranks_a_busier_but_cheaper_one() -> None:
    """The slots are a money cap, so share count on its own is the wrong measure."""
    cheap = session_frame(5_000_000.0, price_scale=0.1)
    dear = session_frame(1_000_000.0, price_scale=1.0)

    assert float(cheap["close"].iloc[-1]) < float(dear["close"].iloc[-1])
    assert ranked({"AAA": cheap, "ZZZ": dear}) == ["ZZZ", "AAA"]


def test_a_symbol_with_an_unreadable_session_ranks_last_but_still_trades() -> None:
    order = ranked(
        {
            "AAA": price_history().drop(columns=["volume"]),
            "ZZZ": session_frame(2_000_000.0),
        }
    )

    assert order == ["ZZZ", "AAA"]


def test_ranking_breaks_ties_on_the_symbol_so_the_order_is_stable() -> None:
    order = ranked({name: session_frame(3_000_000.0) for name in ("ZZZ", "AAA", "MMM")})

    assert order == ["AAA", "MMM", "ZZZ"]


def candidate(symbol: str) -> OrbCandidate:
    return OrbCandidate(symbol=symbol, direction=1, high=10.0, low=9.0, close=10.5)


def test_orb_breakouts_are_ranked_on_the_same_traded_value_key() -> None:
    """The relative-volume gate says who breaks out; this says who gets the slot."""
    strategy = FakeStrategy(price_history())
    strategy._daily_frames = {
        "AAA": session_frame(5_000_000.0, price_scale=0.1),
        "MMM": session_frame(1_000_000.0),
        "ZZZ": session_frame(2_000_000.0),
    }

    ordered = strategy._rank_candidates([candidate(name) for name in ("AAA", "MMM", "ZZZ")], NOW)

    assert [entry.symbol for entry in ordered] == ["ZZZ", "MMM", "AAA"]


def test_an_orb_breakout_without_a_daily_frame_ranks_last() -> None:
    strategy = FakeStrategy(price_history())
    strategy._daily_frames = {"ZZZ": session_frame(1_000_000.0)}

    ordered = strategy._rank_candidates([candidate("AAA"), candidate("ZZZ")], NOW)

    assert [entry.symbol for entry in ordered] == ["ZZZ", "AAA"]


# --- TFB-50's own position cap, on both paths that can open a position ---


class EnteringStrategy(FakeStrategy):
    """A composer whose entries always succeed, so the cap is what stops the loop."""

    def __init__(self, frames: dict[str, DataFrame]) -> None:
        super().__init__(price_history())
        self._daily_frames = frames
        self._eligible_symbols = sorted(frames)
        self._holdings = {}
        self._pending = {}
        self._claims = {}
        self._enabled = {"tfb_50"}
        self.entered: list[str] = []

    def _enter(self, engine: str, signal: str, asset: str, *args: object, **kwargs: object) -> bool:
        self.entered.append(asset)
        self._claims[asset] = engine
        self._holdings[asset] = holding(NOW, entry=1.0)
        self._holdings[asset].engine = engine
        return True


@pytest.fixture
def tfb_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every candidate passes TFB-50's setup, and its ATR is one point."""
    monkeypatch.setattr(portfolio, "tfb_entry", lambda frame: True)
    monkeypatch.setattr(portfolio, "latest_atr", lambda frame: 1.0)


def test_the_composer_stops_entering_tfb_50_at_its_own_cap(tfb_signals: None) -> None:
    """Five for this engine, whatever room the portfolio-wide cap still has."""
    volumes = {f"S{index}": float(index + 1) * 1e6 for index in range(TFB_POSITIONS_MAX + 3)}
    strategy = EnteringStrategy({name: session_frame(volume) for name, volume in volumes.items()})

    strategy._run_tfb(NOW)

    busiest = sorted(volumes, key=lambda symbol: -volumes[symbol])
    assert strategy.entered == busiest[:TFB_POSITIONS_MAX]
    assert strategy._engine_position_count("tfb_50") == TFB_POSITIONS_MAX


# --- The standalone class, which is what a backtest runs ---


class StandaloneHarness:
    """The lumibot surface a daily strategy touches, and nothing else."""

    def __init__(
        self,
        turnover: dict[str, float],
        held: dict[str, float],
        frames: dict[str, DataFrame] | None = None,
    ) -> None:
        self._frames = frames or {}
        self.parameters = {
            "symbols": list(turnover),
            "fractional_orders": True,
            "position_fraction_max": 0.10,
            "risk_per_trade_max": 0.02,
            "risk_per_day_max": 0.02,
        }
        self.is_backtesting = True
        self.portfolio_value = 100_000.0
        self.exporter = None
        self.submitted: list[tuple[str, str]] = []
        self._turnover = turnover
        self._held = held
        self.initialize()

    def get_datetime(self) -> datetime:
        return NOW

    def get_historical_prices(self, symbol: str, length: int, step: str) -> object:
        if symbol == "^GSPC":
            return type("Bars", (), {"df": price_history()})()
        frame = self._frames.get(symbol)
        frame = price_history().copy(deep=True) if frame is None else frame.copy(deep=True)
        if symbol not in self._frames:
            frame.iloc[-1, frame.columns.get_loc("volume")] = self._turnover[symbol]
        # Cut the prior session's high so the entry trigger clears it.
        frame.iloc[-2, frame.columns.get_loc("high")] = float(frame["close"].iloc[-1]) - 1.0
        return type("Bars", (), {"df": frame})()

    def get_positions(self) -> list[object]:
        return [
            type("P", (), {"quantity": quantity, "asset": type("A", (), {"symbol": symbol})()})()
            for symbol, quantity in self._held.items()
        ]

    def get_position(self, symbol: str) -> object | None:
        quantity = self._held.get(symbol)
        return None if quantity is None else type("P", (), {"quantity": quantity})()

    def get_orders(self) -> list[object]:
        return []

    def cancel_open_orders(self, orders: list[object]) -> None:
        pass

    def create_order(self, symbol: str, quantity: object, side: str, **kwargs: object) -> tuple:
        return (symbol, side)

    def submit_order(self, order: tuple) -> None:
        self.submitted.append(order)


class TfbStandalone(StandaloneHarness, tfb_50.Strategy):
    pass


class SmaStandalone(StandaloneHarness, sma.Strategy):
    pass


@pytest.fixture
def standalone_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 50-day average and ADX pinned so every candidate's setup passes."""
    closes = price_history()["close"]
    averages = DataFrame({"a": [119.0] * (len(closes) - 3) + [120.0] * 3}, index=closes.index)["a"]
    monkeypatch.setattr(shared, "ta_sma", lambda close, length, talib: averages)
    monkeypatch.setattr(
        shared,
        "ta_adx",
        lambda high, low, close, length, talib: DataFrame({"ADX_14": [25.0] * len(close)}),
    )
    monkeypatch.setattr(daily, "earnings_exit_due", lambda symbol, day: False)


def turnovers(count: int) -> dict[str, float]:
    """Distinct traded values, ascending by symbol name.

    Turnover has to run against the alphabet, or an engine that ranked nothing
    would pass a ranking assertion on symbol order alone.
    """
    return {f"S{index}": float(index + 1) * 1e6 for index in range(count)}


def test_the_standalone_engine_enters_the_busiest_names_up_to_its_cap(
    standalone_signals: None,
) -> None:
    volumes = turnovers(TFB_POSITIONS_MAX + 3)
    strategy = TfbStandalone(volumes, held={})

    strategy.on_trading_iteration()

    busiest = sorted(volumes, key=lambda symbol: -volumes[symbol])
    assert [symbol for symbol, _ in strategy.submitted] == busiest[:TFB_POSITIONS_MAX]
    assert all(side == "buy" for _, side in strategy.submitted)


def test_the_standalone_cap_counts_a_buy_sent_but_not_yet_filled(
    standalone_signals: None,
) -> None:
    """A daily entry fills at the next open, so the cap cannot wait for fills."""
    strategy = TfbStandalone(turnovers(TFB_POSITIONS_MAX + 3), held={})

    strategy.on_trading_iteration()

    assert len(strategy.submitted) == TFB_POSITIONS_MAX
    assert strategy.get_positions() == [], "no fill has landed, yet the cap held"


def test_a_position_already_held_takes_one_of_the_standalone_slots(
    standalone_signals: None,
) -> None:
    strategy = TfbStandalone(turnovers(TFB_POSITIONS_MAX + 3), held={"HELD": 10.0})

    strategy.on_trading_iteration()

    assert len(strategy.submitted) == TFB_POSITIONS_MAX - 1


def test_the_momentum_engine_caps_nothing(standalone_signals: None) -> None:
    """Its register states no position cap, so every signal is offered a slot."""
    strategy = SmaStandalone(turnovers(TFB_POSITIONS_MAX + 3), held={})

    assert strategy.positions_max is None
    assert strategy._open_positions() == 0


# --- TFB-50's own market screen, on both paths that can open a position ---


def screened_frame(turnover: float, price: float = 100.0) -> DataFrame:
    """A history whose last 20 sessions average `turnover`, at roughly `price`."""
    frame = price_history().copy(deep=True)
    scale = price / float(frame["close"].iloc[-1])
    for column in ("open", "high", "low", "close"):
        frame[column] = frame[column] * scale
    recent = frame.index[-TFB_TURNOVER_SESSIONS:]
    frame["volume"] = 1.0
    frame.loc[recent, "volume"] = turnover / cast(Any, frame.loc[recent, "close"])
    return frame


def test_the_screen_admits_a_name_that_clears_both_floors() -> None:
    assert tfb_market_ready(screened_frame(TFB_TURNOVER_MIN * 2)) is True


def test_the_screen_rejects_a_name_below_the_price_floor() -> None:
    """The register's floor is $5, so these literals do not follow the constant."""
    assert tfb_market_ready(screened_frame(TFB_TURNOVER_MIN * 2, price=4.99)) is False
    assert tfb_market_ready(screened_frame(TFB_TURNOVER_MIN * 2, price=5.01)) is True


def test_the_screen_rejects_a_name_whose_twenty_session_turnover_is_thin() -> None:
    """A busy last session must not carry a name that is usually too thin."""
    thin = screened_frame(TFB_TURNOVER_MIN * 0.5)
    busy_close = float(thin["close"].iloc[-1])
    thin.iloc[-1, thin.columns.get_loc("volume")] = TFB_TURNOVER_MIN * 5 / busy_close

    assert average_dollar_volume(thin, 1) > TFB_TURNOVER_MIN, "the last session is busy"
    assert average_dollar_volume(thin, TFB_TURNOVER_SESSIONS) < TFB_TURNOVER_MIN
    assert tfb_market_ready(thin) is False


def test_the_screen_rejects_a_name_with_too_little_history() -> None:
    short = screened_frame(TFB_TURNOVER_MIN * 2).tail(TFB_TURNOVER_SESSIONS - 1)

    assert tfb_market_ready(short) is False


def test_the_composer_skips_a_name_its_own_screen_rejects(tfb_signals: None) -> None:
    """The shared discovery admitted these; this engine's floors decide again."""
    strategy = EnteringStrategy(
        {
            "RICH": screened_frame(TFB_TURNOVER_MIN * 2),
            "THIN": screened_frame(TFB_TURNOVER_MIN * 0.5),
            "CHEAP": screened_frame(TFB_TURNOVER_MIN * 2, price=TFB_PRICE_MIN - 0.01),
        }
    )

    strategy._run_tfb(NOW)

    assert strategy.entered == ["RICH"]


def test_the_standalone_engine_skips_a_name_its_own_screen_rejects(
    standalone_signals: None,
) -> None:
    strategy = TfbStandalone(
        {"RICH": 0.0, "THIN": 0.0},
        held={},
        # Priced above the average the fixture pins, so the setup passes too and
        # the screen is the only thing that can turn a name away.
        frames={
            "RICH": screened_frame(TFB_TURNOVER_MIN * 2, price=200.0),
            "THIN": screened_frame(TFB_TURNOVER_MIN * 0.5, price=200.0),
        },
    )

    strategy.on_trading_iteration()

    assert [symbol for symbol, _ in strategy.submitted] == ["RICH"]


# --- Earnings no longer close a TFB-50 position ---


def test_the_composer_does_not_read_the_calendar_for_tfb_50(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its register reads "earnings exit = none", so the report is not consulted."""
    read: list[str] = []

    def record(symbol: str, day: object) -> bool:
        read.append(symbol)
        return True

    monkeypatch.setattr(portfolio, "earnings_exit_due", record)
    frame = price_history()
    strategy = FakeStrategy(frame)
    held = holding(NOW, entry=float(frame["close"].iloc[-1]))
    held.engine = "tfb_50"

    strategy._manage_daily(held, NOW.replace(hour=15, minute=55))

    assert read == [], "the calendar was read for an engine that does not use it"
    assert strategy.exited == []


def test_the_composer_still_closes_a_momentum_position_before_earnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(portfolio, "earnings_exit_due", lambda symbol, day: True)
    frame = price_history()
    strategy = FakeStrategy(frame)
    held = holding(NOW, entry=float(frame["close"].iloc[-1]))

    strategy._manage_daily(held, NOW.replace(hour=15, minute=55))

    assert strategy.exited == [held]


@pytest.mark.parametrize(
    ("strategy_class", "leaves"),
    [(TfbStandalone, False), (SmaStandalone, True)],
)
def test_only_the_momentum_engine_sells_the_standalone_way_before_earnings(
    monkeypatch: pytest.MonkeyPatch,
    strategy_class: type[StandaloneHarness],
    leaves: bool,
) -> None:
    monkeypatch.setattr(daily, "earnings_exit_due", lambda symbol, day: True)
    monkeypatch.setattr(shared, "ta_sma", lambda close, length, talib: closes_at(100.0))
    monkeypatch.setattr(
        shared, "ta_rsi", lambda close, length, talib: closes_at(60.0, name="RSI_14")
    )
    frame = price_history()
    last = float(frame["close"].iloc[-1])
    strategy = strategy_class({"AAA": 1e9}, held={"AAA": 10.0})
    strategy._highest["AAA"] = last
    strategy._stops["AAA"] = 1.0

    strategy._manage("AAA", NOW.date(), 10.0, frame)

    assert [side for _, side in strategy.submitted] == (["sell"] if leaves else [])


def closes_at(value: float, name: str | None = None) -> Series:
    closes = price_history()["close"]
    return Series(value, index=closes.index, name=name)
