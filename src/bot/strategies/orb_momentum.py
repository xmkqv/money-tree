from bot.strategies.orb_base import OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 10
    volume_multiple = 1.5
    uses_macd = False
    risk_fraction_max = None
    target_multiples = (2.0, 3.0, 5.0)
    # The newest completed candle, or the one before it — twenty minutes of a move.
    signal_candles_max = 2
    # A quarter of the opening range beyond the breakout level is as far past it as
    # an entry may be paid for.
    entry_extension_max = 0.25
