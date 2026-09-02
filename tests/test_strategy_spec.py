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

from bot.portfolio import DAILY_EXIT_NEEDS_BOTH as COMPOSER_EXIT_NEEDS_BOTH
from bot.portfolio import ORB_CLOSE_DEADLINE, UNIVERSE_CAP_MIN, UNIVERSE_TURNOVER_MIN
from bot.portfolio import ORB_ENTRY_EXTENSION_MAX as COMPOSER_ENTRY_EXTENSION_MAX
from bot.portfolio import ORB_SIGNAL_CANDLES_MAX as COMPOSER_SIGNAL_CANDLES_MAX
from bot.portfolio import ORB_TARGET_MULTIPLES as COMPOSER_TARGET_MULTIPLES
from bot.portfolio import Strategy as PortfolioStrategy
from bot.strategies import orb, orb_base, orb_momentum, shared, sma, tfb_50
from bot.strategies.daily import DailyStrategy
from bot.strategies.orb_base import (
    ORB_PRICE_MIN,
    ORB_RISK_CEILING,
    ORB_TURNOVER_MIN,
)
from bot.strategies.shared import MIN_NOTIONAL_USD, entry_quantity, fractional_allowed
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
    DAILY_EXIT_NEEDS_BOTH,
    FIELDS,
    ORB_HISTORY_SESSIONS,
    ORB_TRAIL_ATR_MULTIPLE,
    ORB_TRAIL_BARS_MIN,
    POSITION_FRACTION_CEILING,
    POSITION_NOTIONAL_MIN,
    POSITIONS_MAX,
    RISK_PER_TRADE_DEFAULT,
    Row,
    entry_windows,
    strategy_spec,
)
from ui.strategies import (
    ORB_ENTRY_EXTENSION_MAX as PAGE_ENTRY_EXTENSION_MAX,
)
from ui.strategies import (
    ORB_SIGNAL_CANDLES_MAX as PAGE_SIGNAL_CANDLES_MAX,
)


def configuration(per_trade: float = 0.005, per_day: float = 0.02) -> TradingConfiguration:
    return TradingConfiguration(
        fractional_orders=True,
        position_fraction_max=0.2,
        risk_per_day_max=per_day,
        risk_per_trade_max=per_trade,
    )


def spec_rows(strategy_id: str) -> dict[str, str]:
    return {row["field"]: row["value"] for row in spec_rows_full(strategy_id)}


def spec_rows_full(strategy_id: str) -> list[dict[str, str]]:
    card = next(
        card for card in strategy_spec(configuration())["strategies"] if card["id"] == strategy_id
    )
    return card["rows"]


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
    ("engine", "minutes", "volume_multiple", "uses_macd", "ranked"),
    [("orb", 5, 1.3, False, True), ("orb_momentum", 10, 1.5, False, True)],
)
def test_orb_numbers_match_the_composer(
    engine: str, minutes: int, volume_multiple: float, uses_macd: bool, ranked: bool
) -> None:
    """portfolio.py hard-codes these per variant; the page must quote the same."""
    assert orb_variant_arguments()[engine] == (
        engine,
        minutes,
        volume_multiple,
        uses_macd,
        ranked,
    )

    rows = spec_rows(engine)
    assert f"{minutes}-minute" in rows["Range"]
    assert f"{volume_multiple:g}x the 20-session" in rows["Confirmation"]
    assert ("MACD" in rows["Confirmation"]) is uses_macd


