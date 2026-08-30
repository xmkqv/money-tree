"""Hold the strategy page to the code it claims to describe.

The page exists so the rules can be checked against intent, which is worth
nothing if the page and the bot can drift apart. Every number quoted on it is
pinned here to the literal in the module that actually runs, so moving a
threshold in the bot fails a test instead of leaving the page confidently wrong.
"""

import ast
import inspect
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pytest

from bot.portfolio import ORB_CLOSE_DEADLINE
from bot.portfolio import Strategy as PortfolioStrategy
from bot.strategies import orb, orb_base, orb_momentum, sma, tfb_50
from bot.strategies.shared import MIN_NOTIONAL_USD, entry_quantity
from bot.types import TradingConfiguration
from tests.test_ledger import _snapshot
from ui.dashboard import (
    CHART_TIMEFRAMES,
    bot_state,
    chart_window,
    opening_range,
    orb_levels,
    session_hour_bars,
    wilder_atr,
)
from ui.ledger import TRADING_ZONE
from ui.strategies import (
    FIELDS,
    ORB_HISTORY_SESSIONS,
    ORB_RISK_CEILING,
    ORB_TRAIL_ATR_MULTIPLE,
    ORB_TRAIL_BARS_MIN,
    POSITION_FRACTION_CEILING,
    POSITION_NOTIONAL_MIN,
    POSITIONS_MAX,
    Row,
    entry_windows,
    strategy_spec,
)


def configuration(per_trade: float = 0.005, per_day: float = 0.02) -> TradingConfiguration:
    return TradingConfiguration(
        fractional_orders=True,
        position_fraction_max=0.2,
        risk_per_day_max=per_day,
        risk_per_trade_max=per_trade,
    )


def spec_rows(strategy_id: str) -> dict[str, str]:
    card = next(
        card for card in strategy_spec(configuration())["strategies"] if card["id"] == strategy_id
    )
    return {row["field"]: row["value"] for row in card["rows"]}


COMPOSER = Path("src/bot/portfolio.py")


