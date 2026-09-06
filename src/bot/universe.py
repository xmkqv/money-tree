MARKET_CAP_USD_MIN = 500_000_000.0
PRICE_USD_MIN = 5.0
TURNOVER_USD_MIN = 20_000_000.0


def millions(value: float) -> str:
    return f"${value / 1_000_000:g}M"


def percent(fraction: float) -> str:
    text = f"{fraction * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


UNIVERSE = (
    f"US equities screened daily: market cap {millions(MARKET_CAP_USD_MIN)} or more, share "
    f"price ${PRICE_USD_MIN:.0f} or more, 3-month average daily turnover "
    f"{millions(TURNOVER_USD_MIN)} or more, and tradable and fractionable at Alpaca."
)
