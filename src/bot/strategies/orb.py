from bot.strategies.orb_base import OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 5
    volume_multiple = 1.3
    uses_macd = False
    risk_fraction_max = 0.01