@pytest.mark.parametrize(
    ("engine", "minutes", "volume_multiple", "uses_macd"),
    [("orb", 5, 1.3, False), ("orb_momentum", 10, 1.5, False)],
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
    assert "if opening.empty or after.empty:" in variant
    assert "self._orb_signal(after, high, low)" in variant
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
    assert "price = self._orb_price(candidate)" in inspect.getsource(
        PortfolioStrategy._run_orb_variant
    )
    assert "return candidate.close" in inspect.getsource(PortfolioStrategy._orb_price)

    entry = spec_rows(engine)["Entry"]
    assert "size is worked out from the live quote" in entry
    assert "falling back to the breakout candle's close" in entry
    assert "the fill then sets the entry, the risk and the targets" in entry


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_short_is_quoted_as_settling_in_whole_shares(engine: str) -> None:
    """Only the breakout engines can short, so only they carry the rounding rule."""
    assert fractional_allowed(1, True) is True
    assert fractional_allowed(-1, True) is False

    rounds_down = 'fractional_allowed(direction, bool(self.parameters["fractional_orders"]))'
    assert rounds_down in inspect.getsource(PortfolioStrategy._enter)
    assert "fractional_allowed(holding.direction" in inspect.getsource(PortfolioStrategy._protect)
    assert "fractional_allowed(holding.direction" in inspect.getsource(PortfolioStrategy._exit)

    rows = spec_rows(engine)
    assert "sized in whole shares" in rows["Direction"]
    assert "rounded down to whole shares" in rows["Exit Rule"]


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_scale_out_below_one_share_is_skipped_before_the_stop_is_cancelled(engine: str) -> None:
    """Sizing must happen before _cancel, or a skipped slice strips the stop."""
    source = inspect.getsource(PortfolioStrategy._exit)
    sized = source.index("size = quantity_value(")
    cancelled = source.index("self._cancel(holding.asset)")

    assert sized < cancelled, "the order is sized before anything is cancelled"
    assert "if size <= 0:" in source

    assert "skipped rather than sent" in spec_rows(engine)["Exit Rule"]


def test_only_the_engines_that_can_short_state_the_rounding_rule() -> None:
    for engine in ("sma", "tfb_50"):
        assert "Long only." in spec_rows(engine)["Direction"]
        assert "whole shares" not in spec_rows(engine)["Direction"]


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_relative_volume_needs_a_full_history_to_confirm(engine: str) -> None:
    """A short history is no confirmation, so the page must not promise an average."""
    history_source = inspect.getsource(orb_base.session_volume)
    source = inspect.getsource(orb_base.relative_volume_ready)

    assert f"if len(history) != {ORB_HISTORY_SESSIONS}" in history_source
    assert f".tail({ORB_HISTORY_SESSIONS})" in history_source
    assert "volume.turnover >= ORB_TURNOVER_MIN" in source

    confirmation = spec_rows(engine)["Confirmation"]
    assert f"All {ORB_HISTORY_SESSIONS} earlier sessions" in confirmation
    assert "no confirmation at all" in confirmation


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_traded_stock_is_off_limits_to_both_breakout_engines(engine: str) -> None:
    """_orb_traded is keyed by day and symbol alone, so the ban crosses engines."""
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)
    unscanned = inspect.getsource(PortfolioStrategy._orb_unscanned)

    assert "self._orb_scanned.add(key)" in variant
    assert "(day, symbol) not in self._orb_traded" in unscanned
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
    assert f"{ORB_TRAIL_BARS_MIN} completed" in stop


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


@pytest.mark.parametrize(
    ("engine", "multiples"),
    [("orb", "1.5x, 2.5x and 4x"), ("orb_momentum", "2x, 3x and 5x")],
)
def test_the_targets_are_cut_from_the_fill(engine: str, multiples: str) -> None:
    """Both engines re-read their targets on the fill, so neither quotes the signal price."""
    filled = inspect.getsource(PortfolioStrategy.on_filled_order)

    assert "multiples = ORB_TARGET_MULTIPLES.get(holding.engine)" in filled
    assert "holding.entry + holding.direction * holding.risk * multiple" in filled

    reward = spec_rows(engine)["Min. R:R"]
    assert "re-cut from the filled price" in reward
    assert f"{multiples} the risk actually taken" in reward


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_scale_out_fractions_match_the_composer(engine: str) -> None:
    manage = inspect.getsource(PortfolioStrategy._manage_orb)

    assert "holding.original_quantity * 0.5" in manage
    assert "holding.original_quantity * 0.25" in manage

    exit_rule = spec_rows(engine)["Exit Rule"]
    assert "half the position as first filled" in exit_rule
    assert "a quarter of it at the second" in exit_rule


