"""PolymarketPandas — core HTTP client dataclass with order building and pagination."""

import base64
import hashlib
import hmac
import inspect
import json
import logging
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
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from tqdm import tqdm

from polymarket_pandas._version import __version__
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
    UmaMixin,
    XTrackerMixin,
)
from polymarket_pandas.types import SendOrderResponse, SignedOrder
from polymarket_pandas.utils import (
    DEFAULT_BOOL_COLUMNS,
    DEFAULT_DICT_COLUMNS,
    DEFAULT_DROP_COLUMNS,
    DEFAULT_INT_DATETIME_COLUMNS,
    DEFAULT_JSON_COLUMNS,
    DEFAULT_MS_INT_DATETIME_COLUMNS,
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

logger = logging.getLogger("polymarket_pandas")
# Library convention: consumers choose where log records go. NullHandler
# prevents "no handlers found" warnings in contexts that don't configure logging.
logger.addHandler(logging.NullHandler())

_REDACTED = "***REDACTED***"
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "poly_api_key",
        "poly_passphrase",
        "poly_signature",
        "poly_builder_api_key",
        "poly_builder_passphrase",
        "poly_builder_signature",
    }
)


def _redact_headers(headers) -> dict:
    """Return a copy of headers with sensitive values replaced by ``***REDACTED***``."""
    return {
        k: (_REDACTED if k.lower() in _SENSITIVE_HEADERS else v) for k, v in dict(headers).items()
    }


def _is_retryable_error(exc: BaseException) -> bool:
    """Retry on network errors and 429/5xx HTTP responses."""
    if isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ),
    ):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