def orb_variant_arguments() -> dict[str, tuple[Any, ...]]:
    """The literals portfolio.py passes to _run_orb_variant for each engine."""
    tree = ast.parse(COMPOSER.read_text())
    found: dict[str, tuple[Any, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "_run_orb_variant":
            continue
        values = [argument.value for argument in node.args if isinstance(argument, ast.Constant)]
        found[str(values[0])] = tuple(values)
    return found


def test_every_strategy_answers_every_category() -> None:
    spec = strategy_spec(configuration())

    assert [card["id"] for card in spec["strategies"]] == ["orb", "orb_momentum", "sma", "tfb_50"]
    for card in spec["strategies"]:
        assert [row["field"] for row in card["rows"]] == FIELDS, card["id"]
        for row in card["rows"]:
            assert row["value"].strip(), f"{card['id']} {row['field']} is blank"
            assert row["source"].strip(), f"{card['id']} {row['field']} cites no source"


@pytest.mark.parametrize(
    ("engine", "minutes", "volume_multiple", "uses_macd"),
    [("orb", 5, 1.3, False), ("orb_momentum", 10, 1.5, True)],
)
def test_orb_numbers_match_the_composer(
    engine: str, minutes: int, volume_multiple: float, uses_macd: bool
) -> None:
    """portfolio.py hard-codes these per variant; the page must quote the same."""
    assert orb_variant_arguments()[engine] == (engine, minutes, volume_multiple, uses_macd)

    rows = spec_rows(engine)
    assert f"{minutes}-minute" in rows["Range"]
    assert f"{volume_multiple:g}x the 20-session" in rows["Confirmation"]
    assert ("MACD" in rows["Confirmation"]) is uses_macd


@pytest.mark.parametrize(
    ("engine", "minutes", "volume_multiple", "uses_macd"),
    [("orb", 5, 1.3, False), ("orb_momentum", 10, 1.5, True)],
)
def test_the_standalone_orb_classes_still_agree_with_the_composer(
    engine: str, minutes: int, volume_multiple: float, uses_macd: bool
) -> None:
    """The single-strategy classes duplicate these values; a split would mislead."""
    module = orb if engine == "orb" else orb_momentum
    assert module.Strategy.candle_minutes == minutes
    assert module.Strategy.volume_multiple == volume_multiple
    assert module.Strategy.uses_macd is uses_macd


ORB_ENGINES = ["orb", "orb_momentum"]


@pytest.mark.parametrize(("engine", "minutes"), [("orb", 5), ("orb_momentum", 10)])
def test_the_opening_range_is_quoted_as_a_period_not_a_bar_stamp(engine: str, minutes: int) -> None:
    """between_time bounds the candle by its stamp; the page must quote what it covers.

    The candle stamped 09:30 covers the five minutes up to 09:35 — _completed proves
    the stamp is the start, since it waits until stamp + minutes has passed. Selecting
    it as "09:30" to "09:34" picks that one candle, but 09:34 is not when the range
    ends, and the range ends exactly when the first scan runs.
    """
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)
    label_end = "09:34" if minutes == 5 else "09:39"

    assert 'between_time("09:30", "09:34" if minutes == 5 else "09:39")' in variant
    assert "index) + timedelta(minutes=minutes) <= now" in inspect.getsource(
        PortfolioStrategy._completed
    )

    opening_end = entry_windows()[engine]["from"]
    rows = spec_rows(engine)
    assert f"09:30 up to {opening_end}" in rows["Range"]
    assert label_end not in rows["Range"], "a bar stamp is not the end of the period"
    assert f"from {opening_end}, the moment the opening candle closes" in rows["Setup"]


@pytest.mark.parametrize(("engine", "minutes"), [("orb", 5), ("orb_momentum", 10)])
def test_the_order_is_sent_when_the_signal_candle_closes(engine: str, minutes: int) -> None:
    """The register enters at the next candle's open; the composer sends the order there.

    The scan runs on the candle boundary, reads the candle that has just closed, and
    submits in the same pass — so the order reaches the market at the open of the next
    candle. A signal candle must have closed at or after the opening candle did, which
    keeps the opening candle from breaking its own range and puts the earliest possible
    entry one candle beyond the range.
    """
    loop = inspect.getsource(PortfolioStrategy.on_trading_iteration)
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)

    assert "now.minute % 5 == 0" in loop
    assert "self._run_orb(now)" in loop and "self._run_orb_momentum(now)" in loop
    assert "or now.minute % minutes" in variant
    assert "if opening.empty or frame_at.time() < opening_end:" in variant
    assert "self._enter(" in variant, "the scan submits in the same pass"

    opening_end = entry_windows()[engine]["from"]
    hour, minute = (int(part) for part in opening_end.split(":"))
    first_entry = f"{hour:02d}:{minute + minutes:02d}"

    entry = spec_rows(engine)["Entry"]
    assert f"open of the next {minutes}-minute candle" in entry
    assert f"{first_entry} at the earliest" in entry
    assert "cannot break its own range" in entry


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_fill_and_not_the_signal_price_sets_the_trade(engine: str) -> None:
    """Sizing uses the last known price; everything after it is read off the fill."""
    filled = inspect.getsource(PortfolioStrategy.on_filled_order)

    assert "holding.entry = self._entry_price(order, price)" in filled
    assert "holding.risk = abs(holding.entry - holding.stop)" in filled
    assert "avg_fill_price" in inspect.getsource(PortfolioStrategy._entry_price)
    assert "candidate.close," in inspect.getsource(PortfolioStrategy._run_orb_variant)

    entry = spec_rows(engine)["Entry"]
    assert "size is worked out from the breakout candle's close" in entry
    assert "the fill then sets the entry" in entry
    assert ("the risk and the targets" in entry) is (engine == "orb")


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_relative_volume_needs_a_full_history_to_confirm(engine: str) -> None:
    """A short history is no confirmation, so the page must not promise an average."""
    source = inspect.getsource(orb_base.relative_volume_ready)

    assert f"if len(history) != {ORB_HISTORY_SESSIONS}" in source
    assert f".tail({ORB_HISTORY_SESSIONS})" in source
    assert "historical_daily_average >= 1_000_000" in source

    confirmation = spec_rows(engine)["Confirmation"]
    assert f"All {ORB_HISTORY_SESSIONS} earlier sessions" in confirmation
    assert "no confirmation at all" in confirmation


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_traded_stock_is_off_limits_to_both_breakout_engines(engine: str) -> None:
    """_orb_traded is keyed by day and symbol alone, so the ban crosses engines."""
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)

    assert "self._orb_scanned.add(key)" in variant
    assert "(now.date(), symbol) in self._orb_traded" in variant
    assert "key = (now.date(), engine, symbol)" in variant

    setup = spec_rows(engine)["Setup"]
    assert "at most once per stock per day" in setup
    assert "Once either breakout engine has traded a stock" in setup


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_breakout_trail_matches_the_composer(engine: str) -> None:
    manage = inspect.getsource(PortfolioStrategy._manage_orb)

    assert f"trail = {ORB_TRAIL_ATR_MULTIPLE} * latest_atr(frame)" in manage
    assert f"if len(frame) < {ORB_TRAIL_BARS_MIN}" in manage
    assert "next_stop(holding.direction, holding.stop, candidate)" in manage

    stop = spec_rows(engine)["Stop Loss"]
    assert f"trails {ORB_TRAIL_ATR_MULTIPLE:g}x the 14-period ATR" in stop
    assert f"{ORB_TRAIL_BARS_MIN} completed candles" in stop


