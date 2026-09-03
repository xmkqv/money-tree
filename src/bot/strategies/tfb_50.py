from typing import Any, cast

from pandas import DataFrame, Series

from .shared import average_dollar_volume


TFB_RISK_MAX = 0.005
TFB_POSITIONS_MAX = 5
TFB_PRICE_USD_MIN = 5.0
TFB_TURNOVER_USD_MIN = 20_000_000.0
TFB_TURNOVER_SESSIONS = 20


def is_tfb_market_ready(frame: DataFrame) -> bool:
    closes = cast(Series, frame["close"])
    if closes.empty:
        return False
    price = float(cast(Any, closes).iloc[-1])
    if price < TFB_PRICE_USD_MIN:
        return False
    return average_dollar_volume(frame, TFB_TURNOVER_SESSIONS) >= TFB_TURNOVER_USD_MIN