# ── CTF Exchange V2 contract addresses (Polygon mainnet) ───────────
# Polymarket CLOB V2 cutover: 2026-04-28 ~11:00 UTC. V1 addresses retired.
CTF_EXCHANGE = "0xE111180000d2663C0091e4f400237545B87B996B"
NEG_RISK_CTF_EXCHANGE = "0xe2222d279d744050d28e00520010520000310F59"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ZERO_BYTES32 = "0x" + "00" * 32

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
    UmaMixin,
    RewardsMixin,
    XTrackerMixin,
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
    xtracker_url: str = field(default="https://xtracker.polymarket.com/api/", repr=False)
    rpc_url: str | None = field(default=None, repr=False)
    proxy_url: str | None = field(default=None, repr=False)
    address: str | None = field(default=None, repr=False)
    private_funder_key: str | None = field(default=None, repr=False)
    private_key: str | None = field(default=None, repr=False)
    signature_type: int | None = field(default=1, repr=False)
    chain_id: int = field(default=137, repr=False)
    timeout: int | float | httpx.Timeout = field(default=30, repr=False)
    max_pages: int = field(default=100, repr=False)
    max_retries: int = field(default=3, repr=False)
    user_agent: str | None = field(default=None, repr=False)
    tqdm_description: str = field(default="", repr=True)
    use_tqdm: bool = field(default=True, repr=True)
    _api_key: str | None = field(default=None, repr=False)
    _api_secret: str | None = field(default=None, repr=False)
    _api_passphrase: str | None = field(default=None, repr=False)
    _builder_api_key: str | None = field(default=None, repr=False)
    _builder_api_secret: str | None = field(default=None, repr=False)
    _builder_api_passphrase: str | None = field(default=None, repr=False)
    builder_code: str | None = field(default=None, repr=False)
    _relayer_api_key: str | None = field(default=None, repr=False)
    _relayer_api_key_address: str | None = field(default=None, repr=False)
    numeric_columns: tuple = field(default=DEFAULT_NUMERIC_COLUMNS)
    str_datetime_columns: tuple = field(default=DEFAULT_STR_DATETIME_COLUMNS)
    int_datetime_columns: tuple = field(default=DEFAULT_INT_DATETIME_COLUMNS)
    ms_int_datetime_columns: tuple = field(default=DEFAULT_MS_INT_DATETIME_COLUMNS)
    bool_columns: tuple = field(default=DEFAULT_BOOL_COLUMNS)
    drop_columns: tuple = field(default=DEFAULT_DROP_COLUMNS)
    json_columns: tuple = field(default=DEFAULT_JSON_COLUMNS)
    dict_columns: tuple = field(default=DEFAULT_DICT_COLUMNS)

    # Mapping: (field_name, env_var, fallback)
    _ENV_DEFAULTS: dict = field(
        default_factory=lambda: {
            "rpc_url": ("POLYMARKET_RPC_URL", "https://polygon-rpc.com"),
            "proxy_url": ("HTTP_PROXY", None),
            "address": ("POLYMARKET_ADDRESS", None),
            "private_funder_key": ("POLYMARKET_FUNDER", None),
            "private_key": ("POLYMARKET_PRIVATE_KEY", None),
            "_api_key": ("POLYMARKET_API_KEY", None),
            "_api_secret": ("POLYMARKET_API_SECRET", None),
            "_api_passphrase": ("POLYMARKET_API_PASSPHRASE", None),
            "_builder_api_key": ("POLYMARKET_BUILDER_API_KEY", None),
            "_builder_api_secret": ("POLYMARKET_BUILDER_API_SECRET", None),
            "_builder_api_passphrase": ("POLYMARKET_BUILDER_API_PASSPHRASE", None),
            "builder_code": ("POLYMARKET_BUILDER_CODE", None),
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

        # Normalize timeout to httpx.Timeout so connect/read/write/pool are
        # independently bounded. A scalar applies to all four phases.
        if isinstance(self.timeout, (int, float)):
            self._timeout = httpx.Timeout(float(self.timeout))
        else:
            self._timeout = self.timeout

        ua = self.user_agent or (
            f"polymarket-pandas/{__version__} "
            "(+https://github.com/sigma-quantiphi/polymarket-pandas)"
        )
        self._client = httpx.Client(
            proxy=self.proxy_url,
            timeout=self._timeout,
            headers={"User-Agent": ua, "Accept": "application/json"},
        )
        self._numeric_columns = expand_column_lists(self.numeric_columns)
        self._str_datetime_columns = expand_column_lists(self.str_datetime_columns)
        self._int_datetime_columns = expand_column_lists(self.int_datetime_columns)
        self._ms_int_datetime_columns = expand_column_lists(self.ms_int_datetime_columns)
        self._bool_columns = expand_column_lists(self.bool_columns)
        self._drop_columns = expand_column_lists(self.drop_columns)
        self._json_columns = expand_column_lists(self.json_columns)
        self._dict_columns = expand_column_lists(self.dict_columns)

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

    def _send_request(
        self,
        *,
        method: str,
        url: str,
        params: dict | None = None,
        json: dict | list | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Send a request via ``self._client`` with retries on network + 429/5xx.

        Successful 2xx responses return immediately. Retryable failures
        (connect/read/write/pool errors, 429, 5xx) are retried with
        exponential backoff + jitter up to ``self.max_retries`` attempts.
        Non-retryable 4xx responses are returned unchanged so
        ``_handle_response`` can map them to the ``Polymarket*Error`` hierarchy.
        """
        attempts = max(1, self.max_retries + 1)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception(_is_retryable_error),
        )
        def _do() -> httpx.Response:
            request = self._client.build_request(
                method=method,
                url=url,
                params=params,
                json=json,
                headers=headers,
            )
            logger.debug(
                "request %s %s headers=%s",
                request.method,
                request.url,
                _redact_headers(request.headers),
            )
            resp = self._client.send(request)
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                retry_after = resp.headers.get("Retry-After")
                logger.warning(
                    "retryable response %s for %s %s (retry-after=%s)",
                    resp.status_code,
                    request.method,
                    request.url,
                    retry_after,
                )
                resp.raise_for_status()  # triggers HTTPStatusError → tenacity retry
            return resp

        try:
            return _do()
        except httpx.HTTPStatusError as exc:
            # Retries exhausted on a 429/5xx. Return the response so
            # _handle_response can map it to the right Polymarket*Error.
            return exc.response

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

    def _has_builder_creds(self) -> bool:
        return bool(
            self._builder_api_key and self._builder_api_secret and self._builder_api_passphrase
        )

    def _require_builder_auth(self) -> None:
        if not self._has_builder_creds():
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
        response = self._send_request(
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
        response = self._send_request(
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
        response = self._send_request(
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
        response = self._send_request(
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
        response = self._send_request(
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
        response = self._send_request(
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
        response = self._send_request(
            method=method,
            url=f"{self.bridge_url}{path}",
            params=filter_params(params),
            json=data,
        )
        return self._handle_response(response)

    def _request_xtracker(
        self,
        path: str,
        method: str = "GET",
        params: dict | None = None,
        data: dict | list | None = None,
    ) -> dict | list:
        response = self._send_request(
            method=method,
            url=f"{self.xtracker_url}{path}",
            params=filter_params(params),
            json=data,
        )
        payload = self._handle_response(response)
        # xtracker wraps every response in {success, data, message}; unwrap
        # once here so mixin methods stay one-liners.
        if isinstance(payload, dict) and "success" in payload:
            if not payload.get("success", True):
                raise PolymarketAPIError(
                    status_code=response.status_code,
                    url=str(response.request.url),
                    detail=payload.get("error") or payload.get("message"),
                )
            return payload.get("data", payload)
        return payload

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
            ms_int_datetime_columns=self._ms_int_datetime_columns,
            bool_columns=self._bool_columns,
            drop_columns=self._drop_columns,
            json_columns=self._json_columns,
            dict_columns=self._dict_columns,
        )

    def preprocess_dict(self, data: dict) -> dict:
        """Apply type coercion to a single dict (same rules as preprocess_dataframe)."""
        return _preprocess_dict(
            data,
            numeric_columns=self.numeric_columns,
            str_datetime_columns=self.str_datetime_columns,
            int_datetime_columns=self.int_datetime_columns,
            ms_int_datetime_columns=self.ms_int_datetime_columns,
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

    # ── Offset-paginated _all methods ─────────────────────────────────

    def get_tags_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        order: list[str] | None = None,
        ascending: bool | None = None,
        include_template: bool | None = None,
        is_carousel: bool | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all tags and return a single DataFrame."""
        return self._autopage(
            self.get_tags,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            include_template=include_template,
            is_carousel=is_carousel,
        )

    def get_events_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
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
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
        expand_markets: bool | None = True,
        expand_clob_token_ids: bool | None = True,
        expand_outcomes: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all events and return a single DataFrame."""
        return self._autopage(
            self.get_events,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            id=id,
            slug=slug,
            tag_id=tag_id,
            exclude_tag_id=exclude_tag_id,
            related_tags=related_tags,
            featured=featured,
            cyom=cyom,
            include_chat=include_chat,
            include_template=include_template,
            recurrence=recurrence,
            closed=closed,
            start_date_min=start_date_min,
            start_date_max=start_date_max,
            end_date_min=end_date_min,
            end_date_max=end_date_max,
            expand_markets=expand_markets,
            expand_clob_token_ids=expand_clob_token_ids,
            expand_outcomes=expand_outcomes,
        )

    def get_events_keyset_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        after_cursor: str | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        id: list[int] | None = None,
        slug: list[str] | None = None,
        closed: bool | None = None,
        live: bool | None = None,
        featured: bool | None = None,
        cyom: bool | None = None,
        title_search: str | None = None,
        liquidity_min: float | None = None,
        liquidity_max: float | None = None,
        volume_min: float | None = None,
        volume_max: float | None = None,
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
        start_time_min: str | pd.Timestamp | None = None,
        start_time_max: str | pd.Timestamp | None = None,
        tag_id: list[int] | None = None,
        tag_slug: str | None = None,
        exclude_tag_id: list[int] | None = None,
        related_tags: bool | None = None,
        tag_match: str | None = None,
        series_id: list[int] | None = None,
        game_id: list[int] | None = None,
        event_date: str | pd.Timestamp | None = None,
        event_week: int | None = None,
        featured_order: bool | None = None,
        recurrence: str | None = None,
        created_by: list[str] | None = None,
        parent_event_id: int | None = None,
        include_children: bool | None = None,
        partner_slug: str | None = None,
        include_chat: bool | None = None,
        include_template: bool | None = None,
        include_best_lines: bool | None = None,
        locale: str | None = None,
        expand_markets: bool | None = True,
        expand_clob_token_ids: bool | None = True,
        expand_outcomes: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all events via keyset pagination.

        Follows the server-supplied ``next_cursor`` until it is omitted (final
        page) or ``max_pages`` is reached. Accepts the same filters as
        :meth:`get_events_keyset` plus ``max_pages`` and a starting
        ``after_cursor``.

        Prefer this over :meth:`get_events_all` for bulk scans — it uses the
        keyset endpoint (stable ordering, up to 500 rows/page) instead of
        offset pagination.

        Returns:
            pd.DataFrame — concatenation of all pages' ``data`` frames.
        """
        pages: list[pd.DataFrame] = []
        cursor = after_cursor
        n = 0
        while True:
            page = self.get_events_keyset(
                limit=limit,
                after_cursor=cursor,
                order=order,
                ascending=ascending,
                id=id,
                slug=slug,
                closed=closed,
                live=live,
                featured=featured,
                cyom=cyom,
                title_search=title_search,
                liquidity_min=liquidity_min,
                liquidity_max=liquidity_max,
                volume_min=volume_min,
                volume_max=volume_max,
                start_date_min=start_date_min,
                start_date_max=start_date_max,
                end_date_min=end_date_min,
                end_date_max=end_date_max,
                start_time_min=start_time_min,
                start_time_max=start_time_max,
                tag_id=tag_id,
                tag_slug=tag_slug,
                exclude_tag_id=exclude_tag_id,
                related_tags=related_tags,
                tag_match=tag_match,
                series_id=series_id,
                game_id=game_id,
                event_date=event_date,
                event_week=event_week,
                featured_order=featured_order,
                recurrence=recurrence,
                created_by=created_by,
                parent_event_id=parent_event_id,
                include_children=include_children,
                partner_slug=partner_slug,
                include_chat=include_chat,
                include_template=include_template,
                include_best_lines=include_best_lines,
                locale=locale,
                expand_markets=expand_markets,
                expand_clob_token_ids=expand_clob_token_ids,
                expand_outcomes=expand_outcomes,
            )
            pages.append(page["data"])
            cursor = page.get("next_cursor")
            n += 1
            if not cursor or (max_pages is not None and n >= max_pages):
                break
        return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()

    def get_markets_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
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
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
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
        expand_clob_token_ids: bool = True,
        expand_events: bool = True,
        expand_series: bool = True,
        expand_outcomes: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all markets and return a single DataFrame."""
        return self._autopage(
            self.get_markets,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            id=id,
            slug=slug,
            clob_token_ids=clob_token_ids,
            condition_ids=condition_ids,
            market_maker_address=market_maker_address,
            liquidity_num_min=liquidity_num_min,
            liquidity_num_max=liquidity_num_max,
            volume_num_min=volume_num_min,
            volume_num_max=volume_num_max,
            start_date_min=start_date_min,
            start_date_max=start_date_max,
            end_date_min=end_date_min,
            end_date_max=end_date_max,
            tag_id=tag_id,
            related_tags=related_tags,
            cyom=cyom,
            uma_resolution_status=uma_resolution_status,
            game_id=game_id,
            sports_market_types=sports_market_types,
            rewards_min_size=rewards_min_size,
            question_ids=question_ids,
            include_tag=include_tag,
            closed=closed,
            expand_clob_token_ids=expand_clob_token_ids,
            expand_events=expand_events,
            expand_series=expand_series,
            expand_outcomes=expand_outcomes,
        )

    def get_markets_keyset_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        after_cursor: str | None = None,
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
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
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
        expand_clob_token_ids: bool = True,
        expand_events: bool = True,
        expand_series: bool = True,
        expand_outcomes: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all markets via keyset pagination.

        Follows the server-supplied ``next_cursor`` until it is omitted (final
        page) or ``max_pages`` is reached. Accepts the same filters as
        :meth:`get_markets_keyset` plus ``max_pages`` and a starting
        ``after_cursor``.

        Prefer this over :meth:`get_markets_all` for bulk scans — it uses the
        keyset endpoint (stable ordering, up to 1000 rows/page) instead of
        offset pagination.

        Returns:
            pd.DataFrame — concatenation of all pages' ``data`` frames.
        """
        pages: list[pd.DataFrame] = []
        cursor = after_cursor
        n = 0
        while True:
            page = self.get_markets_keyset(
                limit=limit,
                after_cursor=cursor,
                order=order,
                ascending=ascending,
                id=id,
                slug=slug,
                clob_token_ids=clob_token_ids,
                condition_ids=condition_ids,
                market_maker_address=market_maker_address,
                liquidity_num_min=liquidity_num_min,
                liquidity_num_max=liquidity_num_max,
                volume_num_min=volume_num_min,
                volume_num_max=volume_num_max,
                start_date_min=start_date_min,
                start_date_max=start_date_max,
                end_date_min=end_date_min,
                end_date_max=end_date_max,
                tag_id=tag_id,
                related_tags=related_tags,
                cyom=cyom,
                uma_resolution_status=uma_resolution_status,
                game_id=game_id,
                sports_market_types=sports_market_types,
                rewards_min_size=rewards_min_size,
                question_ids=question_ids,
                include_tag=include_tag,
                closed=closed,
                expand_clob_token_ids=expand_clob_token_ids,
                expand_events=expand_events,
                expand_series=expand_series,
                expand_outcomes=expand_outcomes,
            )
            pages.append(page["data"])
            cursor = page.get("next_cursor")
            n += 1
            if not cursor or (max_pages is not None and n >= max_pages):
                break
        return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()

    def get_series_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        order: list[str] | None = None,
        ascending: bool | None = None,
        slug: list[str] | None = None,
        categories_ids: list[int] | None = None,
        categories_labels: list[str] | None = None,
        closed: bool | None = None,
        include_chat: bool | None = None,
        recurrence: str | None = None,
        expand_events: bool = False,
        expand_event_tags: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all series and return a single DataFrame."""
        return self._autopage(
            self.get_series,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            slug=slug,
            categories_ids=categories_ids,
            categories_labels=categories_labels,
            closed=closed,
            include_chat=include_chat,
            recurrence=recurrence,
            expand_events=expand_events,
            expand_event_tags=expand_event_tags,
        )

    def get_teams_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        order: list[str] | None = None,
        ascending: bool | None = None,
        league: list[str] | None = None,
        name: list[str] | None = None,
        abbreviation: list[str] | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all teams and return a single DataFrame."""
        return self._autopage(
            self.get_teams,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            league=league,
            name=name,
            abbreviation=abbreviation,
        )

    def get_comments_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        order: str | None = None,
        ascending: bool | None = None,
        parent_entity_type: str | None = None,
        parent_entity_id: int | None = None,
        get_positions: bool | None = None,
        holders_only: bool | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all comments and return a single DataFrame."""
        return self._autopage(
            self.get_comments,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            get_positions=get_positions,
            holders_only=holders_only,
        )

    def get_comments_by_user_address_all(
        self,
        user_address: str,
        *,
        max_pages: int | None = None,
        limit: int | None = 300,
        order: str | None = None,
        ascending: bool | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all comments by a user and return a single DataFrame."""
        return self._autopage(
            self.get_comments_by_user_address,
            user_address=user_address,
            max_pages=max_pages,
            limit=limit,
            order=order,
            ascending=ascending,
        )

    def get_positions_all(
        self,
        user: str,
        *,
        max_pages: int | None = None,
        limit: int | None = 100,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        sizeThreshold: float | None = 1,
        redeemable: bool | None = None,
        mergeable: bool | None = None,
        sortBy: str | None = "TOKENS",
        sortDirection: str | None = "DESC",
        title: str | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all positions and return a single DataFrame."""
        return self._autopage(
            self.get_positions,
            max_pages=max_pages,
            user=user,
            limit=limit,
            market=market,
            eventId=eventId,
            sizeThreshold=sizeThreshold,
            redeemable=redeemable,
            mergeable=mergeable,
            sortBy=sortBy,
            sortDirection=sortDirection,
            title=title,
        )

    def get_closed_positions_all(
        self,
        user: str,
        *,
        max_pages: int | None = None,
        limit: int | None = 10,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        title: str | None = None,
        sortBy: str | None = "REALIZEDPNL",
        sortDirection: str | None = "DESC",
    ) -> pd.DataFrame:
        """Auto-page through all closed positions and return a single DataFrame."""
        return self._autopage(
            self.get_closed_positions,
            max_pages=max_pages,
            user=user,
            limit=limit,
            market=market,
            eventId=eventId,
            title=title,
            sortBy=sortBy,
            sortDirection=sortDirection,
        )

    def get_market_positions_all(
        self,
        market: str,
        *,
        max_pages: int | None = None,
        limit: int | None = 50,
        user: str | None = None,
        status: str | None = "ALL",
        sortBy: str | None = "TOTAL_PNL",
        sortDirection: str | None = "DESC",
    ) -> pd.DataFrame:
        """Auto-page through all market positions and return a single DataFrame."""
        return self._autopage(
            self.get_market_positions,
            max_pages=max_pages,
            market=market,
            limit=limit,
            user=user,
            status=status,
            sortBy=sortBy,
            sortDirection=sortDirection,
        )

    def get_trades_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 100,
        takerOnly: bool | None = True,
        filterType: str | None = None,
        filterAmount: float | None = None,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        user: str | None = None,
        side: str | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all trades and return a single DataFrame."""
        return self._autopage(
            self.get_trades,
            max_pages=max_pages,
            limit=limit,
            takerOnly=takerOnly,
            filterType=filterType,
            filterAmount=filterAmount,
            market=market,
            eventId=eventId,
            user=user,
            side=side,
        )

    def get_user_activity_all(
        self,
        user: str,
        *,
        max_pages: int | None = None,
        limit: int | None = 100,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        type: list[str] | None = None,
        start: int | pd.Timestamp | None = None,
        end: int | pd.Timestamp | None = None,
        sortBy: str | None = "TIMESTAMP",
        sortDirection: str | None = "DESC",
        side: str | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all user activity and return a single DataFrame."""
        return self._autopage(
            self.get_user_activity,
            max_pages=max_pages,
            user=user,
            limit=limit,
            market=market,
            eventId=eventId,
            type=type,
            start=start,
            end=end,
            sortBy=sortBy,
            sortDirection=sortDirection,
            side=side,
        )

    def get_leaderboard_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 25,
        category: str | None = "OVERALL",
        timePeriod: str | None = "DAY",
        orderBy: str | None = "PNL",
        user: str | None = None,
        userName: str | None = None,
    ) -> pd.DataFrame:
        """Auto-page through the full leaderboard and return a single DataFrame."""
        return self._autopage(
            self.get_leaderboard,
            max_pages=max_pages,
            limit=limit,
            category=category,
            timePeriod=timePeriod,
            orderBy=orderBy,
            user=user,
            userName=userName,
        )

    def get_builder_leaderboard_all(
        self,
        *,
        max_pages: int | None = None,
        limit: int | None = 25,
        timePeriod: str | None = "DAY",
    ) -> pd.DataFrame:
        """Auto-page through the full builder leaderboard and return a single DataFrame."""
        return self._autopage(
            self.get_builder_leaderboard,
            max_pages=max_pages,
            limit=limit,
            timePeriod=timePeriod,
        )

    # ── Cursor-paginated _all methods ──────────────────────────────────

    def get_sampling_markets_all(
        self,
        *,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all sampling markets and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_sampling_markets,
            max_pages=max_pages,
        )

    def get_simplified_markets_all(
        self,
        *,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all simplified markets and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_simplified_markets,
            max_pages=max_pages,
        )

    def get_sampling_simplified_markets_all(
        self,
        *,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all sampling simplified markets and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_sampling_simplified_markets,
            max_pages=max_pages,
        )

    def get_rewards_markets_current_all(
        self,
        *,
        max_pages: int | None = None,
        sponsored: bool | None = None,
        expand_rewards_config: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all current reward configs and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_rewards_markets_current,
            max_pages=max_pages,
            sponsored=sponsored,
            expand_rewards_config=expand_rewards_config,
        )

    def get_rewards_markets_multi_all(
        self,
        *,
        max_pages: int | None = None,
        q: str | None = None,
        tag_slug: str | None = None,
        event_id: str | None = None,
        event_title: str | None = None,
        order_by: str | None = None,
        position: str | None = None,
        min_volume_24hr: float | None = None,
        max_volume_24hr: float | None = None,
        min_spread: float | None = None,
        max_spread: float | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page_size: int | None = None,
        expand_rewards_config: bool = False,
        expand_tokens: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all reward markets and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_rewards_markets_multi,
            max_pages=max_pages,
            q=q,
            tag_slug=tag_slug,
            event_id=event_id,
            event_title=event_title,
            order_by=order_by,
            position=position,
            min_volume_24hr=min_volume_24hr,
            max_volume_24hr=max_volume_24hr,
            min_spread=min_spread,
            max_spread=max_spread,
            min_price=min_price,
            max_price=max_price,
            page_size=page_size,
            expand_rewards_config=expand_rewards_config,
            expand_tokens=expand_tokens,
        )

    def get_rewards_earnings_all(
        self,
        date: str,
        *,
        max_pages: int | None = None,
        signature_type: int | None = None,
        maker_address: str | None = None,
        sponsored: bool | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all user earnings and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_rewards_earnings,
            max_pages=max_pages,
            date=date,
            signature_type=signature_type,
            maker_address=maker_address,
            sponsored=sponsored,
        )

    def get_rewards_user_markets_all(
        self,
        *,
        max_pages: int | None = None,
        date: str | None = None,
        signature_type: int | None = None,
        maker_address: str | None = None,
        sponsored: bool | None = None,
        q: str | None = None,
        tag_slug: str | None = None,
        favorite_markets: bool | None = None,
        no_competition: bool | None = None,
        only_mergeable: bool | None = None,
        only_open_orders: bool | None = None,
        only_open_positions: bool | None = None,
        order_by: str | None = None,
        position: str | None = None,
        page_size: int | None = None,
        expand_rewards_config: bool = False,
        expand_tokens: bool = False,
        expand_earnings: bool = False,
    ) -> pd.DataFrame:
        """Auto-page through all user reward markets and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_rewards_user_markets,
            max_pages=max_pages,
            date=date,
            signature_type=signature_type,
            maker_address=maker_address,
            sponsored=sponsored,
            q=q,
            tag_slug=tag_slug,
            favorite_markets=favorite_markets,
            no_competition=no_competition,
            only_mergeable=only_mergeable,
            only_open_orders=only_open_orders,
            only_open_positions=only_open_positions,
            order_by=order_by,
            position=position,
            page_size=page_size,
            expand_rewards_config=expand_rewards_config,
            expand_tokens=expand_tokens,
            expand_earnings=expand_earnings,
        )

    def get_user_trades_all(
        self,
        *,
        max_pages: int | None = None,
        id: str | None = None,
        taker: str | None = None,
        maker: str | None = None,
        market: str | None = None,
        before: str | pd.Timestamp | None = None,
        after: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all user trades and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_user_trades,
            max_pages=max_pages,
            id=id,
            taker=taker,
            maker=maker,
            market=market,
            before=before,
            after=after,
        )

    def get_active_orders_all(
        self,
        *,
        max_pages: int | None = None,
        id: str | None = None,
        market: str | None = None,
        asset_id: str | None = None,
    ) -> pd.DataFrame:
        """Auto-page through all active orders and return a single DataFrame."""
        return self._autopage_cursor(
            self.get_active_orders,
            max_pages=max_pages,
            id=id,
            market=market,
            asset_id=asset_id,
        )

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

    @staticmethod
    def _normalize_builder_code(code: str | None) -> str:
        """Coerce a builder code to a 0x-prefixed 32-byte hex string.

        ``None`` / empty → zero bytes32. Short hex (e.g. a 16-byte
        builder ID) is left-padded with zeros. Invalid lengths raise.
        """
        if not code:
            return ZERO_BYTES32
        s = code.lower().removeprefix("0x")
        if len(s) > 64 or any(c not in "0123456789abcdef" for c in s):
            raise ValueError(
                f"builder_code must be 0x-prefixed hex up to 32 bytes (64 hex chars); got {code!r}"
            )
        return "0x" + s.rjust(64, "0")

    def build_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        *,
        neg_risk: bool | None = None,
        tick_size: str | None = None,
        builder_code: str | None = None,
        metadata: str | None = None,
        timestamp_ms: int | None = None,
        expiration: int | pd.Timestamp | str | None = None,
    ) -> SignedOrder:
        """Build and sign a CLOB V2 order, ready for :meth:`place_order`.

        Args:
            token_id: CLOB token ID (ERC-1155 conditional token).
            price: Limit price per share (0–1). Automatically snapped to
                the market's tick size to avoid "Invalid tick size"
                rejections (valid ticks: ``0.1``, ``0.01``, ``0.001``,
                ``0.0001``).
            size: Number of shares (conditional tokens).
            side: ``"BUY"`` or ``"SELL"``.
            neg_risk: ``True`` if the market is neg-risk. Auto-fetched if not
                provided.
            tick_size: Market tick size (``"0.1"``, ``"0.01"``, ``"0.001"``,
                or ``"0.0001"``). Auto-fetched if not provided.
            builder_code: 0x-prefixed bytes32 hex (up to 64 hex chars,
                left-padded). Per-call override of ``self.builder_code``.
                Defaults to zero bytes32 (no builder attribution).
            metadata: 0x-prefixed bytes32 hex for arbitrary order metadata.
                Defaults to zero bytes32.
            timestamp_ms: Order timestamp in milliseconds. Defaults to
                ``int(time.time() * 1000)``. Replaces V1's ``nonce`` field
                for order uniqueness.
            expiration: Optional Unix-seconds expiration for GTD orders.
                Accepts ``int``, ``pd.Timestamp``, or ISO-8601 ``str``.
                **In V2 this is a wire-body field only — not part of the
                signed EIP-712 struct.** The matching engine treats it as
                a soft cancel hint. Omit (or ``0``) for GTC orders.

        Returns:
            dict: Signed order dict ready for :meth:`place_order`.
        """
        if not self.private_key:
            raise PolymarketAuthError(detail="private_key is required to build orders.")

        # Auto-fetch market params from CLOB API (cached per token_id)
        if neg_risk is None:
            neg_risk = self.get_neg_risk(token_id)
        if tick_size is None:
            tick_size = str(self.get_tick_size(token_id))

        # Snap price to the market's tick size to prevent "Invalid tick
        # size" rejections from floating-point drift.
        if tick_size in _TICK_SIZES:
            price_dec = _TICK_SIZES[tick_size][0]
            ts_float = float(tick_size)
            price = _round_normal(round(price / ts_float) * ts_float, price_dec)

        side_int, maker_amount, taker_amount = self._get_order_amounts(side, price, size, tick_size)

        # EOA signs; maker is the funder (proxy wallet or EOA)
        eoa = Account.from_key(self.private_key).address
        maker = self.address or eoa
        exchange = NEG_RISK_CTF_EXCHANGE if neg_risk else CTF_EXCHANGE
        salt = round(time.time() * random.random())
        sig_type = self.signature_type if self.signature_type is not None else 0
        ts_ms = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        meta_b32 = self._normalize_builder_code(metadata) if metadata else ZERO_BYTES32
        builder_b32 = self._normalize_builder_code(
            builder_code if builder_code is not None else self.builder_code
        )

        # EIP-712 signing — V2 domain (version="2") and 11-field Order struct
        domain = {
            "name": "Polymarket CTF Exchange",
            "version": "2",
            "chainId": self.chain_id,
            "verifyingContract": exchange,
        }
        types = {
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "metadata", "type": "bytes32"},
                {"name": "builder", "type": "bytes32"},
            ],
        }
        message = {
            "salt": salt,
            "maker": maker,
            "signer": eoa,
            "tokenId": int(token_id),
            "makerAmount": maker_amount,
            "takerAmount": taker_amount,
            "side": side_int,
            "signatureType": sig_type,
            "timestamp": ts_ms,
            "metadata": bytes.fromhex(meta_b32.removeprefix("0x")),
            "builder": bytes.fromhex(builder_b32.removeprefix("0x")),
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

        wire: dict = {
            "salt": salt,
            "maker": maker,
            "signer": eoa,
            "tokenId": token_id,
            "makerAmount": str(maker_amount),
            "takerAmount": str(taker_amount),
            "side": side.upper(),
            "signatureType": sig_type,
            "timestamp": str(ts_ms),
            "metadata": meta_b32,
            "builder": builder_b32,
            "signature": sig,
        }
        # `expiration` is a non-signed wire-body field in V2 — used by the
        # matching engine as a GTD cancel hint only. Omit when zero/None
        # so GTC orders stay clean.
        if expiration:
            wire["expiration"] = str(to_unix_timestamp(expiration))
        return wire

    def submit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: str = "GTC",
        post_only: bool = False,
        **kwargs,
    ) -> SendOrderResponse:
        """Build, sign, and place an order in a single call.

        Args:
            token_id: CLOB token ID (ERC-1155 conditional token).
            price: Limit price per share (0–1). Automatically snapped to
                the market's tick size (valid ticks: ``0.1``, ``0.01``,
                ``0.001``, ``0.0001``).
            size: Number of shares (conditional tokens).
            side: ``"BUY"`` or ``"SELL"``.
            order_type: ``"GTC"`` (default), ``"FOK"``, ``"GTD"``, or ``"FAK"``.
            post_only: If True, reject the order if it would immediately
                match (maker-only). Only valid with GTC/GTD.
            **kwargs: Forwarded to :meth:`build_order` (``neg_risk``,
                ``tick_size``, ``builder_code``, ``metadata``, ``timestamp_ms``).

        Returns:
            dict: API response from the CLOB order endpoint.

        Note:
            V2: Builder attribution is carried in the signed order's
            ``builder`` (bytes32) field. Set ``builder_code=`` here, the
            ``builder_code`` constructor arg, or the
            ``POLYMARKET_BUILDER_CODE`` env var. ``POLY_BUILDER_*`` HMAC
            headers are no longer attached to order placement.
        """
        self._require_l2_auth()
        order = self.build_order(token_id, price, size, side, **kwargs)
        return self.place_order(
            order=order, owner=self._api_key, orderType=order_type, post_only=post_only
        )

    _BATCH_SIZE = 15  # CLOB API max orders per /orders call

    def submit_orders(
        self,
        orders: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build, sign, and place multiple orders from a DataFrame.

        Required columns: ``tokenId``, ``price``, ``size``, ``side``.

        Optional columns: ``orderType`` (default ``"GTC"``), ``postOnly``
        (default ``False``), ``negRisk``, ``tickSize``, ``builderCode``,
        ``expiration`` (Unix seconds / ISO string / Timestamp; for GTD).

        Prices are automatically snapped to each market's tick size
        (valid ticks: ``0.1``, ``0.01``, ``0.001``, ``0.0001``) to
        prevent floating-point rejections.

        Market parameters (``neg_risk``, ``tick_size``) are auto-fetched
        from the CLOB API (and cached) when not provided.

        Orders are batched in groups of 15 (the CLOB limit) and submitted
        via the ``/orders`` endpoint.

        Args:
            orders: DataFrame with one row per order.

        Returns:
            pd.DataFrame: API responses for each batch.

        Note:
            V2: Builder attribution is per-order via the signed
            ``builder`` field. Provide a ``builderCode`` column or set
            ``builder_code`` on the client.
        """
        self._require_l2_auth()

        from polymarket_pandas.order_schema import SubmitOrderSchema

        SubmitOrderSchema.validate(orders)

        # Build and sign each order
        signed = []
        for row in orders.itertuples(index=False):
            order: dict = dict(
                self.build_order(
                    token_id=str(row.tokenId),
                    price=float(row.price),
                    size=float(row.size),
                    side=str(row.side),
                    neg_risk=getattr(row, "negRisk", None),
                    tick_size=getattr(row, "tickSize", None),
                    builder_code=getattr(row, "builderCode", None),
                    expiration=getattr(row, "expiration", None),
                )
            )
            order["owner"] = self._api_key
            order["orderType"] = getattr(row, "orderType", "GTC") or "GTC"
            if getattr(row, "postOnly", False):
                order["postOnly"] = True
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