def spec_row(strategy_id: str, field: str) -> Row:
    card = next(
        card for card in strategy_spec(configuration())["strategies"] if card["id"] == strategy_id
    )
    return next(row for row in card["rows"] if row["field"] == field)


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_resting_stop_is_resent_when_it_stops_covering_the_position(engine: str) -> None:
    """The stop lives at the broker, so the page may not describe it as a watched level."""
    source = inspect.getsource(PortfolioStrategy._resync_stops)

    assert "self._protect(holding, quantity)" in source
    assert "resting[1] < quantity - STOP_COVERAGE_TOLERANCE" in source

    stop = spec_row(engine, "Stop Loss")
    assert "_resync_stops" in stop["source"]
    assert "rests as a live order at the broker" in stop["value"]


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_position_below_the_minimum_notional_is_not_opened(engine: str) -> None:
    assert MIN_NOTIONAL_USD == POSITION_NOTIONAL_MIN
    assert "quantity * price < MIN_NOTIONAL_USD" in inspect.getsource(entry_quantity)

    entry = spec_rows(engine)["Entry"]
    assert f"less than ${POSITION_NOTIONAL_MIN}" in entry
    assert "another engine already holds the stock" in entry


def test_the_five_minute_targets_are_cut_from_the_fill() -> None:
    """ORB5 re-reads its targets on the fill, so the page must not quote the signal price."""
    filled = inspect.getsource(PortfolioStrategy.on_filled_order)

    assert 'if holding.engine == "orb":' in filled
    assert "for multiple in (1.5, 2.5, 4.0)" in filled

    reward = spec_rows("orb")["Min. R:R"]
    assert "re-cut from the filled price" in reward
    assert "1.5x, 2.5x and 4x the risk actually taken" in reward


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_scale_out_fractions_match_the_composer(engine: str) -> None:
    manage = inspect.getsource(PortfolioStrategy._manage_orb)

    assert "holding.original_quantity * 0.5" in manage
    assert "holding.original_quantity * 0.25" in manage

    exit_rule = spec_rows(engine)["Exit Rule"]
    assert "half the position as first filled" in exit_rule
    assert "a quarter of it at the second" in exit_rule


def test_the_five_minute_engine_states_its_own_risk_ceiling() -> None:
    """ORB declares 1% in the register, so the configured limit does not override it."""
    source = inspect.getsource(PortfolioStrategy._run_orb_variant)

    assert f'risk_fraction_max={ORB_RISK_CEILING} if engine == "orb" else None' in source
    assert orb.Strategy.risk_fraction_max == ORB_RISK_CEILING
    assert orb_momentum.Strategy.risk_fraction_max is None
    assert "risk_fraction = risk_fraction_max" in inspect.getsource(PortfolioStrategy._enter)

    risk = {
        card["id"]: next(row for row in card["rows"] if row["field"] == "Max Risk")["value"]
        for card in strategy_spec(configuration(per_trade=0.02))["strategies"]
    }
    assert risk["orb"].startswith("1% of account equity per trade")
    assert risk["orb_momentum"].startswith("2% of account equity per trade")

    # A tighter configured limit must not drag the published ORB figure down with it,
    # because the bot no longer applies it to this engine.
    assert spec_rows("orb")["Max Risk"].startswith("1% of account equity per trade")
    assert spec_rows("orb_momentum")["Max Risk"].startswith("0.5% of account equity per trade")


