"""Async WebSocket client for Polymarket real-time data streams.

Uses the ``websockets`` library for native async I/O with automatic
reconnection, ``async for`` iteration, and async context manager support.

Usage::

    async with AsyncPolymarketWebSocket.from_client(client) as ws:
        session = await ws.market_channel(asset_ids=["15871..."])
        async for event_type, payload in session:
            print(event_type, payload)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import orjson
import pandas as pd
import websockets

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
    orderbook_meta,
)
from polymarket_pandas.utils import (
    preprocess_dataframe as _preprocess_dataframe,
)
from polymarket_pandas.utils import (
    preprocess_dict as _preprocess_dict,
)

_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
_SPORTS_URL = "wss://sports-api.polymarket.com/ws"
_RTDS_URL = "wss://ws-live-data.polymarket.com"

_MAX_RECONNECT_DELAY = 60


@dataclass
class AsyncPolymarketWebSocketSession:
    """Async WebSocket session with reconnection and ``async for`` support.

    Yields ``(event_type, payload)`` tuples where payload is a preprocessed
    ``pd.DataFrame`` or ``dict`` depending on the event type.
    """

    _url: str
    _on_open_msg: bytes | None = field(default=None, repr=False)
    _preprocess_fn: Callable | None = field(default=None, repr=False)
    _parse_fn: Callable | None = field(default=None, repr=False)
    _ping_interval: int = 10
    _ping_msg: str = "PING"
    _reconnect: bool = True
    _ws: websockets.ClientConnection | None = field(default=None, init=False, repr=False)
    _ping_task: asyncio.Task | None = field(default=None, init=False, repr=False)

    async def connect(self) -> None:
        """Establish the WebSocket connection."""
        self._ws = await websockets.connect(self._url)
        if self._on_open_msg is not None:
            await self._ws.send(self._on_open_msg)
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def subscribe(self, asset_ids: list[str], **kwargs) -> None:
        """Subscribe to additional assets on a live connection."""
        msg = {"assets_ids": asset_ids, "type": "market", **kwargs}
        await self._ws.send(orjson.dumps(msg))

    async def unsubscribe(self, asset_ids: list[str], **kwargs) -> None:
        """Unsubscribe from assets on a live connection."""
        msg = {
            "assets_ids": asset_ids,
            "type": "market",
            "action": "unsubscribe",
            **kwargs,
        }
        await self._ws.send(orjson.dumps(msg))

    async def __aiter__(self) -> AsyncIterator[tuple[str, pd.DataFrame | dict]]:
        """Iterate over parsed WebSocket messages with auto-reconnection."""
        delay = 1
        while True:
            try:
                if self._ws is None:
                    await self.connect()
                async for raw in self._ws:
                    if raw == "PONG" or raw == b"PONG":
                        continue
                    if self._parse_fn:
                        result = self._parse_fn(raw)
                        if result is None:
                            continue
                        if isinstance(result, list):
                            for item in result:
                                if item is not None:
                                    yield item
                        else:
                            yield result
                    else:
                        msg = orjson.loads(raw)
                        if isinstance(msg, list):
                            for item in msg:
                                yield item.get("event_type", ""), item
                        else:
                            yield msg.get("event_type", ""), msg
                    delay = 1  # reset backoff on successful message
            except (
                websockets.ConnectionClosed,
                websockets.ConnectionClosedError,
                ConnectionError,
                OSError,
            ):
                if not self._reconnect:
                    break
                await self.close()
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _ping_loop(self) -> None:
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(self._ping_interval)
                if self._ws:
                    await self._ws.send(self._ping_msg)
        except (asyncio.CancelledError, Exception):
            pass


@dataclass
class AsyncPolymarketWebSocket:
    """Async WebSocket client for Polymarket real-time data streams.

    Provides channel methods that return ``AsyncPolymarketWebSocketSession``
    instances supporting ``async for`` iteration and ``async with`` lifecycle.
    """

    api_key: str | None = field(default_factory=lambda: os.getenv("POLYMARKET_API_KEY"), repr=False)
    api_secret: str | None = field(
        default_factory=lambda: os.getenv("POLYMARKET_API_SECRET"), repr=False
    )
    api_passphrase: str | None = field(
        default_factory=lambda: os.getenv("POLYMARKET_API_PASSPHRASE"), repr=False
    )
    numeric_columns: tuple = field(default=DEFAULT_NUMERIC_COLUMNS)
    str_datetime_columns: tuple = field(default=DEFAULT_STR_DATETIME_COLUMNS)
    int_datetime_columns: tuple = field(default=DEFAULT_INT_DATETIME_COLUMNS)
    ms_int_datetime_columns: tuple = field(default=DEFAULT_MS_INT_DATETIME_COLUMNS)
    bool_columns: tuple = field(default=DEFAULT_BOOL_COLUMNS)
    drop_columns: tuple = field(default=DEFAULT_DROP_COLUMNS)
    json_columns: tuple = field(default=DEFAULT_JSON_COLUMNS)
    dict_columns: tuple = field(default=DEFAULT_DICT_COLUMNS)

    def __post_init__(self) -> None:
        self._numeric_columns = expand_column_lists(self.numeric_columns)
        self._str_datetime_columns = expand_column_lists(self.str_datetime_columns)
        self._int_datetime_columns = expand_column_lists(self.int_datetime_columns)
        self._ms_int_datetime_columns = expand_column_lists(self.ms_int_datetime_columns)
        self._bool_columns = expand_column_lists(self.bool_columns)
        self._drop_columns = expand_column_lists(self.drop_columns)
        self._json_columns = expand_column_lists(self.json_columns)
        self._dict_columns = expand_column_lists(self.dict_columns)

    @classmethod
    def from_client(cls, client) -> AsyncPolymarketWebSocket:
        """Share credentials and column config with an async or sync client."""
        # Support both AsyncPolymarketPandas (._sync) and PolymarketPandas
        sync = getattr(client, "_sync", client)
        return cls(
            api_key=sync._api_key,
            api_secret=sync._api_secret,
            api_passphrase=sync._api_passphrase,
            numeric_columns=sync.numeric_columns,
            str_datetime_columns=sync.str_datetime_columns,
            int_datetime_columns=sync.int_datetime_columns,
            ms_int_datetime_columns=sync.ms_int_datetime_columns,
            bool_columns=sync.bool_columns,
            drop_columns=sync.drop_columns,
            json_columns=sync.json_columns,
            dict_columns=sync.dict_columns,
        )

    # ── Private helpers ─────────────────────────────────────────────────

    def _preprocess(self, df: pd.DataFrame, *, int_datetime_unit: str = "s") -> pd.DataFrame:
        return _preprocess_dataframe(
            df,
            numeric_columns=self._numeric_columns,
            str_datetime_columns=self._str_datetime_columns,
            int_datetime_columns=self._int_datetime_columns,
            ms_int_datetime_columns=self._ms_int_datetime_columns,
            bool_columns=self._bool_columns,
            drop_columns=self._drop_columns,
            json_columns=self._json_columns,
            dict_columns=self._dict_columns,
            int_datetime_unit=int_datetime_unit,
        )

    def _preprocess_dict(self, data: dict, *, int_datetime_unit: str = "s") -> dict:
        return _preprocess_dict(
            data,
            numeric_columns=self._numeric_columns,
            str_datetime_columns=self._str_datetime_columns,
            int_datetime_columns=self._int_datetime_columns,
            ms_int_datetime_columns=self._ms_int_datetime_columns,
            bool_columns=self._bool_columns,
            drop_columns=self._drop_columns,
            json_columns=self._json_columns,
            int_datetime_unit=int_datetime_unit,
        )

    # ── Channel methods ─────────────────────────────────────────────────

    def market_channel(
        self,
        asset_ids: list[str],
        *,
        initial_dump: bool = True,
        level: int = 2,
        custom_feature_enabled: bool = True,
        ping_interval: int = 10,
        reconnect: bool = True,
    ) -> AsyncPolymarketWebSocketSession:
        """Create a market data WebSocket session.

        Returns an ``AsyncPolymarketWebSocketSession`` that yields
        ``(event_type, payload)`` tuples via ``async for``.

        Book events yield ``("book", DataFrame[OrderbookSchema])`` with columns
        ``price``, ``size``, ``side``, ``market``, ``assetId``, ``timestamp``,
        ``hash``, and optional ``minOrderSize``, ``tickSize``, ``negRisk``.

        Args:
            asset_ids: CLOB token IDs to subscribe to.
            level: Order-book depth level (1 or 2).
            initial_dump: Request an initial snapshot on connect.
            reconnect: Auto-reconnect on disconnect.
        """
        sub = orjson.dumps(
            {
                "assets_ids": asset_ids,
                "type": "market",
                "initial_dump": initial_dump,
                "level": level,
                "custom_feature_enabled": custom_feature_enabled,
            }
        )

        preprocess = self._preprocess
        preprocess_dict = self._preprocess_dict

        def _parse_single(msg):
            event_type = msg.get("event_type", "")

            if event_type == "book":
                bids = pd.json_normalize(
                    msg, record_path="bids", meta=orderbook_meta, errors="ignore"
                )
                bids["side"] = "bids"
                asks = pd.json_normalize(
                    msg, record_path="asks", meta=orderbook_meta, errors="ignore"
                )
                asks["side"] = "asks"
                return event_type, preprocess(
                    pd.concat([bids, asks], ignore_index=True), int_datetime_unit="ms"
                )

            elif event_type == "price_change":
                data = pd.json_normalize(
                    [msg], record_path="price_changes", meta=["market", "timestamp"]
                )
                return event_type, preprocess(data, int_datetime_unit="ms")

            elif event_type in ("last_trade_price", "best_bid_ask", "tick_size_change"):
                return event_type, preprocess(pd.DataFrame([msg]), int_datetime_unit="ms")

            elif event_type in ("new_market", "market_resolved"):
                return event_type, preprocess_dict(msg, int_datetime_unit="ms")

            return event_type, msg

        def _parse(raw):
            data = orjson.loads(raw)
            if isinstance(data, list):
                return [_parse_single(item) for item in data]
            return _parse_single(data)

        return AsyncPolymarketWebSocketSession(
            _url=_MARKET_URL,
            _on_open_msg=sub,
            _parse_fn=_parse,
            _ping_interval=ping_interval,
            _reconnect=reconnect,
        )

    def user_channel(
        self,
        markets: list[str],
        *,
        ping_interval: int = 10,
        reconnect: bool = True,
    ) -> AsyncPolymarketWebSocketSession:
        """Create an authenticated user WebSocket session.

        Requires L2 API credentials. Yields ``(event_type, payload)`` tuples
        where event_type is ``"trade"`` or ``"order"``.

        Trade events yield ``("trade", DataFrame[ClobTradeSchema])``.
        Order events yield ``("order", DataFrame[ActiveOrderSchema])``.

        Args:
            markets: Condition IDs to monitor.
        """
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            raise ValueError("user_channel requires api_key, api_secret, api_passphrase")

        # Build L2 auth subscription message
        ts = str(int(time.time()))
        sig = hmac.new(
            base64.urlsafe_b64decode(self.api_secret),
            (ts + "GET" + "/ws/user").encode(),
            hashlib.sha256,
        ).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).decode()

        sub = orjson.dumps(
            {
                "auth": {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "passphrase": self.api_passphrase,
                },
                "markets": markets,
                "type": "user",
                "POLY_API_KEY": self.api_key,
                "POLY_PASSPHRASE": self.api_passphrase,
                "POLY_SIGNATURE": sig_b64,
                "POLY_TIMESTAMP": ts,
            }
        )

        preprocess = self._preprocess

        def _parse_single(msg):
            event_type = msg.get("event_type", "")
            if event_type in ("trade", "order"):
                return event_type, preprocess(pd.DataFrame([msg]))
            return event_type, msg

        def _parse(raw):
            data = orjson.loads(raw)
            if isinstance(data, list):
                return [_parse_single(item) for item in data]
            return _parse_single(data)

        return AsyncPolymarketWebSocketSession(
            _url=_USER_URL,
            _on_open_msg=sub,
            _parse_fn=_parse,
            _ping_interval=ping_interval,
            _reconnect=reconnect,
        )

    def sports_channel(
        self,
        *,
        ping_interval: int = 10,
        reconnect: bool = True,
    ) -> AsyncPolymarketWebSocketSession:
        """Create a sports resolution WebSocket session.

        Yields ``(event_type, payload)`` tuples for live sports resolution events.
        """
        preprocess = self._preprocess

        def _parse_single(msg):
            event_type = msg.get("event_type", "")
            if event_type == "sport_result":
                return event_type, preprocess(pd.DataFrame([msg]))
            return event_type, msg

        def _parse(raw):
            data = orjson.loads(raw)
            if isinstance(data, list):
                return [_parse_single(item) for item in data]
            return _parse_single(data)

        return AsyncPolymarketWebSocketSession(
            _url=_SPORTS_URL,
            _on_open_msg=None,
            _parse_fn=_parse,
            _ping_interval=ping_interval,
            _ping_msg=orjson.dumps({"type": "ping"}).decode(),
            _reconnect=reconnect,
        )

    def rtds_channel(
        self,
        subscriptions: list[dict],
        *,
        ping_interval: int = 5,
        reconnect: bool = True,
    ) -> AsyncPolymarketWebSocketSession:
        """Create a Real-Time Data Streams WebSocket session.

        Yields ``(event_type, payload)`` tuples for crypto prices,
        Chainlink prices, and market comments.

        Args:
            subscriptions: List of subscription dicts, e.g.
                ``[{"type": "crypto_prices", "condition_id": "0x..."}]``.
        """
        sub = orjson.dumps(subscriptions)
        preprocess = self._preprocess

        def _parse_single(msg):
            event_type = msg.get("type", msg.get("event_type", ""))
            if event_type in ("crypto_prices", "crypto_prices_chainlink", "comment"):
                return event_type, preprocess(pd.DataFrame([msg]), int_datetime_unit="ms")
            return event_type, msg

        def _parse(raw):
            data = orjson.loads(raw)
            if isinstance(data, list):
                return [_parse_single(item) for item in data]
            return _parse_single(data)

        return AsyncPolymarketWebSocketSession(
            _url=_RTDS_URL,
            _on_open_msg=sub,
            _parse_fn=_parse,
            _ping_interval=ping_interval,
            _reconnect=reconnect,
        )
