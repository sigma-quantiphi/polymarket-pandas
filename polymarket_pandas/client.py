"""PolymarketPandas — core HTTP client dataclass with order building and pagination."""

import base64
import hashlib
import hmac
import inspect
import json
import math
import os
import random
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
    CTFMixin,
    DataMixin,
    GammaMixin,
    RelayerMixin,
    RewardsMixin,
)
from polymarket_pandas.types import SendOrderResponse, SignedOrder
from polymarket_pandas.utils import (
    DEFAULT_BOOL_COLUMNS,
    DEFAULT_DROP_COLUMNS,
    DEFAULT_INT_DATETIME_COLUMNS,
    DEFAULT_JSON_COLUMNS,
    DEFAULT_NUMERIC_COLUMNS,
    DEFAULT_STR_DATETIME_COLUMNS,
    expand_column_lists,
    filter_params,
    orderbook_meta,
    to_unix_timestamp,
)
from polymarket_pandas.utils import (
    preprocess_dataframe as _preprocess_dataframe,
)
from polymarket_pandas.utils import (
    preprocess_dict as _preprocess_dict,
)

# ── CTF Exchange contract addresses (Polygon mainnet) ────────────────
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# Tick-size → (price_decimals, size_decimals, amount_decimals)
_TICK_SIZES = {
    "0.1": (1, 2, 3),
    "0.01": (2, 2, 4),
    "0.001": (3, 2, 5),
    "0.0001": (4, 2, 6),
}


def _round_down(v: float, decimals: int) -> float:
    factor = 10**decimals
    return math.floor(v * factor) / factor


def _round_normal(v: float, decimals: int) -> float:
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(str(v)).quantize(Decimal(10) ** -decimals, rounding=ROUND_HALF_UP))


def _round_up(v: float, decimals: int) -> float:
    factor = 10**decimals
    return math.ceil(v * factor) / factor


def _decimal_places(v: float) -> int:
    from decimal import Decimal

    return abs(Decimal(str(v)).as_tuple().exponent)