@pytest.mark.parametrize(("engine", "multiple"), [("sma", 1.5), ("tfb_50", 2.0)])
def test_daily_stop_multiples_match_the_composer(engine: str, multiple: float) -> None:
    runner = PortfolioStrategy._run_sma if engine == "sma" else PortfolioStrategy._run_tfb

    assert f"{multiple} * latest_atr(frame)" in inspect.getsource(runner)
    assert f"{multiple:g}x the 14-period ATR" in spec_rows(engine)["Stop Loss"]

    module = sma if engine == "sma" else tfb_50
    assert module.Strategy.stop_multiple == multiple


def test_only_the_momentum_engine_blocks_entries_before_earnings() -> None:
    assert "earnings_blocked" in inspect.getsource(PortfolioStrategy._run_sma)
    assert "earnings_blocked" not in inspect.getsource(PortfolioStrategy._run_tfb)

    assert "within 5 days" in spec_rows("sma")["Entry"]
    assert "do not block" in spec_rows("tfb_50")["Entry"]


def test_portfolio_limits_match_the_composer() -> None:
    source = inspect.getsource(PortfolioStrategy._enter)

    assert f"self._pending) >= {POSITIONS_MAX}" in source
    assert f"min({POSITION_FRACTION_CEILING:.2f}" in source

    rules = {row["field"]: row["value"] for row in strategy_spec(configuration())["portfolio"]}
    assert f"At most {POSITIONS_MAX} positions" in rules["Position cap"]
    for card in strategy_spec(configuration())["strategies"]:
        risk = next(row for row in card["rows"] if row["field"] == "Max Risk")
        assert "10% of equity" in risk["value"]


def test_intraday_engines_are_flat_before_the_close() -> None:
    assert "ORB_CLOSE_DEADLINE" in inspect.getsource(PortfolioStrategy._manage)
    assert time(15, 55) > ORB_CLOSE_DEADLINE, "the market order needs room to fill"

    for engine in ("orb", "orb_momentum"):
        assert "15:55" in spec_rows(engine)["Emergency Exit"]
    for engine in ("sma", "tfb_50"):
        assert "15:50" in spec_rows(engine)["Emergency Exit"]


def test_risk_wording_follows_the_reported_configuration() -> None:
    """The limits are environment settings, so the page must not quote defaults."""
    spec = strategy_spec(configuration(per_trade=0.0075, per_day=0.03))
    rows = {row["field"]: row["value"] for row in spec["strategies"][2]["rows"]}
    rules = {row["field"]: row["value"] for row in spec["portfolio"]}

    assert "0.75% of account equity" in rows["Max Risk"]
    assert "3%" in rules["Daily loss limit"]
    assert spec["configured"] is True


def test_spec_falls_back_to_documented_defaults_when_no_bot_is_reporting() -> None:
    spec = strategy_spec(None)

    assert spec["configured"] is False
    assert "0.5% of account equity" in spec["strategies"][2]["rows"][8]["value"]


def test_the_universe_screen_matches_the_discovery_query() -> None:
    source = inspect.getsource(PortfolioStrategy._discover_eligible_symbols)

    assert "500_000_000" in source
    assert "cap >= 5e8 and volume >= 1e6" in source

    market = spec_rows("orb")["Market"]
    assert "$500M" in market and "1M shares" in market


def test_the_page_describes_the_module_the_bot_actually_runs() -> None:
    """trade.py runs the composer, not the single-strategy classes."""
    trade = Path("src/bot/trade.py").read_text()

    assert "from bot.portfolio import Strategy" in trade
    for card in strategy_spec(configuration())["strategies"]:
        assert any("portfolio.py" in row["source"] for row in card["rows"]), card["id"]


