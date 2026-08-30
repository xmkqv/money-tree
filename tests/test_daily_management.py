"""Replay the daily engines' position management against a built price history.

The trailing stop is the rule that decides when a daily trade dies, and it is
the one that reads the widest slice of state, so it is exercised here against a
real frame and real indicators rather than asserted from the source text.
"""

from datetime import UTC, datetime, timedelta

import pytest
from pandas import DataFrame, DatetimeIndex

from bot import portfolio
from bot.portfolio import Holding, OrbCandidate, Strategy
from bot.strategies.shared import TRADING_ZONE, normalize_ohlcv


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
