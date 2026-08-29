"""What each engine actually does, written against the code that runs it.

The page this feeds exists so the rules can be checked against intent, which
only works if it describes the live path. `bot/trade.py` runs
`bot.portfolio.Strategy`, and that composer carries its own copy of every
threshold rather than importing the single-strategy classes in
`bot/strategies/`, so the numbers here are read from `portfolio.py`.

Every figure quoted below is asserted against the source in
tests/test_strategy_spec.py. A threshold changed in the bot without this table
following it fails those tests rather than quietly leaving the page wrong.
"""

from datetime import time
from typing import Any, TypedDict

from bot.types import STRATEGY_LABELS, TradingConfiguration


FIELDS = [
    "Market",
    "Sentiment",
    "Direction",
    "Range",
    "Setup",
    "Confirmation",
    "Entry",
    "Stop Loss",
    "Max Risk",
    "Min. R:R",
    "Exit Rule",
    "Emergency Exit",
]

# Defaults from bot/types.py Settings, used only when no bot is reporting.
RISK_PER_TRADE_DEFAULT = 0.005
RISK_PER_DAY_DEFAULT = 0.02
POSITION_FRACTION_DEFAULT = 0.20

# portfolio.py caps the notional fraction at this regardless of configuration.
POSITION_FRACTION_CEILING = 0.10
POSITIONS_MAX = 10
ORB_RISK_CEILING = 0.01

# Breakout figures the composer hard-codes: relative volume needs exactly this
# many earlier sessions to compare against, the trail reads this ATR multiple
# off this many completed candles, and a position worth less than this is not
# opened at all. Each is pinned to its source in tests/test_strategy_spec.py.
ORB_HISTORY_SESSIONS = 20
ORB_TRAIL_ATR_MULTIPLE = 1.5
ORB_TRAIL_BARS_MIN = 15
POSITION_NOTIONAL_MIN = 1

# When each engine can open a trade, from portfolio.py. The daily pair is
# checked once a session before 09:40; the two breakout engines scan on their
# own candle boundary until 10:30. Positions already open keep being managed
# after these windows close — this is when a NEW trade can start.
ENTRY_WINDOWS: dict[str, tuple[time, time]] = {
    "orb": (time(9, 35), time(10, 30)),
    "orb_momentum": (time(9, 40), time(10, 30)),
    "sma": (time(9, 30), time(9, 40)),
    "tfb_50": (time(9, 30), time(9, 40)),
}


def entry_windows() -> dict[str, dict[str, str]]:
    """The windows as plain HH:MM, for the page to compare against the clock."""
    return {
        engine: {"from": f"{opens:%H:%M}", "to": f"{closes:%H:%M}"}
        for engine, (opens, closes) in ENTRY_WINDOWS.items()
    }


UNIVERSE = (
    "US equities screened daily: market cap $500M or more, 3-month average "
    "daily volume 1M shares or more, and tradable and fractionable at Alpaca."
)


class Row(TypedDict):
    field: str
    value: str
    source: str


class StrategyCard(TypedDict):
    id: str
    short: str
    label: str
    kind: str
    rows: list[Row]