def _to_token_decimals(v: float) -> int:
    return int(round(v * 1e6))


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
    CTFMixin,
    RewardsMixin,
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
    rpc_url: str | None = field(default=None, repr=False)
    proxy_url: str | None = field(default=None, repr=False)
    address: str | None = field(default=None, repr=False)
    private_funder_key: str | None = field(default=None, repr=False)
    private_key: str | None = field(default=None, repr=False)
    signature_type: int | None = field(default=1, repr=False)
    chain_id: int = field(default=137, repr=False)
    timeout: int = field(default=30, repr=False)
    max_pages: int = field(default=100, repr=False)
    tqdm_description: str = field(default="", repr=True)
    use_tqdm: bool = field(default=True, repr=True)
    _api_key: str | None = field(default=None, repr=False)
    _api_secret: str | None = field(default=None, repr=False)
    _api_passphrase: str | None = field(default=None, repr=False)
    _builder_api_key: str | None = field(default=None, repr=False)
    _builder_api_secret: str | None = field(default=None, repr=False)
    _builder_api_passphrase: str | None = field(default=None, repr=False)
    _relayer_api_key: str | None = field(default=None, repr=False)
    _relayer_api_key_address: str | None = field(default=None, repr=False)
    numeric_columns: tuple = field(default=DEFAULT_NUMERIC_COLUMNS)
    str_datetime_columns: tuple = field(default=DEFAULT_STR_DATETIME_COLUMNS)
    int_datetime_columns: tuple = field(default=DEFAULT_INT_DATETIME_COLUMNS)
    bool_columns: tuple = field(default=DEFAULT_BOOL_COLUMNS)
    drop_columns: tuple = field(default=DEFAULT_DROP_COLUMNS)
    json_columns: tuple = field(default=DEFAULT_JSON_COLUMNS)

    # Mapping: (field_name, env_var, fallback)
    _ENV_DEFAULTS: dict = field(
        default_factory=lambda: {
            "rpc_url": ("POLYMARKET_RPC_URL", "https://polygon-rpc.com"),
            "proxy_url": ("FIXIE_URL", None),
            "address": ("POLYMARKET_ADDRESS", None),
            "private_funder_key": ("POLYMARKET_FUNDER", None),
            "private_key": ("POLYMARKET_PRIVATE_KEY", None),
            "_api_key": ("POLYMARKET_API_KEY", None),
            "_api_secret": ("POLYMARKET_API_SECRET", None),
            "_api_passphrase": ("POLYMARKET_API_PASSPHRASE", None),
            "_builder_api_key": ("POLYMARKET_BUILDER_API_KEY", None),
            "_builder_api_secret": ("POLYMARKET_BUILDER_API_SECRET", None),
            "_builder_api_passphrase": ("POLYMARKET_BUILDER_API_PASSPHRASE", None),
            "_relayer_api_key": ("POLYMARKET_RELAYER_API_KEY", None),
            "_relayer_api_key_address": ("POLYMARKET_RELAYER_API_KEY_ADDRESS", None),
        },
        repr=False,
    )

    def __post_init__(self) -> None:
        # Resolve env vars at runtime (after load_dotenv has had a chance to run)
        for attr, (env_var, fallback) in self._ENV_DEFAULTS.items():
            if getattr(self, attr) is None:
                setattr(self, attr, os.getenv(env_var, fallback))

        self._client = httpx.Client(proxy=self.proxy_url, timeout=self.timeout)
        self._numeric_columns = expand_column_lists(self.numeric_columns)
        self._str_datetime_columns = expand_column_lists(self.str_datetime_columns)
        self._int_datetime_columns = expand_column_lists(self.int_datetime_columns)
        self._bool_columns = expand_column_lists(self.bool_columns)
        self._drop_columns = expand_column_lists(self.drop_columns)
        self._json_columns = expand_column_lists(self.json_columns)

        # Derive EOA address from private key if not explicitly set
        if self.private_key and not self.address:
            self.address = Account.from_key(self.private_key).address

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
            page_len = getattr(page, "attrs", {}).get("_raw_count", len(page))
            offset += page_len
            len_pages = page_len
            if progress_bar:
                progress_bar.update(1)
        if progress_bar:
            progress_bar.close()
        return pd.concat(data, ignore_index=True)

    def _build_l1_headers(
        self,
        *,
        nonce: int = 0,
        server_timestamp: str | None = None,
        message: str = "This message attests that I control the given wallet",
    ) -> dict:
        """
        Build EIP-712 L1 headers (POLY_SIGNATURE is an EIP-712 sig).
        Only needed for /auth/api-key (create) and /auth/derive-api-key.
        """
        # L1 auth always uses the EOA address (derived from private_key),
        # NOT self.address which may be the proxy wallet.
        eoa = Account.from_key(self.private_key).address
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
            "address": eoa,
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
        sig = "0x" + Account.sign_message(signable, private_key=self.private_key).signature.hex()
        return {
            "POLY_ADDRESS": eoa,
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
        timestamp: int | None = None,
    ) -> dict:
        """
        Build Polymarket L2 headers for private CLOB endpoints.
        """
        addr = self.address
        if self.private_key:
            addr = Account.from_key(self.private_key).address
        ts = str(timestamp if timestamp is not None else int(time.time()))
        msg = f"{ts}{method.upper()}{request_path}"
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            msg += body_str
        secret_bytes = base64.urlsafe_b64decode(self._api_secret)
        sig = base64.urlsafe_b64encode(
            hmac.new(secret_bytes, msg.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        return {
            "POLY_ADDRESS": addr,
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
            # Lazy auto-derive: try derive then create on first L2 call
            if self.private_key:
                try:
                    creds = self.derive_api_key()
                except Exception:
                    creds = self.create_api_key()
                self._api_key = creds["apiKey"]
                self._api_secret = creds["secret"]
                self._api_passphrase = creds["passphrase"]
                return
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
        timestamp: int | None = None,
    ) -> dict:
        ts = str(timestamp if timestamp is not None else int(time.time()))
        msg = f"{ts}{method.upper()}{request_path}"
        if body is not None:
            msg += json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        secret_bytes = base64.urlsafe_b64decode(self._builder_api_secret)
        sig = base64.urlsafe_b64encode(
            hmac.new(secret_bytes, msg.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
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

    def preprocess_dict(self, data: dict) -> dict:
        """Apply type coercion to a single dict (same rules as preprocess_dataframe)."""
        return _preprocess_dict(
            data,
            numeric_columns=self.numeric_columns,
            str_datetime_columns=self.str_datetime_columns,
            int_datetime_columns=self.int_datetime_columns,
            bool_columns=self.bool_columns,
            drop_columns=self.drop_columns,
            json_columns=self.json_columns,
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

    def get_series_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all series and return a single DataFrame."""
        return self._autopage(self.get_series, **kwargs)

    def get_teams_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all teams and return a single DataFrame."""
        return self._autopage(self.get_teams, **kwargs)

    def get_comments_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all comments and return a single DataFrame."""
        return self._autopage(self.get_comments, **kwargs)

    def get_comments_by_user_address_all(self, user_address: str, **kwargs) -> pd.DataFrame:
        """Auto-page through all comments by a user and return a single DataFrame."""
        return self._autopage(self.get_comments_by_user_address, user_address=user_address, **kwargs)

    def get_positions_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all positions and return a single DataFrame."""
        return self._autopage(self.get_positions, **kwargs)

    def get_closed_positions_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all closed positions and return a single DataFrame."""
        return self._autopage(self.get_closed_positions, **kwargs)

    def get_market_positions_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all market positions and return a single DataFrame."""
        return self._autopage(self.get_market_positions, **kwargs)

    def get_trades_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all trades and return a single DataFrame."""
        return self._autopage(self.get_trades, **kwargs)

    def get_user_activity_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all user activity and return a single DataFrame."""
        return self._autopage(self.get_user_activity, **kwargs)

    def get_leaderboard_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through the full leaderboard and return a single DataFrame."""
        return self._autopage(self.get_leaderboard, **kwargs)

    def get_builder_leaderboard_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through the full builder leaderboard and return a single DataFrame."""
        return self._autopage(self.get_builder_leaderboard, **kwargs)

    def get_sampling_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all sampling markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_sampling_markets, **kwargs)

    def get_simplified_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all simplified markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_simplified_markets, **kwargs)

    def get_sampling_simplified_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all sampling simplified markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_sampling_simplified_markets, **kwargs)

    def get_rewards_markets_current_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all current reward configs and return a single DataFrame."""
        return self._autopage_cursor(self.get_rewards_markets_current, **kwargs)

    def get_rewards_markets_multi_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all reward markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_rewards_markets_multi, **kwargs)

    def get_rewards_earnings_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all user earnings and return a single DataFrame."""
        return self._autopage_cursor(self.get_rewards_earnings, **kwargs)

    def get_rewards_user_markets_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all user reward markets and return a single DataFrame."""
        return self._autopage_cursor(self.get_rewards_user_markets, **kwargs)

    def get_user_trades_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all user trades and return a single DataFrame."""
        return self._autopage_cursor(self.get_user_trades, **kwargs)

    def get_active_orders_all(self, **kwargs) -> pd.DataFrame:
        """Auto-page through all active orders and return a single DataFrame."""
        return self._autopage_cursor(self.get_active_orders, **kwargs)

    # ── Order building & submission ─────────────────────────────────────

    @staticmethod
    def _get_order_amounts(
        side: str, price: float, size: float, tick_size: str
    ) -> tuple[int, int, int]:
        """Calculate makerAmount and takerAmount from price/size.

        Returns (side_int, maker_amount, taker_amount) in 6-decimal base units.
        """
        if tick_size not in _TICK_SIZES:
            raise ValueError(f"Invalid tick_size={tick_size!r}. Must be one of {list(_TICK_SIZES)}")
        price_dec, size_dec, amount_dec = _TICK_SIZES[tick_size]
        raw_price = _round_normal(price, price_dec)

        side_upper = side.upper()
        if side_upper == "BUY":
            raw_taker = _round_down(size, size_dec)
            raw_maker = raw_taker * raw_price
            if _decimal_places(raw_maker) > amount_dec:
                raw_maker = _round_up(raw_maker, amount_dec + 4)
                if _decimal_places(raw_maker) > amount_dec:
                    raw_maker = _round_down(raw_maker, amount_dec)
            return 0, _to_token_decimals(raw_maker), _to_token_decimals(raw_taker)
        elif side_upper == "SELL":
            raw_maker = _round_down(size, size_dec)
            raw_taker = raw_maker * raw_price
            if _decimal_places(raw_taker) > amount_dec:
                raw_taker = _round_up(raw_taker, amount_dec + 4)
                if _decimal_places(raw_taker) > amount_dec:
                    raw_taker = _round_down(raw_taker, amount_dec)
            return 1, _to_token_decimals(raw_maker), _to_token_decimals(raw_taker)
        else:
            raise ValueError(f"side must be 'BUY' or 'SELL', got {side!r}")

    def build_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        *,
        fee_rate_bps: int | None = None,
        expiration: int | pd.Timestamp | str = 0,
        nonce: int = 0,
        neg_risk: bool | None = None,
        tick_size: str | None = None,
    ) -> SignedOrder:
        """Build and sign a CLOB order, ready for :meth:`place_order`.

        Args:
            token_id: CLOB token ID (ERC-1155 conditional token).
            price: Limit price per share (0–1).
            size: Number of shares (conditional tokens).
            side: ``"BUY"`` or ``"SELL"``.
            fee_rate_bps: Fee rate in basis points. Auto-fetched from the CLOB
                API if not provided.
            expiration: Unix timestamp, ``pd.Timestamp``, or ISO-8601 string
                for GTD orders. ``0`` = no expiry.
            nonce: Order nonce for on-chain cancellation (default 0).
            neg_risk: ``True`` if the market is neg-risk. Auto-fetched if not
                provided.
            tick_size: Market tick size (``"0.1"``, ``"0.01"``, ``"0.001"``,
                or ``"0.0001"``). Auto-fetched if not provided.

        Returns:
            dict: Signed order dict with all fields expected by :meth:`place_order`.
        """
        if not self.private_key:
            raise PolymarketAuthError(detail="private_key is required to build orders.")

        # Auto-fetch market params from CLOB API (cached per token_id)
        if neg_risk is None:
            neg_risk = self.get_neg_risk(token_id)
        if tick_size is None:
            tick_size = str(self.get_tick_size(token_id))
        if fee_rate_bps is None:
            fee_rate_bps = self.get_fee_rate(token_id)

        expiration = to_unix_timestamp(expiration)

        side_int, maker_amount, taker_amount = self._get_order_amounts(side, price, size, tick_size)

        # EOA signs; maker is the funder (proxy wallet or EOA)
        eoa = Account.from_key(self.private_key).address
        maker = self.address or eoa
        exchange = NEG_RISK_CTF_EXCHANGE if neg_risk else CTF_EXCHANGE
        salt = round(time.time() * random.random())
        sig_type = self.signature_type if self.signature_type is not None else 0

        # EIP-712 signing
        domain = {
            "name": "Polymarket CTF Exchange",
            "version": "1",
            "chainId": self.chain_id,
            "verifyingContract": exchange,
        }
        types = {
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
            ],
        }
        message = {
            "salt": salt,
            "maker": maker,
            "signer": eoa,
            "taker": ZERO_ADDRESS,
            "tokenId": int(token_id),
            "makerAmount": maker_amount,
            "takerAmount": taker_amount,
            "expiration": expiration,
            "nonce": nonce,
            "feeRateBps": fee_rate_bps,
            "side": side_int,
            "signatureType": sig_type,
        }
        signable = encode_typed_data(
            full_message={
                "domain": domain,
                "types": types,
                "primaryType": "Order",
                "message": message,
            }
        )
        sig = "0x" + Account.sign_message(signable, private_key=self.private_key).signature.hex()

        return {
            "salt": salt,
            "maker": maker,
            "signer": eoa,
            "taker": ZERO_ADDRESS,
            "tokenId": token_id,
            "makerAmount": str(maker_amount),
            "takerAmount": str(taker_amount),
            "expiration": str(expiration),
            "nonce": str(nonce),
            "feeRateBps": str(fee_rate_bps),
            "side": side.upper(),
            "signatureType": sig_type,
            "signature": sig,
        }

    def submit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "GTC",
        **kwargs,
    ) -> SendOrderResponse:
        """Build, sign, and place an order in a single call.

        Args:
            token_id: CLOB token ID (ERC-1155 conditional token).
            price: Limit price per share (0–1).
            size: Number of shares (conditional tokens).
            side: ``"BUY"`` or ``"SELL"``.
            order_type: ``"GTC"`` (default), ``"FOK"``, ``"GTD"``, or ``"FAK"``.
            **kwargs: Forwarded to :meth:`build_order` (``neg_risk``,
                ``tick_size``, ``fee_rate_bps``, ``expiration``, ``nonce``).

        Returns:
            dict: API response from the CLOB order endpoint.
        """
        self._require_l2_auth()
        order = self.build_order(token_id, price, size, side, **kwargs)
        return self.place_order(order=order, owner=self._api_key, orderType=order_type)

    _BATCH_SIZE = 15  # CLOB API max orders per /orders call

    def submit_orders(
        self,
        orders: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build, sign, and place multiple orders from a DataFrame.

        Required columns: ``token_id``, ``price``, ``size``, ``side``.

        Optional columns: ``order_type`` (default ``"GTC"``), ``expiration``,
        ``nonce``, ``neg_risk``, ``tick_size``, ``fee_rate_bps``.

        Market parameters (``neg_risk``, ``tick_size``, ``fee_rate_bps``) are
        auto-fetched from the CLOB API (and cached) when not provided.

        Orders are batched in groups of 15 (the CLOB limit) and submitted
        via the ``/orders`` endpoint.

        Args:
            orders: DataFrame with one row per order.

        Returns:
            pd.DataFrame: API responses for each batch.
        """
        self._require_l2_auth()

        # Build and sign each order
        signed = []
        for row in orders.itertuples(index=False):
            order: dict = dict(
                self.build_order(
                    token_id=str(row.token_id),
                    price=float(row.price),
                    size=float(row.size),
                    side=str(row.side),
                    fee_rate_bps=getattr(row, "fee_rate_bps", None),
                    expiration=getattr(row, "expiration", 0),
                    nonce=getattr(row, "nonce", 0),
                    neg_risk=getattr(row, "neg_risk", None),
                    tick_size=getattr(row, "tick_size", None),
                )
            )
            order["owner"] = self._api_key
            order["orderType"] = getattr(row, "order_type", "GTC") or "GTC"
            signed.append(order)

        # Batch submit via /orders endpoint (max 15 per call)
        results = []
        for i in range(0, len(signed), self._BATCH_SIZE):
            batch_df = pd.DataFrame(signed[i : i + self._BATCH_SIZE])
            resp = self.place_orders(batch_df)
            results.append(resp)

        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()