def test_the_five_minute_engine_states_its_own_risk_ceiling() -> None:
    """ORB declares its own ceiling in the register, so the configured limit does not win."""
    source = inspect.getsource(PortfolioStrategy._run_orb_variant)

    assert 'risk_fraction_max=ORB_RISK_CEILING if engine == "orb" else None' in source
    assert orb.Strategy.risk_fraction_max == ORB_RISK_CEILING
    assert orb_momentum.Strategy.risk_fraction_max is None
    assert "risk_fraction = risk_fraction_max" in inspect.getsource(PortfolioStrategy._enter)

    risk = {
        card["id"]: next(row for row in card["rows"] if row["field"] == "Max Risk")["value"]
        for card in strategy_spec(configuration(per_trade=0.02))["strategies"]
    }
    ceiling = f"{ORB_RISK_CEILING * 100:g}% of account equity per trade"
    assert risk["orb"].startswith(ceiling)
    assert risk["orb_momentum"].startswith("2% of account equity per trade")

    # A looser configured limit must not drag the published ORB figure up with it,
    # because the bot no longer applies it to this engine.
    assert spec_rows("orb")["Max Risk"].startswith(ceiling)
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
    """The limits are environment settings, so the page must not quote defaults.

    Read off TFB-50: Momentum (SMA) sets no per-trade risk limit, so its card
    has no configured figure to follow.
    """
    spec = strategy_spec(configuration(per_trade=0.0075, per_day=0.03))
    rows = {row["field"]: row["value"] for row in spec["strategies"][3]["rows"]}
    rules = {row["field"]: row["value"] for row in spec["portfolio"]}

    assert "0.75% of account equity" in rows["Max Risk"]
    assert "3%" in rules["Daily loss limit"]
    assert spec["configured"] is True


def test_spec_falls_back_to_documented_defaults_when_no_bot_is_reporting() -> None:
    spec = strategy_spec(None)
    card = next(card for card in spec["strategies"] if card["id"] == "tfb_50")
    rows = {row["field"]: row["value"] for row in card["rows"]}

    assert spec["configured"] is False
    assert f"{RISK_PER_TRADE_DEFAULT:.1%} of account equity" in rows["Max Risk"]


def test_the_momentum_engine_sets_no_per_trade_risk_limit() -> None:
    """Its register reads "risk per trade = not set", so only the notional caps it."""
    assert "caps_risk_per_trade=False" in inspect.getsource(PortfolioStrategy._run_sma)
    assert "caps_risk_per_trade" not in inspect.getsource(PortfolioStrategy._run_tfb)

    assert sma.Strategy.caps_risk_per_trade is False
    assert tfb_50.Strategy.caps_risk_per_trade is True

    risk = spec_rows("sma")["Max Risk"]
    assert "No per-trade risk limit" in risk
    assert f"{POSITION_FRACTION_CEILING:.0%} of equity" in risk


def test_the_daily_engines_give_up_on_the_twenty_day_average() -> None:
    assert "length=20" in inspect.getsource(shared.signal_exit)

    for engine in ("sma", "tfb_50"):
        assert "20-day average" in spec_rows(engine)["Exit Rule"]


def test_only_the_momentum_engine_exits_on_either_condition() -> None:
    """TFB-50 still waits for the close and RSI together."""
    assert DAILY_EXIT_NEEDS_BOTH == COMPOSER_EXIT_NEEDS_BOTH
    assert sma.Strategy.exit_needs_both is False
    assert tfb_50.Strategy.exit_needs_both is True

    assert "Either one is enough" in spec_rows("sma")["Exit Rule"]
    assert "with RSI (14) under 50" in spec_rows("tfb_50")["Exit Rule"]


def test_an_unreadable_earnings_calendar_does_not_force_an_exit() -> None:
    """The register only exits on earnings it can actually see."""
    assert "return False" in inspect.getsource(DailyStrategy._earnings_exit_due)
    assert "exit_for_earnings = False" in inspect.getsource(PortfolioStrategy._manage_daily)

    for engine in ("sma", "tfb_50"):
        assert "cannot be read" in spec_rows(engine)["Emergency Exit"]