def _pct(fraction: float) -> str:
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _orb(minutes: int, volume_multiple: float, uses_macd: bool, per_trade: float) -> list[Row]:
    opening_end = "09:34" if minutes == 5 else "09:39"
    first_scan = "09:35" if minutes == 5 else "09:40"
    risk_cap = ORB_RISK_CEILING if minutes == 5 else per_trade

    confirmation = (
        f"Volume traded so far today is at least {volume_multiple:g}x the "
        f"{ORB_HISTORY_SESSIONS}-session average at the same time of day, and that average "
        f"session turns over at least 1M shares. All {ORB_HISTORY_SESSIONS} earlier sessions "
        "must be there to compare against — a shorter history is not a weaker signal, it is "
        "no confirmation at all, and the breakout is passed over."
    )
    if uses_macd:
        confirmation += " MACD (12/26/9) must also be rising for a long, falling for a short."

    if minutes == 5:
        targets = (
            "Targets are re-cut from the filled price: 1.5x, 2.5x and 4x the risk actually "
            "taken, so a fill away from the signal price carries them with it."
        )
        reward = "1.5:1 at the first target, then 2.5:1 and 4:1."
    else:
        targets = "Targets sit half a range, one range and two ranges beyond the breakout level."
        reward = (
            "About 2:1 at the first target — half a range of reward against a quarter "
            "of a range of risk."
        )

    return [
        Row(field="Market", value=UNIVERSE, source="portfolio.py · _discover_eligible_symbols"),
        Row(
            field="Sentiment",
            value="None. This engine takes signals whatever the wider market is doing.",
            source="portfolio.py · _run_orb_variant",
        ),
        Row(
            field="Direction",
            value="Long and short. A short is skipped when the broker will not lend the stock.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="Range",
            value=f"The opening range is 09:30 to {opening_end} — the first {minutes}-minute "
            "candle. Its high and low set the levels for the day.",
            source="portfolio.py · _run_orb_variant",
        ),
        Row(
            field="Setup",
            value=f"A completed {minutes}-minute candle closes above the range high (long) or "
            f"below the range low (short) — a candle still forming never signals. Checked every "
            f"{minutes} minutes from {first_scan} to 10:30, at most once per stock per day. "
            "Once either breakout engine has traded a stock, both leave it alone for the rest "
            "of the session.",
            source="portfolio.py · _run_orb_variant",
        ),
        Row(field="Confirmation", value=confirmation, source="portfolio.py · _orb_confirm"),
        Row(
            field="Entry",
            value="Market order at the breakout candle's close, good for the day only. It is "
            "passed over if another engine already holds the stock, if the account is at its "
            "position cap or fully invested, or if the size that fits the risk limits comes to "
            f"less than ${POSITION_NOTIONAL_MIN}.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="Stop Loss",
            value="Three quarters of the way back into the opening range for a long, a quarter "
            "for a short. Once the first target is hit the stop trails "
            f"{ORB_TRAIL_ATR_MULTIPLE:g}x the 14-period ATR behind the best price the trade has "
            "seen, and never moves back "
            f"past the entry price. The trail needs {ORB_TRAIL_BARS_MIN} completed candles to read "
            "that ATR, and holds where it is until they exist. The level rests as a live order at "
            "the broker, replaced whenever it moves and re-sent if it ever stops covering the "
            "whole position.",
            source="portfolio.py · _run_orb_variant, _manage_orb, _resync_stops",
        ),
        Row(
            field="Max Risk",
            value=f"{_pct(risk_cap)} of account equity per trade"
            + (
                f" — this engine states its own {_pct(ORB_RISK_CEILING)} in the register, so "
                f"that governs instead of the configured {_pct(per_trade)}."
                if minutes == 5
                else " (the configured per-trade limit; this engine states none of its own)."
            )
            + f" A single position is never worth more than {_pct(POSITION_FRACTION_CEILING)} "
            "of equity.",
            source="portfolio.py · _enter",
        ),
        Row(field="Min. R:R", value=f"{reward} {targets}", source="portfolio.py · on_filled_order"),
        Row(
            field="Exit Rule",
            value="Scaled out in three: half the position as first filled at the first target, "
            "a quarter of it at the second, the remainder at the third. The trailing stop "
            "takes whatever is left if price turns first.",
            source="portfolio.py · _manage_orb",
        ),
        Row(
            field="Emergency Exit",
            value="Everything is closed before 15:55 — the exit is sent at 15:54 so the "
            "market order fills in time, and this engine never holds overnight. The "
            "daily loss limit closes all positions and stops new entries for the rest of "
            "the day.",
            source="portfolio.py · _manage, _daily_loss_reached",
        ),
    ]


