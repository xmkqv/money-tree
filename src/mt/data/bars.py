import itertools
from datetime import UTC, datetime, timedelta

import httpx2
from pandas import DataFrame, DatetimeIndex
from pydantic import AwareDatetime, Field

from mt.exchange import TRADING_ZONE
from mt.frames import OHLCV_COLUMNS
from mt.rules.sections import BarsSection
from mt.rules.values import DataFeedName, Timeframe

from .asset import Asset, AssetType
from .http import ExceedPagesError, Payload, get_bytes


class Bar(Payload):
    opened_at: AwareDatetime = Field(alias="t")
    open: float = Field(alias="o")
    high: float = Field(alias="h")
    low: float = Field(alias="l")
    close: float = Field(alias="c")
    volume: float = Field(alias="v")


class _BarsPage(Payload):
    bars: dict[str, list[Bar]] | None = None
    next_page_token: str | None = None


BAR_PATHS: dict[AssetType, str] = {
    AssetType.STOCK: "/v2/stocks/bars",
    AssetType.CRYPTO: "/v1beta3/crypto/us/bars",
    AssetType.OPTION: "/v1beta1/options/bars",
}


def check_supported_asset(asset: Asset) -> None:
    if asset.asset_type not in BAR_PATHS:
        raise ValueError(f"historical bars do not support {asset.asset_type}")


def stock_feed(configuration: BarsSection, timeframe: Timeframe) -> DataFeedName:
    return configuration.daily_feed if timeframe.endswith("Day") else configuration.intraday_feed


def feed_end(configuration: BarsSection, feed: DataFeedName, end: datetime) -> datetime:
    if feed != "sip":
        return end
    return min(end, datetime.now(UTC) - timedelta(minutes=configuration.sip_delay_minutes))


def bar_frame(bars: list[Bar]) -> DataFrame:
    frame = DataFrame([bar.model_dump() for bar in bars]).set_index("opened_at")
    index = DatetimeIndex(frame.index).tz_convert(TRADING_ZONE)
    columns = frame.set_axis(index)[list(OHLCV_COLUMNS)]
    return columns.astype(float).sort_index()


class BarsClientAlpaca:
    def __init__(self, client: httpx2.AsyncClient, configuration: BarsSection) -> None:
        self._client = client
        self._configuration = configuration

    async def bars(
        self,
        assets: list[Asset],
        timeframe: Timeframe,
        start: datetime,
        end: datetime | None = None,
        *,
        limit: int,
        pages_max: int,
    ) -> dict[Asset, list[Bar]]:
        groups: dict[AssetType, dict[str, Asset]] = {}
        rows: dict[Asset, list[Bar]] = {asset: [] for asset in assets}
        for asset in rows:
            check_supported_asset(asset)
            symbols = groups.setdefault(asset.asset_type, {})
            symbols[str(asset)] = asset
        for asset_type, symbols in groups.items():
            params: dict[str, object] = {
                "timeframe": timeframe,
                "start": start,
                "limit": limit,
                "sort": "asc",
            }
            until = end
            path = BAR_PATHS[asset_type]
            batch_size = self._configuration.symbols_per_request
            if asset_type == AssetType.STOCK:
                feed = stock_feed(self._configuration, timeframe)
                params.update(feed=feed, adjustment="all")
                if until is not None:
                    until = feed_end(self._configuration, feed, until)
            elif asset_type == AssetType.OPTION:
                batch_size = min(batch_size, self._configuration.options_per_request)
            if until is not None:
                if until < start:
                    continue
                params["end"] = until
            for batch in itertools.batched(symbols, batch_size, strict=False):
                query = {**params, "symbols": ",".join(batch)}
                page_count = 0
                while True:
                    page = _BarsPage.model_validate_json(await get_bytes(self._client, path, query))
                    for symbol, bars in (page.bars or {}).items():
                        rows[symbols[symbol]].extend(bars)
                    page_count += 1
                    if not page.next_page_token:
                        break
                    if page_count >= pages_max:
                        raise ExceedPagesError("Bars exceed the configured page limit")
                    query["page_token"] = page.next_page_token
        return rows

    async def series(
        self,
        asset: Asset,
        timeframe: Timeframe,
        start: datetime,
        end: datetime | None = None,
        *,
        limit: int,
        pages_max: int,
    ) -> list[Bar]:
        rows = await self.bars([asset], timeframe, start, end, limit=limit, pages_max=pages_max)
        return rows[asset]