def test_the_daily_setups_describe_what_the_predicates_check() -> None:
    """Both setup rows had drifted from the comparisons they name."""
    assert "latest > latest_50 > latest_200" in inspect.getsource(shared.momentum_entry)
    sma_setup = spec_rows("sma")["Setup"]
    assert "above the 50-day average" in sma_setup
    assert "average above the 200-day" in sma_setup

    assert "_finite_value(average_50, -4)" in inspect.getsource(shared.tfb_entry)
    assert "3 sessions ago" in spec_rows("tfb_50")["Setup"], "iloc[-1] vs iloc[-4] is three"


def test_sorting_sits_between_confirmation_and_entry() -> None:
    """A rule that decides who gets a slot belongs before the entry it gates."""
    assert FIELDS.index("Confirmation") + 1 == FIELDS.index("Sorting")
    assert FIELDS.index("Sorting") + 1 == FIELDS.index("Entry")


def test_daily_candidates_compete_on_traded_value_in_both_paths() -> None:
    """Alphabetical order handed every slot to whatever sorted first."""
    for runner in (PortfolioStrategy._ranked, DailyStrategy._ranked):
        source = inspect.getsource(runner)
        assert "latest_dollar_volume(frame)" in source
        assert "key=lambda row: (-row[0], row[1])" in source

    for engine in ("sma", "tfb_50"):
        sorting = spec_rows(engine)["Sorting"]
        assert "close times" in sorting and "share volume" in sorting
        assert "highest first" in sorting
        assert "_ranked" in next(
            row["source"] for row in spec_rows_full(engine) if row["field"] == "Sorting"
        )

    for engine in ORB_ENGINES:
        breakout_sorting = spec_rows(engine)["Sorting"]
        assert "close times" in breakout_sorting and "share volume" in breakout_sorting
        assert "highest first" in breakout_sorting
        assert "_rank_candidates" in next(
            row["source"] for row in spec_rows_full(engine) if row["field"] == "Sorting"
        )


def test_an_empty_earnings_calendar_does_not_hold_an_entry_back() -> None:
    """No known date is not the same as earnings being near."""
    assert "upcoming is not None and" in inspect.getsource(shared.earnings_blocked)

    entry = spec_rows("sma")["Entry"]
    assert "within 5 days" in entry
    assert "no earnings date on file is not held back" in entry


def test_the_daily_stop_only_trails_closes_made_since_entry() -> None:
    """Anchoring to the whole frame would stop a new position out on day one."""
    source = inspect.getsource(PortfolioStrategy._manage_daily)

    assert "if len(since):" in source
    assert "observed" not in source


def test_the_universe_screen_matches_the_discovery_query() -> None:
    source = inspect.getsource(PortfolioStrategy._discover_eligible_symbols)

    assert "cap >= UNIVERSE_CAP_MIN" in source
    assert "price >= ORB_PRICE_MIN" in source
    assert "volume * price >= UNIVERSE_TURNOVER_MIN" in source
    assert UNIVERSE_CAP_MIN == 500_000_000.0
    assert UNIVERSE_TURNOVER_MIN == ORB_TURNOVER_MIN

    market = spec_rows("orb")["Market"]
    assert "$500M" in market and "$20M" in market and f"${ORB_PRICE_MIN:.0f}" in market


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


def test_the_ten_minute_targets_are_counted_off_the_fill() -> None:
    """A 10.00-10.50 range: the stop sits three quarters back, R is the rest."""
    levels = orb_levels("orb_momentum", 1, entry=10.50, high=10.50, low=10.00)

    assert levels["stop"] == pytest.approx(10.375)
    risk = 10.50 - 10.375
    assert levels["targets"] == pytest.approx(
        [10.50 + risk * m for m in COMPOSER_TARGET_MULTIPLES["orb_momentum"]]
    )


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_fill_past_the_level_carries_its_targets_with_it(engine: str) -> None:
    """A breakout candle closing past the level used to fill above its own targets.

    ORB10's range targets sat at 10.75, 11.00 and 11.50, so an 11.60 fill was
    through all three the moment it landed: the position scaled itself out within a
    minute of opening, nowhere near its 10.375 stop. Counting from the fill keeps
    every target ahead of the entry, whatever the multiples are set to.
    """
    levels = orb_levels(engine, 1, entry=11.60, high=10.50, low=10.00)

    assert min(levels["targets"]) > 11.60
    assert levels["targets"] == pytest.approx(
        [11.60 + (11.60 - 10.375) * m for m in COMPOSER_TARGET_MULTIPLES[engine]]
    )


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