def _daily(engine: str, stop_multiple: float, per_trade: float) -> list[Row]:
    if engine == "sma":
        setup = (
            "The closing price crosses back above its 20-day average while already above "
            "both the 50-day and 200-day averages. Needs 200 sessions of history."
        )
        confirmation = "RSI (14) between 50 and 70, and ADX (14) at 25 or above."
        entry = (
            "Market buy before 09:40, checked once a day. Skipped if the company reports "
            "earnings within 5 days, or if its earnings date cannot be read."
        )
        setup_source = "strategies/shared.py · momentum_entry"
        entry_source = "portfolio.py · _run_sma"
    else:
        setup = (
            "The closing price is above its 50-day average, that average is higher than it "
            "was 4 sessions ago, and the close beats the previous session's high."
        )
        confirmation = "ADX (14) at 20 or above."
        entry = (
            "Market buy before 09:40, checked once a day. Upcoming earnings do not block "
            "an entry for this engine."
        )
        setup_source = "strategies/shared.py · tfb_entry"
        entry_source = "portfolio.py · _run_tfb"

    return [
        Row(field="Market", value=UNIVERSE, source="portfolio.py · _discover_eligible_symbols"),
        Row(
            field="Sentiment",
            value="The S&P 500 must be trading above its own 20-day average. If it is not, no "
            "daily engine takes a position that day.",
            source="portfolio.py · _run_daily",
        ),
        Row(field="Direction", value="Long only.", source="portfolio.py · _enter"),
        Row(
            field="Range",
            value="Not used. This engine reads daily candles and has no opening range.",
            source="portfolio.py · _run_daily",
        ),
        Row(field="Setup", value=setup, source=setup_source),
        Row(field="Confirmation", value=confirmation, source=setup_source),
        Row(field="Entry", value=entry, source=entry_source),
        Row(
            field="Stop Loss",
            value=f"{stop_multiple:g}x the 14-period ATR below the entry price, then trailing "
            f"{stop_multiple:g}x ATR below the highest close reached since entry. The stop "
            "only ever moves up.",
            source="portfolio.py · _manage_daily",
        ),
        Row(
            field="Max Risk",
            value=f"{_pct(per_trade)} of account equity per trade, and a single position is "
            f"never worth more than {_pct(POSITION_FRACTION_CEILING)} of equity.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="Min. R:R",
            value="No fixed target. The trade is held while the trend holds and closed on the "
            "exit rule below, so no reward-to-risk ratio is set in advance.",
            source="portfolio.py · _manage_daily",
        ),
        Row(
            field="Exit Rule",
            value="Closed when the price falls through the trailing stop, or when the close "
            "drops below its 20-day average with RSI (14) under 50.",
            source="strategies/shared.py · signal_exit",
        ),
        Row(
            field="Emergency Exit",
            value="Closed at 15:50 on the session before the company reports earnings. The "
            "daily loss limit closes all positions and stops new entries for the rest of "
            "the day.",
            source="portfolio.py · _manage_daily, _daily_loss_reached",
        ),
    ]


def portfolio_rules(daily_loss: float) -> list[Row]:
    """Limits the composer applies across every engine at once."""
    return [
        Row(
            field="Position cap",
            value=f"At most {POSITIONS_MAX} positions open at once, counting orders already "
            "placed but not yet filled.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="Exposure",
            value="The total value held never exceeds account equity, so the account never "
            "trades on borrowed money.",
            source="portfolio.py · _enter",
        ),
        Row(
            field="One owner per stock",
            value="Only one engine holds a given stock at a time; the others skip it while "
            "that position is open.",
            source="portfolio.py · _claimed",
        ),
        Row(
            field="Daily loss limit",
            value=f"If equity falls {_pct(daily_loss)} below the previous close, every position "
            "is closed and no new trade is opened until the next session.",
            source="portfolio.py · _daily_loss_reached",
        ),
    ]


def strategy_spec(configuration: TradingConfiguration | None) -> dict[str, Any]:
    """The rule sheet, with the live risk settings folded into the wording.

    Passing the bot's reported configuration keeps the risk figures honest: they
    are environment settings, so quoting the repository defaults would describe
    a deployment that may not be the running one.
    """
    per_trade = configuration.risk_per_trade_max if configuration else RISK_PER_TRADE_DEFAULT
    daily_loss = configuration.risk_per_day_max if configuration else RISK_PER_DAY_DEFAULT

    cards: list[StrategyCard] = [
        StrategyCard(
            id="orb",
            short="ORB5",
            label=STRATEGY_LABELS["orb"],
            kind="Intraday breakout",
            rows=_orb(5, 1.3, False, per_trade),
        ),
        StrategyCard(
            id="orb_momentum",
            short="ORB10",
            label=STRATEGY_LABELS["orb_momentum"],
            kind="Intraday breakout",
            rows=_orb(10, 1.5, True, per_trade),
        ),
        StrategyCard(
            id="sma",
            short="Momentum",
            label=STRATEGY_LABELS["sma"],
            kind="Daily trend",
            rows=_daily("sma", 1.5, per_trade),
        ),
        StrategyCard(
            id="tfb_50",
            short="TFB-50",
            label=STRATEGY_LABELS["tfb_50"],
            kind="Daily trend",
            rows=_daily("tfb_50", 2.0, per_trade),
        ),
    ]
    return {
        "fields": FIELDS,
        "strategies": cards,
        "portfolio": portfolio_rules(daily_loss),
        "configured": configuration is not None,
    }
