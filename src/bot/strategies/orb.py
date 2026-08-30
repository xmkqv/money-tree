from bot.strategies.orb_base import OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 5
    volume_multiple = 1.3
    uses_macd = False
    risk_fraction_max = 0.01
    target_multiples = (1.5, 2.5, 4.0)
    # The newest completed candle, or the one before it — ten minutes of a move.
    signal_candles_max = 2