@pytest.mark.parametrize(("engine", "module"), [("orb", orb), ("orb_momentum", orb_momentum)])
def test_the_standalone_classes_cut_the_same_targets_as_the_composer(
    engine: str, module: Any
) -> None:
    """A backtest that scaled out on different levels than the live bot proves nothing."""
    pending = orb_base.OrbPending(1, 12.925)
    standalone = module.Strategy._filled_targets(module.Strategy, pending, 13.42)

    risk = 13.42 - 12.925
    composed = [13.42 + risk * multiple for multiple in COMPOSER_TARGET_MULTIPLES[engine]]

    assert module.Strategy.target_multiples == COMPOSER_TARGET_MULTIPLES[engine]
    assert list(standalone) == pytest.approx(composed)
    assert min(standalone) > 13.42, "no target may start behind the fill that opened the trade"


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_breakout_is_confirmed_as_of_the_signal_candle(engine: str) -> None:
    """A signal recovered a candle late is still confirmed on the candle that made it."""
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)

    assert "completed[cast(Any, completed.index) <= candidate.at]" in variant
    assert "regular[cast(Any, regular.index) <= signal_at]" in inspect.getsource(
        orb_base.OrbStrategy._scan
    )

    setup = spec_rows(engine)["Setup"]
    assert "The first completed" in setup
    assert "re-read on every pass rather than only its newest candle" in setup
    assert "has already run, and is passed over rather than chased" in setup

    entry = spec_rows(engine)["Entry"]
    assert "filling at the next executable price" in entry


@pytest.mark.parametrize(("engine", "minutes"), [("orb", 5), ("orb_momentum", 10)])
def test_each_engine_quotes_its_own_signal_age_bound(engine: str, minutes: int) -> None:
    """A bound moved in the bot must move on the page: the unit is that engine's candle."""
    bound = COMPOSER_SIGNAL_CANDLES_MAX[engine]
    module = orb if engine == "orb" else orb_momentum

    assert PAGE_SIGNAL_CANDLES_MAX[engine] == bound, "the page must quote the composer's bound"
    assert module.Strategy.signal_candles_max == bound, "the backtest class must agree"
    assert set(PAGE_SIGNAL_CANDLES_MAX) == set(COMPOSER_SIGNAL_CANDLES_MAX)
    assert "self.signal_candles_max" in inspect.getsource(orb_base.OrbStrategy._scan)

    setup = spec_rows(engine)["Setup"]
    assert f"one of the last {bound} completed candles" in setup
    assert f"{bound * minutes} minutes of the move" in setup


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_a_stop_the_market_has_reached_is_quoted_as_a_market_exit(engine: str) -> None:
    """A stop at or past the last price cannot rest, so the position leaves at market.

    This is a real exit path, not a detail: it is how a trade back at breakeven
    after its first scale-out actually closes, and the page described only the
    resting order until now.
    """
    protect = inspect.getsource(PortfolioStrategy._protect)

    assert "holding.direction == 1 and stop >= price" in protect
    assert "holding.direction == -1 and stop <= price" in protect
    assert "self._exit(holding)" in protect

    stop = spec_rows_full(engine)
    stop_row = next(row for row in stop if row["field"] == "Stop Loss")
    assert "cannot rest as an order" in stop_row["value"]
    assert "closed at market there and then" in stop_row["value"]
    assert "_protect" in stop_row["source"]


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_an_entry_already_through_its_stop_is_quoted_as_refused(engine: str) -> None:
    """Sizing on the live quote is what gives this guard teeth.

    Against the breakout candle's close it could never fire — that close is outside
    the range by construction and the stop sits inside it, for a long and a short
    alike. Against the live quote the market can have run back through the level
    before the order goes in, and then there is no position to open.
    """
    assert "direction * (price - stop) <= 0" in inspect.getsource(PortfolioStrategy._enter)
    assert "self._orb_price(candidate)" in inspect.getsource(PortfolioStrategy._run_orb_variant)

    entry = spec_rows(engine)["Entry"]
    assert "already run back through the stop" in entry
    assert "cannot be opened already past its own exit" in entry


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_confirmation_is_quoted_as_of_the_signal_candle(engine: str) -> None:
    """The gates confirm the breakout, so they read the moment that made it."""
    variant = inspect.getsource(PortfolioStrategy._run_orb_variant)
    confirm = inspect.getsource(PortfolioStrategy._orb_confirm)

    assert "completed[cast(Any, completed.index) <= candidate.at]" in variant
    assert "cast(Timestamp, frame.index[-1]).time()" in confirm

    confirmation = spec_rows(engine)["Confirmation"]
    assert "up to the signal candle's close" in confirmation
    assert "rather than as the scan runs" in confirmation


