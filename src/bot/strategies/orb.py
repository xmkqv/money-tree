from bot.strategies.orb_base import ORB_RISK_CEILING, OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 5
    volume_multiple = 1.3
    uses_macd = False
    risk_fraction_max = ORB_RISK_CEILING
    target_multiples = (1.5, 2.5, 4.0)
    # The newest completed candle, or the one before it — ten minutes of a move.
    signal_candles_max = 2
    # No ceiling on how far past the level an entry may be paid for.
    entry_extension_max = None
