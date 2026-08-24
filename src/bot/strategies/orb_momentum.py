from bot.strategies.orb_base import OrbStrategy


class Strategy(OrbStrategy):
    candle_minutes = 10
    volume_multiple = 1.5
    uses_macd = True
    risk_fraction_max = None