def test_the_entry_ceiling_is_quoted_where_it_applies() -> None:
    """Only ORB10 has one, so only ORB10's Entry row may mention it."""
    assert PAGE_ENTRY_EXTENSION_MAX == COMPOSER_ENTRY_EXTENSION_MAX
    assert "self._too_extended(candidate, price, span, limit)" in inspect.getsource(
        PortfolioStrategy._run_orb_variant
    )
    assert "self.entry_extension_max" in inspect.getsource(orb_base.OrbStrategy._scan)

    limit = COMPOSER_ENTRY_EXTENSION_MAX["orb_momentum"]
    assert limit is not None
    entry = spec_rows("orb_momentum")["Entry"]
    assert f"more than {limit * 100:g}% of the opening range beyond the breakout level" in entry

    assert "of the opening range beyond the breakout level" not in spec_rows("orb")["Entry"]


def test_no_engine_claims_a_macd_filter_it_does_not_run() -> None:
    """ORB10's MACD gate is off, so neither card may still advertise one."""
    assert orb.Strategy.uses_macd is False
    assert orb_momentum.Strategy.uses_macd is False
    assert all(arguments[3] is False for arguments in orb_variant_arguments().values())

    for engine in ORB_ENGINES:
        assert "MACD" not in spec_rows(engine)["Confirmation"], engine


@pytest.mark.parametrize("engine", ORB_ENGINES)
def test_the_reward_ratios_are_derived_from_the_multiples(engine: str) -> None:
    """The page formats the ratios from the tuple, so they cannot drift from it."""
    first, second, third = COMPOSER_TARGET_MULTIPLES[engine]

    reward = spec_rows(engine)["Min. R:R"]
    assert f"{first:g}:1 at the first target, then {second:g}:1 and {third:g}:1" in reward
    assert f"{first:g}x, {second:g}x and {third:g}x the risk actually taken" in reward


@pytest.mark.parametrize(("engine", "minutes"), [("orb", 5), ("orb_momentum", 10)])
def test_the_trail_atr_is_quoted_as_reaching_across_sessions(engine: str, minutes: int) -> None:
    """The ATR window spans days, and the page has to say so.

    _manage_orb asks for five calendar days of candles and filters them to regular
    hours only — not to today — so a 14-period ATR necessarily reads prior sessions.
    Two things follow that a reader would otherwise be surprised by: each session's
    first candle sits directly after the previous session's last, so the overnight
    gap counts as a true range; and the 15-candle minimum is satisfied long before
    the trail can arm, rather than holding it back.
    """
    manage = inspect.getsource(PortfolioStrategy._manage_orb)

    assert "now - timedelta(days=5)" in manage, "the window is days, not one session"
    assert 'between_time("09:30", "15:59")' in manage, "regular hours, not one date"
    assert f"len(frame) < {ORB_TRAIL_BARS_MIN}" in manage

    stop = spec_rows(engine)["Stop Loss"]
    assert f"ATR(14) is calculated from {minutes}-minute candles across trading sessions" in stop
    assert "prior-session bars as needed" in stop
    assert "overnight gaps contribute to true range" in stop
    assert f"At least {ORB_TRAIL_BARS_MIN} completed {minutes}-minute candles" in stop
    assert "normally already be satisfied" in stop
