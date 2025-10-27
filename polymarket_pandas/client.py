import hashlib
import hmac
import inspect
import json
import os
import time
from dataclasses import dataclass, field
import httpx

import orjson
import pandas as pd
from pandas import DataFrame
from tqdm import tqdm
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_typed_data

from polymarket_pandas.utils import (
    filter_params,
    snake_columns_to_camel,
    snake_to_camel,
)

orderbook_meta = [
    "market",
    "asset_id",
    "timestamp",
    "hash",
    "min_order_size",
    "tick_size",
    "neg_risk",
]
load_dotenv()


def markets_to_dict(data: pd.DataFrame) -> list:
    data = (
        data.rename(columns={"clobTokenIds": "token_id"})
        .reindex(columns=["token_id", "side"])
        .to_dict("records")
    )
    data = [filter_params(x) for x in data]
    return data


@dataclass
class PolymarketPandas:

    data_url: str = "https://data-api.polymarket.com/"
    gamma_url: str = "https://gamma-api.polymarket.com/"
    clob_url: str = "https://clob.polymarket.com/"
    address: str | None = field(default=os.getenv("POLYMARKET_ADDRESS"), repr=False)
    private_funder_key: str | None = field(
        default=os.getenv("POLYMARKET_FUNDER"), repr=False
    )
    private_key: str | None = field(
        default=os.getenv("POLYMARKET_PRIVATE_KEY"), repr=False
    )
    signature_type: int | None = field(default=1, repr=False)
    chain_id: int = field(default=137, repr=False)
    max_pages: int = field(default=100, repr=False)
    tqdm_description: str = field(default="", repr=True)
    use_tqdm: bool = field(default=True, repr=True)
    _api_key: str | None = field(default=os.getenv("POLYMARKET_API_KEY"), repr=False)
    _api_secret: str | None = field(
        default=os.getenv("POLYMARKET_API_SECRET"), repr=False
    )
    _api_passphrase: str | None = field(
        default=os.getenv("POLYMARKET_API_PASSPHRASE"), repr=False
    )
    numeric_columns: tuple = field(
        default=(
            "bestAsk",
            "bestBid",
            "best_ask",
            "best_bid",
            "fee_rate_bps",
            "full_accuracy_value",
            "lastTradePrice",
            "liquidity",
            "liquidityAmm",
            "liquidityNum",
            "lowerBound",
            "matched_amount",
            "min_order_size",
            "new_tick_size",
            "old_tick_size",
            "oneDayPriceChange",
            "oneHourPriceChange",
            "oneMonthPriceChange",
            "oneWeekPriceChange",
            "oneYearPriceChange",
            "original_size",
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
    str_datetime_columns: tuple = field(
        default=(
            "acceptingOrdersTimestamp",
            "closedTime",
            "createdAt",
            "creationDate",
            "endDate",
            "endDateIso",
            "eventStartTime",
            "expiration",
            "gameStartTime",
            "matchtime",
            "last_update",
            "startDate",
            "startDateIso",
            "startTime",
            "umaEndDate",
            "updatedAt",
        )
    )
    int_datetime_columns: tuple = field(default=("timestamp",))
    bool_columns: tuple = field(
        default=(
            "active",
            "approved",
            "archived",
            "clearBookOnStart",
            "closed",
            "competitive",
            "cyom",
            "deploying",
            "feesEnabled",
            "fpmmLive",
            "funded",
            "hasReviewedDates",
            "holdingRewardsEnabled",
            "manualActivation",
            "negRiskOther",
            "notificationsEnabled",
            "pagerDutyNotificationEnabled",
            "pendingDeployment",
            "ready",
            "readyForCron",
            "restricted",
            "rfqEnabled",
            "wideFormat",
        )
    )
    drop_columns: tuple = field(
        default=(
            "icon",
            "image",
        )
    )

    def __post_init__(self):
        self._client = httpx.Client()
        self._str_datetime_columns = list(self.str_datetime_columns) + [
            snake_to_camel(f"event_{x}") for x in self.str_datetime_columns
        ]
        self._int_datetime_columns = list(self.int_datetime_columns) + [
            snake_to_camel(f"event_{x}") for x in self.int_datetime_columns
        ]
        self._bool_columns = list(self.bool_columns) + [
            snake_to_camel(f"event_{x}") for x in self.bool_columns
        ]
        self._numeric_columns = list(self.numeric_columns) + [
            snake_to_camel(f"event_{x}") for x in self.numeric_columns
        ]
        self._drop_columns = list(self.drop_columns) + [
            snake_to_camel(f"event_{x}") for x in self.drop_columns
        ]

    def _autopage(
        self,
        fetcher,  # bound method like self.get_tags
        /,
        *,
        max_pages: int | None = None,
        page_param_limit: str = "limit",
        page_param_offset: str = "offset",
        **kwargs,
    ) -> pd.DataFrame:
        """
        Auto-paginate any fetcher(limit=..., offset=...) method.

        - Detects default 'limit' from the fetcher signature if not provided in kwargs.
        - Increments offset by the number of items returned each page.
        - If the fetcher returns DataFrames, returns a single concatenated DataFrame.
          Otherwise returns a list of page results.
        """
        sig = inspect.signature(fetcher)
        default_limit = sig.parameters[page_param_limit].default
        limit = kwargs.get(page_param_limit, default_limit)
        offset = kwargs.get(page_param_offset, 0)
        data = []
        n_pages = 0
        len_pages = limit
        progress_bar = (
            tqdm(total=self.max_pages, desc=self.tqdm_description)
            if self.use_tqdm and max_pages
            else None
        )
        while len_pages == limit and (max_pages is None or n_pages < max_pages):
            n_pages += 1
            call_kwargs = dict(kwargs)
            call_kwargs[page_param_limit] = limit
            call_kwargs[page_param_offset] = offset
            page = fetcher(**call_kwargs)
            data.append(page)
            page_len = len(page)
            offset += page_len
            if progress_bar:
                progress_bar.update(1)
                len_pages = page_len
        if progress_bar:
            progress_bar.close()
        return pd.concat(data, ignore_index=True)

    def _build_l1_headers(
        self,
        *,
        private_key: str,
        nonce: int = 0,
        server_timestamp: str | None = None,
        message: str = "This message attests that I control the given wallet",
    ) -> dict:
        """
        Build EIP-712 L1 headers (POLY_SIGNATURE is an EIP-712 sig).
        Only needed for /auth/api-key (create) and /auth/derive-api-key.
        """
        domain = {"name": "ClobAuthDomain", "version": "1", "chainId": self.chain_id}
        types = {
            "ClobAuth": [
                {"name": "address", "type": "address"},
                {"name": "timestamp", "type": "string"},
                {"name": "nonce", "type": "uint256"},
                {"name": "message", "type": "string"},
            ]
        }
        ts = server_timestamp or str(int(time.time()))
        value = {
            "address": self.address,
            "timestamp": ts,
            "nonce": nonce,
            "message": message,
        }
        signable = encode_typed_data(
            full_message={
                "domain": domain,
                "types": types,
                "primaryType": "ClobAuth",
                "message": value,
            }
        )
        acct = Account.from_key(private_key)
        sig = Account.sign_message(signable, private_key=private_key).signature.hex()
        return {
            "POLY_ADDRESS": self.address,
            "POLY_SIGNATURE": sig,
            "POLY_TIMESTAMP": ts,
            "POLY_NONCE": str(nonce),
        }

    def _build_l2_headers(
        self,
        *,
        method: str,
        request_path: str,
        body: dict | list | None = None,
        timestamp_ms: int | None = None,
    ) -> dict:
        """
        Build Polymarket L2 headers for private CLOB endpoints.

        Signature is an HMAC-SHA256 over a canonical string composed of:
            <timestamp><method><request_path><body_json_or_empty>

        Notes:
        - timestamp is UNIX ms (int).
        - request_path is the path only (e.g., "/data/trades"), not including host.
        - body is JSON-encoded if present; GETs typically have no body.
        """
        ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
        # Body normalization (exact string is part of the signature)
        body_str = ""
        if body is not None:
            # Preserve ordering for deterministic string; ensure separators are compact (no spaces)
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        # Canonical message: timestamp + method + path + body
        msg = f"{ts}{method.upper()}{request_path}{body_str}"
        sig = hmac.new(
            key=self._api_secret.encode("utf-8"),
            msg=msg.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return {
            "POLY_ADDRESS": self.address,
            "POLY_SIGNATURE": sig,
            "POLY_TIMESTAMP": ts,
            "POLY_API_KEY": self._api_key,
            "POLY_PASSPHRASE": self._api_passphrase,
        }

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
            json=data,
        )
        data = data.json()
        return data

    def preprocess_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        data = snake_columns_to_camel(data)
        data = data.drop(columns=self._drop_columns, errors="ignore")
        columns = data.columns
        numeric_columns_to_convert = [
            x
            for x in columns
            if x in self._numeric_columns + self._int_datetime_columns
        ]
        int_datetime_columns_to_convert = [
            x for x in columns if x in self._int_datetime_columns
        ]
        str_datetime_columns_to_convert = [
            x for x in columns if x in self._str_datetime_columns
        ]
        bool_columns_to_convert = [x for x in columns if x in self._bool_columns]
        if numeric_columns_to_convert:
            data[numeric_columns_to_convert] = data[numeric_columns_to_convert].apply(
                pd.to_numeric, errors="coerce"
            )
        if int_datetime_columns_to_convert:
            data[int_datetime_columns_to_convert] = data[
                int_datetime_columns_to_convert
            ].apply(pd.to_datetime, utc=True, unit="ms", errors="coerce")
        if str_datetime_columns_to_convert:
            data[str_datetime_columns_to_convert] = data[
                str_datetime_columns_to_convert
            ].apply(pd.to_datetime, utc=True, errors="coerce")
        if bool_columns_to_convert:
            data[bool_columns_to_convert] = data[bool_columns_to_convert].astype(bool)
        if "clobTokenIds" in columns:
            data["clobTokenIds"] = (
                data["clobTokenIds"].dropna().apply(lambda x: orjson.loads(x))
            )
        return data

    def response_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        return self.preprocess_dataframe(pd.DataFrame(data))

    def orderbook_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        bids = pd.json_normalize(data, record_path="bids", meta=orderbook_meta)
        bids["side"] = "bids"
        asks = pd.json_normalize(data, record_path="asks", meta=orderbook_meta)
        asks["side"] = "asks"
        data = pd.concat([bids, asks], ignore_index=True)
        return self.preprocess_dataframe(data)

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
        expand_clob_token_ids: bool = False,
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
        data = self.response_to_dataframe(data)
        if expand_clob_token_ids:
            data = data.explode("clobTokenIds")
            data["clobTokenIds"] = data["clobTokenIds"].astype(str)
        return data

    def get_tags(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        include_template: bool | None = None,
        is_carousel: bool | None = None,
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path="tags",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "include_template": include_template,
                "is_carousel": is_carousel,
            },
        )
        return self.response_to_dataframe(data)

    def get_tag_by_id(self, id: int, include_template: bool | None = None) -> dict:
        data = self._request_gamma(
            path=f"tags/{id}", params={"include_template": include_template}
        )
        return data

    def get_tag_by_slug(self, slug: str, include_template: bool | None = None) -> dict:
        data = self._request_gamma(
            path=f"tags/slug/{slug}", params={"include_template": include_template}
        )
        return data

    def get_related_tags_by_tag_id(
        self, id: int, omit_empty: bool | None = None, status: str | None = None
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path=f"tags/{id}/related-tags/tags",
            params={"omit_empty": omit_empty, "status": status},
        )
        return self.response_to_dataframe(data)

    def get_events(
        self,
        limit: int | None = 500,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        id: list[int] | None = None,
        slug: list[str] | None = None,
        tag_id: int | None = None,
        exclude_tag_id: list[int] | None = None,
        related_tags: bool | None = None,
        featured: bool | None = None,
        cyom: bool | None = None,
        include_chat: bool | None = None,
        include_template: bool | None = None,
        recurrence: str | None = None,
        closed: bool | None = None,
        start_date_min: str | None = None,
        start_date_max: str | None = None,
        end_date_min: str | None = None,
        end_date_max: str | None = None,
    ) -> pd.DataFrame:
        data = self._request_gamma(
            path="events",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "tag_id": tag_id,
                "exclude_tag_id": exclude_tag_id,
                "related_tags": related_tags,
                "featured": featured,
                "cyom": cyom,
                "include_chat": include_chat,
                "include_template": include_template,
                "recurrence": recurrence,
                "closed": closed,
                "start_date_min": start_date_min,
                "start_date_max": start_date_max,
                "end_date_min": end_date_min,
                "end_date_max": end_date_max,
            },
        )
        return self.response_to_dataframe(data)

    def get_event_by_id(
        self,
        id: int,
        include_chat: bool | None = None,
        include_template: bool | None = None,
    ) -> dict:
        data = self._request_gamma(
            path=f"events/{id}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )
        return data

    def get_event_tags(self, id: int) -> pd.DataFrame:
        """
        Retrieve tags associated with an event by its ID.
        Args:
            id (int): The unique identifier for the event.
        Returns:
            pd.DataFrame: A DataFrame containing the event tags.
        """
        data = self._request_gamma(path=f"events/{id}/tags")
        return self.response_to_dataframe(data)

    def get_event_by_slug(
        self,
        slug: str,
        include_chat: bool | None = None,
        include_template: bool | None = None,
    ) -> dict:
        """
        Retrieve an event by its slug.
        Args:
            slug (str): The slug of the event.
            include_chat (bool | None): Whether to include chat information.
            include_template (bool | None): Whether to include the template data.
        Returns:
            dict: The event information.
        """
        data = self._request_gamma(
            path=f"events/slug/{slug}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )
        return data

    def get_series(
        self,
        limit: int | None = 500,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        slug: list[str] | None = None,
        categories_ids: list[int] | None = None,
        categories_labels: list[str] | None = None,
        closed: bool | None = None,
        include_chat: bool | None = None,
        recurrence: str | None = None,
        expand_events: bool = True,
    ) -> pd.DataFrame:
        """
        Retrieve a list of series with optional filters.
        Args:
            limit (int | None): Maximum number of records to retrieve. Default is 500.
            offset (int | None): Number of records to skip.
            order (list[str] | None): Fields to order by.
            ascending (bool | None): Whether the order is ascending.
            slug (list[str] | None): Filter series by a list of slugs.
            categories_ids (list[int] | None): Filter series by category IDs.
            categories_labels (list[str] | None): Filter series by category labels.
            closed (bool | None): Filter by closed status.
            include_chat (bool | None): Whether to include chat information.
            recurrence (str | None): Filter by recurrence type.
            expand_events (bool): Whether to expand the events fields.
        Returns:
            pd.DataFrame: A DataFrame containing the series data.
        """
        data = self._request_gamma(
            path="series",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "slug": slug,
                "categories_ids": categories_ids,
                "categories_labels": categories_labels,
                "closed": closed,
                "include_chat": include_chat,
                "recurrence": recurrence,
            },
        )
        if expand_events:
            data = pd.DataFrame(data)
            meta = [x for x in data.columns if x != "events"]
            data = pd.json_normalize(
                data=data.to_dict("records"),
                record_path="events",
                meta=meta,
                # errors="ignore",
                record_prefix="event_",
            )
        else:
            data = pd.DataFrame(data)
        return self.preprocess_dataframe(data)

    def get_series_by_id(self, id: int, include_chat: bool | None = None) -> dict:
        """
        Retrieve a series by its ID.
        Args:
            id (int): The unique identifier for the series.
            include_chat (bool | None): Whether to include chat information.
        Returns:
            dict: The series information.
        """
        data = self._request_gamma(
            path=f"series/{id}",
            params={"include_chat": include_chat},
        )
        return data

    def get_comments(
        self,
        limit: int | None = None,
        offset: int | None = None,
        order: str | None = None,
        ascending: bool | None = None,
        parent_entity_type: str | None = None,
        parent_entity_id: int | None = None,
        get_positions: bool | None = None,
        holders_only: bool | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve comments with optional filters.
        Args:
            limit (int | None): Maximum number of records to retrieve.
            offset (int | None): Number of records to skip.
            order (str | None): Comma-separated list of fields to order by.
            ascending (bool | None): Whether the order is ascending.
            parent_entity_type (str | None): Entity type (e.g., "Event", "Series", "market").
            parent_entity_id (int | None): ID of the parent entity.
            get_positions (bool | None): Whether to get positions.
            holders_only (bool | None): Whether to filter holders only.
        Returns:
            pd.DataFrame: A DataFrame containing the comments data.
        """
        data = self._request_gamma(
            path="comments",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "parent_entity_type": parent_entity_type,
                "parent_entity_id": parent_entity_id,
                "get_positions": get_positions,
                "holders_only": holders_only,
            },
        )
        return self.response_to_dataframe(data)

    def get_comments_by_user_address(
        self,
        user_address: str,
        limit: int | None = None,
        offset: int | None = None,
        order: str | None = None,
        ascending: bool | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve comments made by a specific user address.
        Args:
            user_address (str): The user address whose comments are to be retrieved.
            limit (int | None): Maximum number of records to retrieve.
            offset (int | None): Number of records to skip.
            order (str | None): Comma-separated list of fields to order by.
            ascending (bool | None): Whether the order is ascending.
        Returns:
            pd.DataFrame: A DataFrame containing the comments data.
        """
        data = self._request_gamma(
            path=f"comments/user_address/{user_address}",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
            },
        )
        return self.response_to_dataframe(data)

    def get_comment_by_id(self, id: int, get_positions: bool | None = None) -> dict:
        """
        Retrieve a comment by its ID.
        Args:
            id (int): The unique identifier for the comment.
            get_positions (bool | None): Whether to include position information.
        Returns:
            dict: The comment details.
        """
        data = self._request_gamma(
            path=f"comments/{id}",
            params={"get_positions": get_positions},
        )
        return data

    def search_markets_events_profiles(
        self,
        q: str,
        cache: bool | None = None,
        events_status: str | None = None,
        limit_per_type: int | None = None,
        page: int | None = None,
        events_tag: list[str] | None = None,
        keep_closed_markets: int | None = None,
        sort: str | None = None,
        ascending: bool | None = None,
        search_tags: bool | None = None,
        search_profiles: bool | None = None,
        recurrence: str | None = None,
        exclude_tag_id: list[int] | None = None,
        optimized: bool | None = None,
    ) -> dict:
        """
        Search markets, events, and profiles.
        Args:
            q (str): The search query string.
            cache (bool | None): Whether to use cached results.
            events_status (str | None): The status of events to filter by.
            limit_per_type (int | None): Maximum number of results per type.
            page (int | None): The page number for results.
            events_tag (list[str] | None): Filter by event tags.
            keep_closed_markets (int | None): Whether to include closed markets.
            sort (str | None): Field to sort results by.
            ascending (bool | None): Whether to sort in ascending order.
            search_tags (bool | None): Whether to search tags.
            search_profiles (bool | None): Whether to search profiles.
            recurrence (str | None): Filter by recurrence type.
            exclude_tag_id (list[int] | None): Tags to exclude from results.
            optimized (bool | None): Whether to optimize the search.
        Returns:
            pd.DataFrame: A DataFrame containing search results.
        """
        data = self._request_gamma(
            path="public-search",
            params={
                "q": q,
                "cache": cache,
                "events_status": events_status,
                "limit_per_type": limit_per_type,
                "page": page,
                "events_tag": events_tag,
                "keep_closed_markets": keep_closed_markets,
                "sort": sort,
                "ascending": ascending,
                "search_tags": search_tags,
                "search_profiles": search_profiles,
                "recurrence": recurrence,
                "exclude_tag_id": exclude_tag_id,
                "optimized": optimized,
            },
        )
        return data

    def get_market_prices(self, token_sides: list[dict]) -> pd.DataFrame:
        """
        Retrieve market prices for multiple tokens and sides.
        Args:
            token_sides (list[dict]): A list of dictionaries. Each dictionary contains:
                - token_id (str): The unique identifier for the token.
                - side (str): The side ("BUY" or "SELL").
        Returns:
            pd.DataFrame: A DataFrame containing the market prices for tokens.
        """
        data = self._request_clob(path="prices", method="POST", data=token_sides)
        return self.response_to_dataframe(data)

    def get_positions(
        self,
        user: str,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        sizeThreshold: float | None = 1,
        redeemable: bool | None = False,
        mergeable: bool | None = False,
        limit: int | None = 100,
        offset: int | None = 0,
        sortBy: str | None = "TOKENS",
        sortDirection: str | None = "DESC",
        title: str | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve positions filtered by a user and optional parameters.
        Args:
            user (str): The user wallet address (required).
            market (list[str] | None): Filter positions by a list of market condition IDs.
            eventId (list[int] | None): Filter positions by a list of event IDs.
            sizeThreshold (float | None): Threshold for size filtering. Default is 1.
            redeemable (bool | None): Whether the positions are redeemable. Default is False.
            mergeable (bool | None): Whether the positions are mergeable. Default is False.
            limit (int | None): Maximum number of records to retrieve. Default is 100.
            offset (int | None): Number of records to skip. Default is 0.
            sortBy (str | None): The field to sort the results by. Default is "TOKENS".
            sortDirection (str | None): Sort direction, either "ASC" or "DESC". Default is "DESC".
            title (str | None): Filter results by title (max length 100).
        Returns:
            pd.DataFrame: A DataFrame containing the positions data.
        """
        data = self._request_gamma(
            path="positions",
            params={
                "user": user,
                "market": market,
                "eventId": eventId,
                "sizeThreshold": sizeThreshold,
                "redeemable": redeemable,
                "mergeable": mergeable,
                "limit": limit,
                "offset": offset,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "title": title,
            },
        )
        return self.response_to_dataframe(data)

    def get_trades(
        self,
        limit: int | None = 100,
        offset: int | None = 0,
        takerOnly: bool | None = True,
        filterType: str | None = None,
        filterAmount: float | None = None,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        user: str | None = None,
        side: str | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve trades for a user or markets with optional filters.
        Args:
            limit (int | None): Maximum number of records to retrieve (default: 100).
            offset (int | None): Number of records to skip (default: 0).
            takerOnly (bool | None): Filter for taker-only trades (default: True).
            filterType (str | None): Filter type, available options: "CASH", "TOKENS".
            filterAmount (float | None): Minimum amount to filter, required with filterType.
            market (list[str] | None): List of market condition IDs (mutually exclusive with eventId).
            eventId (list[int] | None): List of event IDs (mutually exclusive with market).
            user (str | None): User profile address (0x-prefixed, 40 hex characters).
            side (str | None): Trade side, available options: "BUY", "SELL".
        Returns:
            pd.DataFrame: A DataFrame containing the trades data.
        """
        data = self._request_gamma(
            path="trades",
            params={
                "limit": limit,
                "offset": offset,
                "takerOnly": takerOnly,
                "filterType": filterType,
                "filterAmount": filterAmount,
                "market": market,
                "eventId": eventId,
                "user": user,
                "side": side,
            },
        )
        return self.response_to_dataframe(data)

    def get_open_interest(
        self,
        market: list[str] | None = None,
    ) -> dict:
        """
        Retrieve open interest data for specific markets.
        Args:
            market (list[str] | None): List of market condition IDs (0x-prefixed, 64-hex string).
        Returns:
            dict: A dictionary containing open interest data.
        """
        data = self._request_gamma(path="oi", params={"market": market})
        return data

    def get_live_volume(self, id: int) -> dict:
        """
        Retrieve the live volume for an event.
        Args:
            id (int): The unique identifier for the event. Must be >= 1.
        Returns:
            dict: A dictionary containing the live volume data.
        """
        data = self._request_gamma(
            path="live-volume",
            params={"id": id},
        )
        return data

    def get_user_activity(
        self,
        user: str,
        limit: int | None = 100,
        offset: int | None = 0,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        type: list[str] | None = None,
        start: int | None = None,
        end: int | None = None,
        sortBy: str | None = "TIMESTAMP",
        sortDirection: str | None = "DESC",
        side: str | None = None,
    ) -> pd.DataFrame:
        """
        Get on-chain activity for a user.
        Args:
            user (str): User profile address (0x-prefixed, 40 hex characters).
            limit (int | None): Maximum number of records to retrieve (default: 100).
            offset (int | None): Number of records to skip (default: 0).
            market (list[str] | None): Comma-separated list of condition IDs, mutually exclusive with eventId.
            eventId (list[int] | None): Comma-separated list of event IDs, mutually exclusive with market.
            type (list[str] | None): Filter by activity type.
            start (int | None): Minimum timestamp range.
            end (int | None): Maximum timestamp range.
            sortBy (str | None): Field to sort results by (default: "TIMESTAMP").
            sortDirection (str | None): Sort direction, "ASC" or "DESC" (default: "DESC").
            side (str | None): Activity side, "BUY" or "SELL".
        Returns:
            pd.DataFrame: A DataFrame containing the activity data.
        """
        data = self._request_gamma(
            path="activity",
            params={
                "user": user,
                "limit": limit,
                "offset": offset,
                "market": market,
                "eventId": eventId,
                "type": type,
                "start": start,
                "end": end,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "side": side,
            },
        )
        return self.response_to_dataframe(data)

    def get_top_holders(
        self,
        market: list[str],
        limit: int | None = 100,
        minBalance: int | None = 1,
    ) -> pd.DataFrame:
        """
        Retrieve the top holders for specified markets.
        Args:
            market (list[str]): Comma-separated list of condition IDs (0x-prefixed, 64-hex string).
            limit (int | None): Maximum number of top holders to retrieve (default: 100).
            minBalance (int | None): Minimum balance for filtering (default: 1).
        Returns:
            pd.DataFrame: A DataFrame containing the holders data.
        """
        data = self._request_gamma(
            path="holders",
            params={
                "market": market,
                "limit": limit,
                "minBalance": minBalance,
            },
        )
        return self.response_to_dataframe(data)

    def get_traded_markets_count(self, user: str) -> dict:
        """
        Retrieve the total number of markets a user has traded.
        Args:
            user (str): The user wallet address (0x-prefixed, 40 hex characters).
        Returns:
            dict: A dictionary containing the total markets count.
        """
        data = self._request_gamma(
            path="traded",
            params={"user": user},
        )
        return data

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

    def get_orderbook(self, token_id: str) -> pd.DataFrame:
        data = self._request_clob(path="book", params=dict(token_id=token_id))
        return self.orderbook_to_dataframe(data)

    def get_orderbooks(self, data: pd.DataFrame) -> pd.DataFrame:
        data = self._request_clob(
            path="books", method="POST", data=markets_to_dict(data)
        )
        return self.orderbook_to_dataframe(data)

    def get_market_price(self, token_id: str, side: str) -> float:
        """
        Retrieves the market price for a specific token and side.

        Args:
            token_id (str): The unique identifier for the token.
            side (str): The market side, either "BUY" or "SELL".

        Returns:
            dict: A dictionary containing the market price data.
        """
        data = self._request_clob(
            path="price", params={"token_id": token_id, "side": side}
        )
        return float(data["price"])

    # def get_multiple_market_prices(self) -> pd.DataFrame:
    #     """
    #     Retrieves the market prices.
    #
    #     Returns:
    #         dict: A dictionary containing the market price data.
    #     """
    #     data = self._request_clob(
    #         path="prices",
    #     )
    #     return self.response_to_dataframe(data)

    def get_multiple_market_prices_by_request(self, data: pd.DataFrame) -> DataFrame:
        """
        Retrieves market prices for specified tokens and sides via a POST request.

        Returns:
            pd.DataFrame: A DataFrame containing the market prices for the specified tokens and sides.
        """
        data = self._request_clob(
            path="prices", method="POST", data=markets_to_dict(data)
        )
        df = []
        for k, v in data.items():
            for sub_k, sub_v in v.items():
                df.append({"tokenId": k, "side": sub_k, "price": sub_v})
        return self.response_to_dataframe(df)

    def get_price_history(
        self,
        market: str,
        startTs: int | None = None,
        endTs: int | None = None,
        interval: str | None = None,
        fidelity: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetches historical price data for a specific market token.

        Args:
            market (str): The CLOB token ID for which to fetch price history.
            startTs (int | None): The start time, as a Unix UTC timestamp.
            endTs (int | None): The end time, as a Unix UTC timestamp.
            interval (str | None): A duration string ending at the current time. Options: "1m", "1w", "1d", "6h", "1h", "max".
            fidelity (int | None): The resolution of the data, in minutes.

        Returns:
            pd.DataFrame: A DataFrame containing historical price data.
        """
        data = self._request_clob(
            path="prices-history",
            params={
                "market": market,
                "startTs": startTs,
                "endTs": endTs,
                "interval": interval,
                "fidelity": fidelity,
            },
        )
        return self.response_to_dataframe(data)

    def get_midpoint_price(self, token_id: str) -> float:
        """
        Retrieve the midpoint price for a specific token.

        Args:
            token_id (str): The unique identifier for the token.

        Returns:
            dict: A dictionary containing the midpoint price data.
        """
        data = self._request_clob(path="midpoint", params={"token_id": token_id})
        return float(data["mid"])

    def get_bid_ask_spreads(self, data: pd.DataFrame) -> dict:
        """
        Retrieves bid-ask spreads for multiple tokens via a POST request.

        Args:
            data (pd.DataFrame): A list of objects containing the required format for spreads.

        Returns:
            pd.DataFrame: A DataFrame containing the bid-ask spreads data.
        """
        data = self._request_clob(
            path="spreads", method="POST", data=markets_to_dict(data)
        )
        data = {k: float(v) for k, v in data.items()}
        return data

    def get_user_trades(
        self,
        id: str | None = None,
        taker: str | None = None,
        maker: str | None = None,
        market: str | None = None,
        before: str | None = None,
        after: str | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve trades for the authenticated user based on provided filters.

        Args:
            id (str | None): ID of the trade to fetch.
            taker (str | None): Address to get trades where it's included as a taker.
            maker (str | None): Address to get trades where it's included as a maker.
            market (str | None): Market (condition ID) to fetch trades for.
            before (str | None): Fetch trades before this Unix timestamp.
            after (str | None): Fetch trades after this Unix timestamp.

        Returns:
            pd.DataFrame: A DataFrame containing the user's trades based on the filters.
        """
        data = self._request_clob(
            path="data/trades",
            params={
                "id": id,
                "taker": taker,
                "maker": maker,
                "market": market,
                "before": before,
                "after": after,
            },
        )
        return self.response_to_dataframe(data)

    def get_order(self, order_id: str) -> dict:
        """
        Get information about an existing order.

        Args:
            order_id (str): ID of the order to retrieve.

        Returns:
            dict: A dictionary containing the order information.
        """
        data = self._request_clob(
            path=f"data/order/{order_id}",
            method="GET",
        )
        return data

    def get_active_orders(
        self,
        id: str | None = None,
        market: str | None = None,
        asset_id: str | None = None,
    ) -> pd.DataFrame:
        """
        Get active orders for a specific market, asset, or order ID.

        Args:
            id (str | None): ID of the order to retrieve.
            market (str | None): ID of the market/condition.
            asset_id (str | None): ID of the asset/token.

        Returns:
            pd.DataFrame: A DataFrame containing the active orders data.
        """
        data = self._request_clob(
            path="data/orders",
            params={
                "id": id,
                "market": market,
                "asset_id": asset_id,
            },
        )
        return self.response_to_dataframe(data)

    def place_order(
        self,
        order: dict,
        owner: str,
        orderType: str,
    ) -> dict:
        """
        Create and place an order using the Polymarket CLOB API.

        Args:
            order (dict): The signed order object.
            owner (str): API key of the order owner.
            orderType (str): The order type, e.g., "FOK", "GTC", "GTD".

        Returns:
            dict: Response from the API.
        """
        headers = self._build_l2_headers(
            method="POST",
            request_path="/order",
            body={
                "order": order,
                "owner": owner,
                "orderType": orderType,
            },
        )
        response = self._client.post(
            f"{self.clob_url}order",
            json={
                "order": order,
                "owner": owner,
                "orderType": orderType,
            },
            headers=headers,
        )
        return response.json()

    def place_orders(self, orders: pd.DataFrame) -> DataFrame:
        """
        Place multiple orders in a batch (up to 15 orders).

        Args:
            orders (list[dict]): A list of dictionaries. Each dictionary must contain:
                - order (dict): The signed order object.
                - owner (str): API key of the order owner.
                - orderType (str): The order type, e.g., "FOK", "GTC", "GTD", "FAK".

        Returns:
            dict: Response from the API.
        """
        orders_data = []
        data = orders.copy()
        data["expiration"] = data["expiration"].astype(int)
        for [owner, orderType], sub_orders in data.groupby(["owner", "orderType"]):
            for x in sub_orders.to_dict("records"):
                order = {
                    "order": x,
                    "owner": owner,
                    "orderType": orderType,
                }
                orders_data.append(order.copy())
        response = self._request_clob(
            f"orders",
            data=orders_data,
        )
        return self.response_to_dataframe(response)

    def cancel_order(self, order_id: str) -> dict:
        """
        Cancel a single order.

        Args:
            order_id (str): ID of the order to cancel.

        Returns:
            dict: A dictionary containing the response for the cancellation request.
        """
        response = self._request_clob(
            path="order",
            method="DELETE",
            data={"orderID": order_id},
        )
        return response

    def cancel_orders(self, order_ids: list[str]) -> dict:
        """
        Cancel multiple orders.

        Args:
            order_ids (list[str]): List of order IDs to cancel.

        Returns:
            dict: A dictionary containing the response for each cancellation request.
        """
        response = self._request_clob(
            path="orders",
            method="DELETE",
            data=order_ids,
        )
        return response

    def cancel_all_orders(self) -> dict:
        """
        Cancel all orders.

        Returns:
            dict: A dictionary containing the response for all cancellation request.
        """
        response = self._request_clob(
            path="cancel-all",
            method="DELETE",
        )
        return response

    def cancel_orders_from_market(
        self, market: str | None = None, asset_id: str | None = None
    ) -> dict:
        """
        Cancel orders from a specific market or asset.

        Args:
            market (str | None): Condition ID of the market to cancel orders from.
            asset_id (str | None): ID of the asset/token to cancel orders for.

        Returns:
            dict: A dictionary containing the response for each cancellation request.
        """
        response = self._request_clob(
            path="cancel-market-orders",
            method="DELETE",
            params={
                "market": market,
                "asset_id": asset_id,
            },
        )
        return response

    def get_tags_all(self, **kwargs) -> pd.DataFrame:
        return self._autopage(self.get_tags, **kwargs)

    def get_events_all(self, **kwargs) -> pd.DataFrame:
        return self._autopage(self.get_events, **kwargs)

    def get_markets_all(self, **kwargs) -> pd.DataFrame:
        return self._autopage(self.get_markets, **kwargs)


if __name__ == "__main__":
    client = PolymarketPandas()
    # orders = client.get_active_orders()
    teams = client.get_teams()
    print(teams)
    sports_metadata = client.get_sports_metadata()
    print(sports_metadata)
    tags = client.get_tags()
    print(tags)
    series = client.get_series()
    print(series)
    btc_market = series.loc[series["eventEndDate"] >= pd.Timestamp.utcnow()].query(
        "active and slug == 'btc-up-or-down-daily'"
    )
    slugs = btc_market["eventSlug"].head(4).tolist()
    markets = client.get_markets(slug=slugs, expand_clob_token_ids=True)
    print(markets)
    events = client.get_events(slug=slugs)
    print(events)
    token = markets["clobTokenIds"].values[0]
    orderbook = client.get_orderbook(token_id=token)
    print(orderbook)
    orderbooks = client.get_orderbooks(data=markets)
    print(orderbooks)
    market_price = client.get_market_price(token_id=token, side="BUY")
    print(market_price)
    spreads_df = client.get_bid_ask_spreads(data=markets)
    print(spreads_df)
    midpoint_price = client.get_midpoint_price(token_id=token)
    print(midpoint_price)
    market_prices = client.get_multiple_market_prices_by_request(data=markets)
    print(market_prices)
    trades = client.get_trades()
    print(trades)
    # market_prices = client.get_multiple_market_prices()
    # print(market_prices)
