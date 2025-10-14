import os
from dataclasses import dataclass, field
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


def filter_params(params: dict) -> dict:
    new_params = {}
    for key, value in params.items():
        if value:
            if isinstance(value, list):
                new_params[key] = value
            elif pd.notnull(value):
                new_params[key] = value
    return new_params


@dataclass
class PolymarketPandas:
    data_url: str = "https://data-api.polymarket.com/"
    gamma_url: str = "https://gamma-api.polymarket.com/"
    clob_url: str = "https://clob.polymarket.com/"
    key: str | None = field(default=None, repr=False)
    api_key: str | None = field(default=os.getenv("POLYMARKET_API_KEY"), repr=False)
    api_secret: str | None = field(
        default=os.getenv("POLYMARKET_API_SECRET"), repr=False
    )
    api_passphrase: str | None = field(
        default=os.getenv("POLYMARKET_API_PASSPHRASE"), repr=False
    )
    numeric_columns: tuple = field(
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
    datetime_columns: set = field(
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
    bool_columns: set = field(
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

    def __post_init__(self):
        self._client = httpx.Client()

    def _request_data(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        data = httpx.request(
            method=method,
            url=f"{self.data_url}{path}",
            params=filter_params(params),
            data=data,
        )
        return data.json()

    def _request_gamma(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        data = httpx.request(
            method=method,
            url=f"{self.gamma_url}{path}",
            params=filter_params(params),
            data=data,
        )
        return data.json()

    def _request_clob(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        data = httpx.request(
            method=method,
            url=f"{self.clob_url}{path}",
            params=filter_params(params),
            data=data,
        )
        return data.json()

    def preprocess_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        columns = data.columns
        numeric_columns_to_convert = [x for x in columns if x in self.numeric_columns]
        datetime_columns_to_convert = [x for x in columns if x in self.datetime_columns]
        bool_columns_to_convert = [x for x in columns if x in self.bool_columns]
        if numeric_columns_to_convert:
            data[numeric_columns_to_convert] = data[numeric_columns_to_convert].apply(
                pd.to_numeric, errors="coerce"
            )
        if datetime_columns_to_convert:
            data[datetime_columns_to_convert] = data[datetime_columns_to_convert].apply(
                pd.to_datetime, utc=True, errors="coerce"
            )
        if bool_columns_to_convert:
            data[bool_columns_to_convert] = data[bool_columns_to_convert].astype(bool)
        return data

    def response_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        return self.preprocess_dataframe(pd.DataFrame(data))

    def get_markets(
        self,
        limit: int | None = 500,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        id: list[int] | None = None,
        slug: list[str] | None = None,
        clob_token_ids: list[str] | None = None,
        condition_ids: list[str] | None = None,
        market_maker_address: list[str] | None = None,
        liquidity_num_min: float | None = None,
        liquidity_num_max: float | None = None,
        volume_num_min: float | None = None,
        volume_num_max: float | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
        end_date_min: str | None = None,
        end_date_max: str | None = None,
        tag_id: int | None = None,
        related_tags: bool | None = None,
        cyom: bool | None = None,
        uma_resolution_status: str | None = None,
        game_id: str | None = None,
        sports_market_types: list[str] | None = None,
        rewards_min_size: float | None = None,
        question_ids: list[str] | None = None,
        include_tag: bool | None = None,
        closed: bool | None = None,
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path="markets",
            params={
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
        return self.response_to_dataframe(data)

    def get_teams(
        self,
        limit: int | None = 500,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        league: list[str] | None = None,
        name: list[str] | None = None,
        abbreviation: list[str] | None = None,
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path="teams",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "league": league,
                "name": name,
                "abbreviation": abbreviation,
            },
        )
        return self.response_to_dataframe(data)

    def get_sports_metadata(
        self,
        sport: str | None = None,
        image: str | None = None,
        resolution: str | None = None,
        ordering: str | None = None,
        tags: str | None = None,
        series: str | None = None,
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path="teams",
            params={
                "sport": sport,
                "image": image,
                "resolution": resolution,
                "ordering": ordering,
                "tags": tags,
                "series": series,
            },
        )
        return self.response_to_dataframe(data)

    def orderbook_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        bids = pd.json_normalize(data, record_path="bids", meta=orderbook_meta)
        bids["side"] = "bids"
        asks = pd.json_normalize(data, record_path="asks", meta=orderbook_meta)
        asks["side"] = "asks"
        data = pd.concat([bids, asks], ignore_index=True)
        return self.preprocess_dataframe(data)

    def get_orderbook(self, token_id: str) -> pd.DataFrame:
        data = self._request_clob(path="book", params=dict(token_id=token_id))
        print(data)
        return self.orderbook_to_dataframe(data)

    def get_orderbooks(self, data: pd.DataFrame) -> pd.DataFrame:
        data = self._request_clob(path="book", data=data.to_dict("records"))
        return self.orderbook_to_dataframe(data)


if __name__ == "__main__":
    client = PolymarketPandas()
    markets = client.get_markets(order=["volume", "volume24hrAmm"], ascending=False)
    print(markets.loc[0])
    teams = client.get_teams()
    print(teams)
    print(markets["clobTokenIds"][0])
    df = client.get_orderbook(token_id=markets["conditionId"][0])
    print(df)
