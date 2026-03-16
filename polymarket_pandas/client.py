import hashlib
import hmac
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from typing import Self

import httpx
import pandas as pd
from eth_account import Account
from eth_account.messages import encode_typed_data
from tqdm import tqdm

from polymarket_pandas.exceptions import (
    PolymarketAPIError,
    PolymarketAuthError,
    PolymarketRateLimitError,
)
from polymarket_pandas.mixins import (
    BridgeMixin,
    ClobPrivateMixin,
    ClobPublicMixin,
    DataMixin,
    GammaMixin,
    RelayerMixin,
)
from polymarket_pandas.utils import (
    expand_column_lists,
    filter_params,
    orderbook_meta,
)
from polymarket_pandas.utils import (
    preprocess_dataframe as _preprocess_dataframe,
)


def markets_to_dict(data: pd.DataFrame) -> list:
    data = data.reindex(columns=["token_id", "side"]).to_dict("records")
    data = [filter_params(x) for x in data]
    return data


@dataclass
class PolymarketPandas(
    GammaMixin,
    DataMixin,
    ClobPublicMixin,
    ClobPrivateMixin,
    RelayerMixin,
    BridgeMixin,
):
    """Polymarket HTTP client that returns preprocessed pandas DataFrames.

    All endpoint methods live in the six mixins; this class provides the
    HTTP transport, authentication, DataFrame preprocessing, and pagination
    infrastructure. Credentials fall back to environment variables when not
    supplied explicitly. Use as a context manager to ensure the connection
    pool is closed.
    """

    data_url: str = "https://data-api.polymarket.com/"
    gamma_url: str = "https://gamma-api.polymarket.com/"
    clob_url: str = "https://clob.polymarket.com/"
    relayer_url: str = field(default="https://relayer-v2.polymarket.com/", repr=False)
    bridge_url: str = field(default="https://bridge.polymarket.com/", repr=False)
    address: str | None = field(default=os.getenv("POLYMARKET_ADDRESS"), repr=False)
    private_funder_key: str | None = field(default=os.getenv("POLYMARKET_FUNDER"), repr=False)
    private_key: str | None = field(default=os.getenv("POLYMARKET_PRIVATE_KEY"), repr=False)
    signature_type: int | None = field(default=1, repr=False)
    chain_id: int = field(default=137, repr=False)
    max_pages: int = field(default=100, repr=False)
    tqdm_description: str = field(default="", repr=True)
    use_tqdm: bool = field(default=True, repr=True)
    _api_key: str | None = field(default=os.getenv("POLYMARKET_API_KEY"), repr=False)
    _api_secret: str | None = field(default=os.getenv("POLYMARKET_API_SECRET"), repr=False)
    _api_passphrase: str | None = field(default=os.getenv("POLYMARKET_API_PASSPHRASE"), repr=False)
    _builder_api_key: str | None = field(
        default=os.getenv("POLYMARKET_BUILDER_API_KEY"), repr=False
    )
    _builder_api_secret: str | None = field(
        default=os.getenv("POLYMARKET_BUILDER_API_SECRET"), repr=False
    )
    _builder_api_passphrase: str | None = field(
        default=os.getenv("POLYMARKET_BUILDER_API_PASSPHRASE"), repr=False
    )
    _relayer_api_key: str | None = field(
        default=os.getenv("POLYMARKET_RELAYER_API_KEY"), repr=False
    )
    _relayer_api_key_address: str | None = field(
        default=os.getenv("POLYMARKET_RELAYER_API_KEY_ADDRESS"), repr=False
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
            "deployingTimestamp",
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
    json_columns: tuple = field(default=("clobTokenIds", "outcomes", "outcomePrices"))

    def __post_init__(self) -> None:
        self._client = httpx.Client()
        self._numeric_columns = expand_column_lists(self.numeric_columns)
        self._str_datetime_columns = expand_column_lists(self.str_datetime_columns)
        self._int_datetime_columns = expand_column_lists(self.int_datetime_columns)
        self._bool_columns = expand_column_lists(self.bool_columns)
        self._drop_columns = expand_column_lists(self.drop_columns)
        self._json_columns = expand_column_lists(self.json_columns)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> Self:
        """Enter the context manager, returning this client instance."""
        return self

    def __exit__(self, *_: object) -> None:
        """Exit the context manager and close the HTTP connection pool."""
        self.close()

    def _autopage(
        self,
        fetcher,
        /,
        *,
        max_pages: int | None = None,
        page_param_limit: str = "limit",
        page_param_offset: str = "offset",
        **kwargs,
    ) -> pd.DataFrame:
        """
        Auto-paginate any fetcher(limit=..., offset=...) method.
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
        Account.from_key(private_key)
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
        """
        ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
        body_str = ""
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
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

    # ── Error handling ───────────────────────────────────────────────────

    def _handle_response(self, response: httpx.Response) -> dict:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            url = str(exc.request.url)
            try:
                detail: object = exc.response.json()
            except Exception:
                detail = exc.response.text
            if status in (401, 403):
                raise PolymarketAuthError(status, url, detail) from exc
            if status == 429:
                raise PolymarketRateLimitError(status, url, detail) from exc
            raise PolymarketAPIError(status, url, detail) from exc
        return response.json()

    def _extract(self, data: dict, key: str) -> object:
        """
        Extract a key from an API response dict, raising ``PolymarketAPIError``
        with context if the key is absent.
        """
        try:
            return data[key]
        except (KeyError, TypeError) as exc:
            raise PolymarketAPIError(
                status_code=0,
                url="<internal>",
                detail=f"Expected key {key!r} in API response; got: {data!r}",
            ) from exc

    def _require_l2_auth(self) -> None:
        if not (self._api_key and self._api_secret and self._api_passphrase):
            raise PolymarketAuthError(
                detail=(
                    "CLOB API credentials not set. "
                    "Provide _api_key, _api_secret, and _api_passphrase "
                    "(or set POLYMARKET_API_KEY / POLYMARKET_API_SECRET / "
                    "POLYMARKET_API_PASSPHRASE env vars)."
                )
            )

    def _require_builder_auth(self) -> None:
        if not (
            self._builder_api_key and self._builder_api_secret and self._builder_api_passphrase
        ):
            raise PolymarketAuthError(
                detail=(
                    "Builder API credentials not set. "
                    "Provide _builder_api_key, _builder_api_secret, and "
                    "_builder_api_passphrase (or set POLYMARKET_BUILDER_API_KEY / "
                    "POLYMARKET_BUILDER_API_SECRET / "
                    "POLYMARKET_BUILDER_API_PASSPHRASE env vars)."
                )
            )

    # ── Request helpers ──────────────────────────────────────────────────

    def _request_data(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        response = self._client.request(
            method=method,
            url=f"{self.data_url}{path}",
            params=filter_params(params),
            json=data,
        )
        return self._handle_response(response)

    def _request_gamma(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        response = self._client.request(
            method=method,
            url=f"{self.gamma_url}{path}",
            params=filter_params(params),
            json=data,
        )
        return self._handle_response(response)

    def _request_clob(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        response = self._client.request(
            method=method,
            url=f"{self.clob_url}{path}",
            params=filter_params(params),
            json=data,
        )
        return self._handle_response(response)

    def _request_clob_private(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        self._require_l2_auth()
        headers = self._build_l2_headers(
            method=method,
            request_path=f"/{path}",
            body=data,
        )
        response = self._client.request(
            method=method,
            url=f"{self.clob_url}{path}",
            params=filter_params(params),
            json=data,
            headers=headers,
        )
        return self._handle_response(response)

    def _build_builder_headers(
        self,
        *,
        method: str,
        request_path: str,
        body: dict | list | None = None,
        timestamp_ms: int | None = None,
    ) -> dict:
        ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
        body_str = ""
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        msg = f"{ts}{method.upper()}{request_path}{body_str}"
        sig = hmac.new(
            key=self._builder_api_secret.encode("utf-8"),
            msg=msg.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return {
            "POLY_BUILDER_API_KEY": self._builder_api_key,
            "POLY_BUILDER_PASSPHRASE": self._builder_api_passphrase,
            "POLY_BUILDER_TIMESTAMP": ts,
            "POLY_BUILDER_SIGNATURE": sig,
        }

    def _request_clob_builder(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        self._require_builder_auth()
        headers = self._build_builder_headers(method=method, request_path=f"/{path}", body=data)
        response = self._client.request(
            method=method,
            url=f"{self.clob_url}{path}",
            params=filter_params(params),
            json=data,
            headers=headers,
        )
        return self._handle_response(response)

    def _request_relayer(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
        auth_headers: dict | None = None,
    ) -> dict:
        response = self._client.request(
            method=method,
            url=f"{self.relayer_url}{path}",
            params=filter_params(params),
            json=data,
            headers=auth_headers or {},
        )
        return self._handle_response(response)

    def _request_bridge(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict:
        response = self._client.request(
            method=method,
            url=f"{self.bridge_url}{path}",
            params=filter_params(params),
            json=data,
        )
        return self._handle_response(response)

    def _relayer_auth_headers(self) -> dict:
        return {
            k: v
            for k, v in {
                "RELAYER_API_KEY": self._relayer_api_key,
                "RELAYER_API_KEY_ADDRESS": self._relayer_api_key_address,
            }.items()
            if v is not None
        }

    def preprocess_dataframe(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply column renaming, type coercion, and cleanup to a raw DataFrame."""
        return _preprocess_dataframe(
            data,
            numeric_columns=self._numeric_columns,
            str_datetime_columns=self._str_datetime_columns,
            int_datetime_columns=self._int_datetime_columns,
            bool_columns=self._bool_columns,
            drop_columns=self._drop_columns,
            json_columns=self._json_columns,
        )

    def response_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        """Convert a raw JSON response (list of dicts) to a preprocessed DataFrame."""
        return self.preprocess_dataframe(pd.DataFrame(data))

    def orderbook_to_dataframe(self, data: dict | list) -> pd.DataFrame:
        """Normalize a CLOB order-book response into a single bids+asks DataFrame."""
        bids = pd.json_normalize(data, record_path="bids", meta=orderbook_meta)
        bids["side"] = "bids"
        asks = pd.json_normalize(data, record_path="asks", meta=orderbook_meta)
        asks["side"] = "asks"
        data = pd.concat([bids, asks], ignore_index=True)
        return self.preprocess_dataframe(data)

    # ── Pagination helpers ───────────────────────────────────────────────

    def _autopage_cursor(
        self,
        fetcher,
        /,
        *,
        max_pages: int | None = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Cursor-based auto-pager for endpoints that return
        ``{"data": [...], "next_cursor": str, ...}``.

        Stops when ``next_cursor`` is ``"LTE="`` (sentinel for last page),
        empty, or ``max_pages`` is reached.
        """
        pages: list[pd.DataFrame] = []
        next_cursor: str | None = kwargs.pop("next_cursor", None)
        n = 0
        while True:
            page = fetcher(next_cursor=next_cursor, **kwargs)
            pages.append(page["data"])
            next_cursor = page.get("next_cursor")
            n += 1
            if (
                not next_cursor
                or next_cursor == "LTE="
                or (max_pages is not None and n >= max_pages)
            ):
                break
        return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()

    def get_tags_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all tags and return a single DataFrame."""
        return self._autopage(self.get_tags, **kwargs)

    def get_events_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all events and return a single DataFrame."""
        return self._autopage(self.get_events, **kwargs)

    def get_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all markets and return a single DataFrame."""
        return self._autopage(self.get_markets, **kwargs)

    def get_sampling_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all sampling markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_sampling_markets, **kwargs)

    def get_simplified_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all simplified markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_simplified_markets, **kwargs)

    def get_sampling_simplified_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all sampling simplified markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_sampling_simplified_markets, **kwargs)
