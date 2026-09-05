from typing import Any, cast

from pandas import DataFrame, Series

from .shared import average_share_volume


TFB_RISK_MAX = 0.005
TFB_POSITIONS_MAX = 5
TFB_PRICE_USD_MIN = 5.0
TFB_VOLUME_SHARES_MIN = 1_000_000.0
TFB_VOLUME_SESSIONS = 20


def is_tfb_market_ready(frame: DataFrame) -> bool:
    closes = cast(Series, frame["close"])
    if closes.empty:
        return False
    price = float(cast(Any, closes).iloc[-1])
    if price < TFB_PRICE_USD_MIN:
        return False
    return average_share_volume(frame, TFB_VOLUME_SESSIONS) >= TFB_VOLUME_SHARES_MIN
