"""Hold the strategy page to the code it claims to describe.

The page exists so the rules can be checked against intent, which is worth
nothing if the page and the bot can drift apart. Every number quoted on it is
pinned here to the literal in the module that actually runs, so moving a
threshold in the bot fails a test instead of leaving the page confidently wrong.
"""

import ast
import inspect
from datetime import time
from pathlib import Path
from typing import Any

import pytest

from bot.portfolio import ORB_CLOSE_DEADLINE
from bot.portfolio import Strategy as PortfolioStrategy
from bot.strategies import orb, orb_momentum, sma, tfb_50
from bot.types import TradingConfiguration
from tests.test_ledger import _snapshot
from ui.dashboard import bot_state
from ui.strategies import (
    FIELDS,
    ORB_RISK_CEILING,
    POSITION_FRACTION_CEILING,
    POSITIONS_MAX,
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
