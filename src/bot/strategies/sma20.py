# 20SMA. A daily pullback-and-reclaim entry, sized in dollars rather than in
# risk, scaled out at fixed gains, and trailed on 4-hour candles once the trade
# is far enough ahead to protect. Every rule here is read from one register
# entry, so the numbers live together rather than scattered across the bot.

SMA20_CAP_USD_MIN = 2_000_000_000.0
SMA20_POSITIONS_MAX = 5
SMA20_NOTIONAL_USD = 1_000.0
# The stop the position opens with: 10% below the fill.
SMA20_STOP_FRACTION = 0.10
# The gain that moves the stop to breakeven and starts the trailing stop.
SMA20_BREAKEVEN_GAIN = 0.10
# Gains that take profit, and the share of the position each one sells. What is
# left after both runs on the trailing stop alone.
SMA20_TARGET_GAINS = (0.15, 0.25)
SMA20_TARGET_FRACTIONS = (0.50, 0.25)
SMA20_TRAIL_ATR_MULTIPLE = 1.5
SMA20_TRAIL_HOURS = 4
# ATR(14) needs fifteen completed candles to read: fourteen ranges and the close
# before them.
SMA20_TRAIL_BARS_MIN = 15
SMA20_TRAIL_HISTORY_DAYS = 30
# Prices and thresholds are floating point: 100 * 1.1 lands a hair above 110, so
# a gain met exactly would otherwise read as not met. A billionth of the level
# closes that gap, and is far below anything a price is quoted in.
SMA20_GAIN_TOLERANCE = 1e-9


def is_sma20_market_ready(market_cap: float | None) -> bool:
    return market_cap is not None and market_cap >= SMA20_CAP_USD_MIN


def is_gain_reached(price: float, entry: float, gain: float) -> bool:
    """Whether the price is that fraction above the entry, counting the level itself."""
    level = entry * (1.0 + gain)
    return price >= level - abs(level) * SMA20_GAIN_TOLERANCE
