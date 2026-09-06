from .config import settings


def millions(value: float) -> str:
    return f"${value / 1_000_000:g}M"


def percent(fraction: float) -> str:
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


UNIVERSE = (
    f"US equities screened daily: market cap {millions(settings.universe.market_cap_usd_min)} or "
    f"more, share price ${settings.universe.price_usd_min:.0f} or more, 3-month average daily "
    f"turnover {millions(settings.universe.turnover_usd_min)} or more, and tradable and "
    "fractionable at Alpaca."
)
