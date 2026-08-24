from datetime import datetime

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from bot.types import Settings
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
