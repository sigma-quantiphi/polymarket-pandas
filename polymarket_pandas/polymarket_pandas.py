import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import pandas as pd

orderbook_meta = [
    "market",
    "asset_id",
    "timestamp",
    "hash",
    "min_order_size",
    "tick_size",
    "neg_risk",
]


def filter_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """
    Remove empty / None values so we don't send noisy query params.
    Lists are kept as-is, scalars must be non-null.
    """
    if not params:
        return {}
    cleaned: dict[str, Any] = {}
    for k, v in params.items():
        if v is None or v == "":
            continue
        if isinstance(v, list):
            cleaned[k] = v
        else:
            if pd.notnull(v):
                cleaned[k] = v
    return cleaned


@dataclass
class PolymarketPandas:
    """
    Read-only Polymarket client returning Pandas DataFrames.
    Uses public Gamma/Data/CLOB endpoints (no auth).
    """

    data_url: str = "https://data-api.polymarket.com/"
    gamma_url: str = "https://gamma-api.polymarket.com/"
    clob_url: str = "https://clob.polymarket.com/"


    api_key: Optional[str] = field(default=os.getenv("POLYMARKET_API_KEY"), repr=False)
    api_secret: Optional[str] = field(default=os.getenv("POLYMARKET_API_SECRET"), repr=False)
    api_passphrase: Optional[str] = field(default=os.getenv("POLYMARKET_API_PASSPHRASE"), repr=False)


    numeric_columns: tuple[str, ...] = field(
        default=(
            "bestAsk",
            "bestBid",
            "lastTradePrice",
            "liquidity",
            "liquidityAmm",
            "liquidityNum",
            "lowerBound",
            "min_order_size",
            "oneDayPriceChange",
            "oneHourPriceChange",
            "oneMonthPriceChange",
            "oneWeekPriceChange",
            "oneYearPriceChange",
            "price",
            "rewardsMaxSpread",
            "rewardsMinSize",
            "size",
            "spread",
            "tick_size",
            "upperBound",
            "volume",
            "volume1mo",
            "volume1moAmm",
            "volume1moClob",
            "volume1wk",
            "volume1wkAmm",
            "volume1wkClob",
            "volume1yr",
            "volume1yrAmm",
            "volume1yrClob",
            "volume24hr",
            "volumeNum",
        )
    )
    datetime_columns: set[str] = field(
        default=(
            "closedTime",
            "createdAt",
            "endDate",
            "endDateIso",
            "startDate",
            "timestamp",
            "updatedAt",
        )
    )
    bool_columns: set[str] = field(
        default=(
            "active",
            "closed",
            "archived",
            "restricted",
            "hasReviewedDates",
            "readyForCron",
            "fpmmLive",
            "ready",
            "funded",
            "cyom",
            "competitive",
            "pagerDutyNotificationEnabled",
            "approved",
            "clearBookOnStart",
            "manualActivation",
            "negRiskOther",
            "pendingDeployment",
            "deploying",
            "rfqEnabled",
            "holdingRewardsEnabled",
            "feesEnabled",
            "notificationsEnabled",
            "wideFormat",
        )
    )


    def __post_init__(self) -> None:
        self._client = httpx.Client()

    def _get(self, base: str, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(f"{base}{path}", params=filter_params(params))
        resp.raise_for_status()
        return resp.json()

    def _gamma(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._get(self.gamma_url, path, params)

    def _data(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._get(self.data_url, path, params)

    def _clob(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._get(self.clob_url, path, params)


    def _normalize(self, payload: Any) -> pd.DataFrame:
        """
        Normalize list/dict payloads to a DataFrame using pandas.json_normalize
        (preferred over manual loops).
        """
        if isinstance(payload, list):
            df = pd.json_normalize(payload)
        elif isinstance(payload, dict):
            if "data" in payload and isinstance(payload["data"], list):
                df = pd.json_normalize(payload["data"])
            else:
                df = pd.json_normalize(payload)
        else:
            df = pd.DataFrame()
        return df

    def _postprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        cols = df.columns
        num_cols = [c for c in cols if c in self.numeric_columns]
        dt_cols = [c for c in cols if c in self.datetime_columns]
        bool_cols = [c for c in cols if c in self.bool_columns]
        if num_cols:
            df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")
        if dt_cols:
            df[dt_cols] = df[dt_cols].apply(pd.to_datetime, utc=True, errors="coerce")
        if bool_cols:
            df[bool_cols] = df[bool_cols].astype(bool)
        return df


    def get_markets(
        self,
        limit: Optional[int] = 500,
        offset: Optional[int] = None,
        order: Optional[list[str]] = None,
        ascending: Optional[bool] = None,
        id: Optional[list[int]] = None,
        slug: Optional[list[str]] = None,
        clob_token_ids: Optional[list[str]] = None,
        condition_ids: Optional[list[str]] = None,
        market_maker_address: Optional[list[str]] = None,
        liquidity_num_min: Optional[float] = None,
        liquidity_num_max: Optional[float] = None,
        volume_num_min: Optional[float] = None,
        volume_num_max: Optional[float] = None,
        start_date_min: Optional[str] = None,
        start_date_max: Optional[str] = None,
        end_date_min: Optional[str] = None,
        end_date_max: Optional[str] = None,
        tag_id: Optional[int] = None,
        related_tags: Optional[bool] = None,
        cyom: Optional[bool] = None,
        uma_resolution_status: Optional[str] = None,
        game_id: Optional[str] = None,
        sports_market_types: Optional[list[str]] = None,
        rewards_min_size: Optional[float] = None,
        question_ids: Optional[list[str]] = None,
        include_tag: Optional[bool] = None,
        closed: Optional[bool] = None,
    ) -> pd.DataFrame:
        """
        Gamma /markets → normalized DataFrame.

        All parameters are optional and map 1:1 to query params.
        """
        payload = self._gamma(
            "markets",
            {
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "clob_token_ids": clob_token_ids,
                "condition_ids": condition_ids,
                "market_maker_address": market_maker_address,
                "liquidity_num_min": liquidity_num_min,
                "liquidity_num_max": liquidity_num_max,
                "volume_num_min": volume_num_min,
                "volume_num_max": volume_num_max,
                "start_date_min": start_date_min,
                "start_date_max": start_date_max,
                "end_date_min": end_date_min,
                "end_date_max": end_date_max,
                "tag_id": tag_id,
                "related_tags": related_tags,
                "cyom": cyom,
                "uma_resolution_status": uma_resolution_status,
                "game_id": game_id,
                "sports_market_types": sports_market_types,
                "rewards_min_size": rewards_min_size,
                "question_ids": question_ids,
                "include_tag": include_tag,
                "closed": closed,
            },
        )
        return self._postprocess(self._normalize(payload))

    def get_teams(
        self,
        limit: Optional[int] = 500,
        offset: Optional[int] = None,
        order: Optional[list[str]] = None,
        ascending: Optional[bool] = None,
        league: Optional[list[str]] = None,
        name: Optional[list[str]] = None,
        abbreviation: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Gamma /teams → normalized DataFrame."""
        payload = self._gamma(
            "teams",
            {
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "league": league,
                "name": name,
                "abbreviation": abbreviation,
            },
        )
        return self._postprocess(self._normalize(payload))

    def get_sports_metadata(
        self,
        sport: Optional[str] = None,
        image: Optional[str] = None,
        resolution: Optional[str] = None,
        ordering: Optional[str] = None,
        tags: Optional[str] = None,
        series: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Sports metadata (Gamma). Adjust path as needed if a dedicated endpoint exists.
        """
        payload = self._gamma(
            "teams",
            {
                "sport": sport,
                "image": image,
                "resolution": resolution,
                "ordering": ordering,
                "tags": tags,
                "series": series,
            },
        )
        return self._postprocess(self._normalize(payload))


    def _orderbook_to_df(self, payload: dict[str, Any]) -> pd.DataFrame:
        bids = pd.json_normalize(payload, record_path="bids", meta=orderbook_meta)
        bids["side"] = "bid"
        asks = pd.json_normalize(payload, record_path="asks", meta=orderbook_meta)
        asks["side"] = "ask"
        return self._postprocess(pd.concat([bids, asks], ignore_index=True))

    def get_orderbook(self, token_id: str) -> pd.DataFrame:
        """CLOB /book → flattened bid/ask rows."""
        payload = self._clob("book", {"token_id": token_id})
        return self._orderbook_to_df(payload)

    def get_orderbooks(self, tokens_df: pd.DataFrame) -> pd.DataFrame:
        """Bulk CLOB /book (POST-like) → flattened rows."""
        payload = self._clob("book", params=None)  
        return self._orderbook_to_df(payload)


if __name__ == "__main__":
    client = PolymarketPandas()
    markets = client.get_markets(order=["volume", "volume24hrAmm"], ascending=False)
    print(markets.head())