def test_entry_windows_match_the_composer() -> None:
    """The badge says whether a trade can start now, so the hours must be the bot's."""
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)
    assert "opening_end = time(9, 35) if minutes == 5 else time(9, 40)" in variant
    assert "opening_end <= now.time() <= time(10, 30)" in variant

    loop = inspect.getsource(PortfolioStrategy.on_trading_iteration)
    assert "now.time() < time(9, 40)" in loop
    assert "self._run_daily(now)" in loop

    assert entry_windows() == {
        "orb": {"from": "09:35", "to": "10:30"},
        "orb_momentum": {"from": "09:40", "to": "10:30"},
        "sma": {"from": "09:30", "to": "09:40"},
        "tfb_50": {"from": "09:30", "to": "09:40"},
    }


def test_every_engine_on_the_page_has_an_entry_window() -> None:
    windows = entry_windows()

    for card in strategy_spec(configuration())["strategies"]:
        assert card["id"] in windows, card["id"]


def test_bot_state_says_whether_a_roster_was_reported_at_all() -> None:
    """An unreported roster is unknown, not every engine switched off."""
    assert bot_state(None, stale=True)["reported"] is False
    assert bot_state(_snapshot(), stale=False)["reported"] is True
    assert bot_state(_snapshot(), stale=True)["reported"] is True


@pytest.mark.parametrize(
    ("timeframe", "least_days"),
    [("5Min", 2), ("1Hour", 14), ("1Day", 240)],
)
def test_each_timeframe_puts_its_own_context_around_a_trade(
    timeframe: str, least_days: int
) -> None:
    """A day chart needs months either side; a five-minute chart needs hours."""
    _, display, end = chart_window(timeframe, date(2026, 8, 27), date(2026, 8, 27))

    assert (end - display).days >= least_days
    assert display.date() < date(2026, 8, 27) < end.date()
    assert str(display.tzinfo) == str(TRADING_ZONE)


def test_a_long_hold_cannot_ask_for_an_unbounded_run_of_bars() -> None:
    """The window is clamped, so one chart stays one upstream page."""
    _, display, end = chart_window("5Min", date(2020, 1, 2), date(2026, 8, 27))

    assert (end - display).days <= CHART_TIMEFRAMES["5Min"]["span_max"]
    assert end.date() > date(2026, 8, 27)


def test_the_window_always_covers_the_trade_it_is_drawn_for() -> None:
    for timeframe in CHART_TIMEFRAMES:
        _, display, end = chart_window(timeframe, date(2026, 8, 24), date(2026, 8, 28))
        assert display.date() <= date(2026, 8, 24), timeframe
        assert end.date() >= date(2026, 8, 28), timeframe


@pytest.mark.parametrize("timeframe", list(CHART_TIMEFRAMES))
def test_data_reaches_back_far_enough_to_warm_a_200_period_average(timeframe: str) -> None:
    """Without a run-up the longest average would be missing from every chart."""
    data, display, _ = chart_window(timeframe, date(2026, 8, 27), date(2026, 8, 27))
    lead = (display - data).days

    assert lead >= int(CHART_TIMEFRAMES[timeframe]["warmup_days"]) - 1, timeframe
    # roughly 200 bars of the timeframe's own size, allowing for weekends
    sessions = lead * 5 / 7
    per_session = {"5Min": 78, "1Hour": 7, "1Day": 1}[timeframe]
    assert sessions * per_session >= 200, timeframe


def test_reconstructed_orb_levels_follow_the_composer() -> None:
    """A 10.00-10.50 range: the stop sits three quarters back for a long."""
    long = orb_levels("orb", 1, entry=10.60, high=10.50, low=10.00)

    assert long["range"] == {"high": 10.5, "low": 10.0}
    assert long["stop"] == pytest.approx(10.375)
    risk = 10.60 - 10.375
    assert long["targets"] == pytest.approx([10.60 + risk * m for m in (1.5, 2.5, 4.0)])

    short = orb_levels("orb", -1, entry=9.90, high=10.50, low=10.00)
    assert short["stop"] == pytest.approx(10.125)


def test_the_ten_minute_engine_keeps_range_based_targets() -> None:
    """Only the five-minute engine re-cuts its targets from the fill."""
    levels = orb_levels("orb_momentum", 1, entry=10.60, high=10.50, low=10.00)

    assert levels["targets"] == pytest.approx([10.75, 11.0, 11.5])


