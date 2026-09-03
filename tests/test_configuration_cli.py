import re
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from bot.types import (
    PAUSED_STRATEGIES,
    STRATEGY_LABELS,
    RuntimeSnapshot,
    Settings,
    active_strategies,
    published_roster,
)
from cli import __main__ as cli
from tests.world.index import web_settings


def test_strategies_are_normalized_when_configuration_is_valid() -> None:
    settings = Settings(_env_file=None, strategies="sma, orb")

    assert settings.strategy_names == ["sma", "orb"]
    assert settings.trading_configuration.position_fraction_max == 0.2


@pytest.mark.parametrize("strategies", ["", "sma,sma", "unknown"])
def test_configuration_is_rejected_when_strategy_selection_is_invalid(strategies: str) -> None:
    with pytest.raises(ValidationError, match="STRATEGIES|unknown strategies"):
        Settings(_env_file=None, strategies=strategies)


DEPLOYMENT = Path(".railway/railway.ts")


def deployed_strategies() -> list[str]:
    """The roster the deployed bot is started with, read from the Railway config."""
    match = re.search(r'STRATEGIES:\s*"([^"]*)"', DEPLOYMENT.read_text())
    assert match is not None, "railway.ts no longer declares STRATEGIES"
    return [value.strip() for value in match.group(1).split(",") if value.strip()]


def register_states() -> dict[str, str]:
    """The state each engine's README register block declares, keyed by its label."""
    states: dict[str, str] = {}
    for block in Path("README.md").read_text().split("#### ")[1:]:
        found = re.search(r"state = (\w+)", block)
        if found is not None:
            states[block.splitlines()[0].strip()] = found.group(1)
    return states


def test_the_deployment_starts_every_engine_that_is_not_paused() -> None:
    """Unpausing in code does nothing if the bot is never told to load the engine.

    Two switches decide whether an engine trades: PAUSED_STRATEGIES here, and
    the STRATEGIES the deployed bot is started with. An engine whose register
    reads enabled but that the bot never loads is a register that lies.
    """
    deployed = deployed_strategies()

    assert set(deployed).issubset(STRATEGY_LABELS), "unknown engine in the deployed roster"
    # noop is a placeholder, never something the deployment should carry.
    live = {name for name in STRATEGY_LABELS if name not in PAUSED_STRATEGIES and name != "noop"}
    assert live.issubset(set(deployed)), f"not started by the deployment: {live - set(deployed)}"


def test_the_register_state_matches_the_pause_switch() -> None:
    """The page and the README both read paused/enabled off this one frozenset."""
    states = register_states()

    for name, label in STRATEGY_LABELS.items():
        if name == "noop":
            continue
        expected = "paused" if name in PAUSED_STRATEGIES else "enabled"
        assert states[label] == expected, f"{label} register reads {states[label]}"


def test_paused_strategies_are_registered_strategy_names() -> None:
    assert sorted(PAUSED_STRATEGIES) == ["orb_momentum"]
    assert PAUSED_STRATEGIES.issubset(STRATEGY_LABELS)


def test_the_momentum_engine_is_switched_on() -> None:
    """It opens new positions again, so its register must not read paused."""
    assert "sma" not in PAUSED_STRATEGIES
    assert active_strategies(["sma"]) == ["sma"]


def test_the_tfb_engine_is_switched_on() -> None:
    """Its register reads enabled, so it must take new entries."""
    assert "tfb_50" not in PAUSED_STRATEGIES
    assert active_strategies(["tfb_50"]) == ["tfb_50"]


def test_published_roster_names_paused_engines_without_decorating_their_labels() -> None:
    """The label has to stay resolvable; pause travels beside it, not inside it.

    Spelling the state into the label leaves an entry that names no engine, and
    the dashboard then reads that engine as absent rather than paused.
    """
    held = sorted(PAUSED_STRATEGIES)[0]
    labels, paused = published_roster(["orb", held])

    assert labels == [STRATEGY_LABELS["orb"], STRATEGY_LABELS[held]]
    assert paused == [STRATEGY_LABELS[held]]
    assert set(paused).issubset(labels)


def test_published_roster_reports_no_paused_engines_when_none_are_selected() -> None:
    assert published_roster(["orb"]) == ([STRATEGY_LABELS["orb"]], [])


def test_snapshot_without_a_paused_field_still_validates() -> None:
    """Bot and web deploy separately, so one can be reporting before the other ships."""
    body = (
        '{"run_id":"8f558d63-d47d-4a5f-8f77-95b0bf55a591","sequence":1,"status":"running",'
        '"strategies":["ORB (5-minute)"],"started_at":"2026-09-01T13:30:00Z",'
        '"heartbeat_at":"2026-09-01T13:30:05Z","configuration":{"fractional_orders":true,'
        '"position_fraction_max":0.1,"risk_per_day_max":0.02,"risk_per_trade_max":0.005},'
        '"events":[]}'
    )

    assert RuntimeSnapshot.model_validate_json(body).paused == []


def test_paused_strategies_take_no_entries_when_selection_includes_them() -> None:
    settings = Settings(_env_file=None, strategies="orb,sma,tfb_50,orb_momentum")

    assert settings.strategy_names == ["orb", "sma", "tfb_50", "orb_momentum"]
    assert active_strategies(settings.strategy_names) == ["orb", "sma", "tfb_50"]


def test_configuration_is_rejected_when_export_settings_are_incomplete() -> None:
    with pytest.raises(ValidationError, match="state export URL and secret must be set together"):
        Settings(_env_file=None, state_export_url="https://example.com/internal/state")


def test_configuration_is_rejected_when_trade_risk_exceeds_daily_risk() -> None:
    with pytest.raises(ValidationError, match="risk per trade must not exceed risk per day"):
        Settings(_env_file=None, risk_per_day_max=0.01, risk_per_trade_max=0.02)


def test_web_configuration_is_accepted_when_callback_matches_base_url() -> None:
    settings = web_settings()

    assert settings.allowed_railway_emails == {"operator@example.com"}
    assert settings.alpaca_is_paper is True


def test_web_configuration_is_rejected_when_callback_differs_from_base_url() -> None:
    with pytest.raises(ValidationError, match="RAILWAY_OAUTH_REDIRECT_URI must match"):
        web_settings(RAILWAY_OAUTH_REDIRECT_URI="https://other.test/callback")


def test_backtest_dispatches_when_cli_selection_is_valid() -> None:
    calls: list[tuple[object, ...]] = []
    runner = CliRunner()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cli.backtest, "run", lambda *arguments: calls.append(arguments))
        result = runner.invoke(
            cli.app,
            [
                "backtest",
                "--strategy",
                "sma",
                "--symbols",
                "AAPL, MSFT",
                "--start",
                "2025-01-01",
                "--end",
                "2026-01-01",
            ],
        )

    assert result.exit_code == 0
    assert calls == [
        (
            "sma",
            datetime(2025, 1, 1),
            datetime(2026, 1, 1),
            ["AAPL", "MSFT"],
        )
    ]


def test_cli_selection_is_rejected_when_single_strategy_command_receives_multiple() -> None:
    result = CliRunner().invoke(cli.app, ["backtest", "--strategy", "sma,orb"])

    assert result.exit_code == 2
    assert "strategy must select exactly one strategy" in result.output
