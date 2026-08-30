from bot.strategies.orb_base import OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 10
    volume_multiple = 1.5
    uses_macd = True
    risk_fraction_max = None
    # Half a range, one range and two ranges beyond the breakout level, written as
    # multiples of the risk a fill at that level would take. See _filled_targets.
    target_multiples = (2.0, 4.0, 8.0)