def test_average_true_range_needs_more_bars_than_its_period() -> None:
    flat = [{"h": 2.0, "l": 1.0, "c": 1.5} for _ in range(14)]

    assert wilder_atr(flat) is None
    assert wilder_atr(flat + [{"h": 2.0, "l": 1.0, "c": 1.5}]) == pytest.approx(1.0)


def test_the_opening_range_is_the_first_candle_of_its_length() -> None:
    bars = [
        {"t": "2026-08-27T13:30:00Z", "h": 10.5, "l": 10.0, "c": 10.2},
        {"t": "2026-08-27T13:35:00Z", "h": 11.0, "l": 9.5, "c": 10.8},
        {"t": "2026-08-27T13:45:00Z", "h": 12.0, "l": 8.0, "c": 11.0},
    ]

    assert opening_range(bars, date(2026, 8, 27), 5) == (10.5, 10.0)
    # the ten-minute engine takes both of the first two candles
    assert opening_range(bars, date(2026, 8, 27), 10) == (11.0, 9.5)
    assert opening_range([], date(2026, 8, 27), 5) is None


def _half_hours(day: str, times: list[str]) -> list[dict[str, Any]]:
    """Half-hour bars at the given New York times, expressed the way Alpaca does."""
    bars = []
    for n, clock in enumerate(times, start=1):
        at = datetime.fromisoformat(f"{day}T{clock}:00").replace(tzinfo=TRADING_ZONE)
        bars.append(
            {
                "t": at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "o": float(n),
                "h": float(n) + 1,
                "l": float(n) - 1,
                "c": float(n) + 0.5,
                "v": 100.0 * n,
            }
        )
    return bars


def _clocks(bars: list[dict[str, Any]]) -> list[str]:
    return [
        datetime.fromisoformat(str(bar["t"]).replace("Z", "+00:00"))
        .astimezone(TRADING_ZONE)
        .strftime("%H:%M")
        for bar in bars
    ]


def test_hourly_bars_are_counted_from_the_opening_bell() -> None:
    """Alpaca's own hours start at midnight, which puts 09:00 on a session chart."""
    full = ["09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00"]

    assert _clocks(session_hour_bars(_half_hours("2026-08-27", full))) == [
        "09:30",
        "10:30",
        "11:30",
        "12:30",
    ]


def test_hourly_bars_leave_out_trading_outside_the_session() -> None:
    """The pre- and post-market bars come back alongside and are not the session."""
    around = ["04:00", "08:00", "09:00", "09:30", "15:30", "16:00", "19:30"]

    assert _clocks(session_hour_bars(_half_hours("2026-08-27", around))) == ["09:30", "15:30"]


def test_the_last_hourly_bar_is_the_half_hour_to_the_close() -> None:
    """A session is six and a half hours, so its seventh bar is a short one."""
    session = [
        f"{hour:02d}:{minute:02d}"
        for hour in range(9, 16)
        for minute in (0, 30)
        if hour > 9 or minute
    ]
    folded = session_hour_bars(_half_hours("2026-08-27", session))

    assert len(folded) == 7
    assert _clocks(folded)[-1] == "15:30"


def test_a_folded_hour_carries_the_whole_hour_it_covers() -> None:
    """Open from the first half, close from the last, extremes and volume across both."""
    (folded,) = session_hour_bars(_half_hours("2026-08-27", ["09:30", "10:00"]))

    assert folded["o"] == 1.0  # the 09:30 half-hour's open
    assert folded["c"] == 2.5  # the 10:00 half-hour's close
    assert folded["h"] == 3.0
    assert folded["l"] == 0.0
    assert folded["v"] == 300.0


def test_folding_keeps_sessions_apart() -> None:
    """Two days of half-hours must not collapse into one run of hours."""
    bars = _half_hours("2026-08-27", ["09:30", "10:00"]) + _half_hours(
        "2026-08-28", ["09:30", "10:00"]
    )
    folded = session_hour_bars(bars)

    assert len(folded) == 2
    assert _clocks(folded) == ["09:30", "09:30"]
