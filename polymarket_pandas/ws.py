from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import orjson
import pandas as pd
from websocket import WebSocketApp

from polymarket_pandas.utils import (
    DEFAULT_BOOL_COLUMNS,
    DEFAULT_DICT_COLUMNS,
    DEFAULT_DROP_COLUMNS,
    DEFAULT_INT_DATETIME_COLUMNS,
    DEFAULT_JSON_COLUMNS,
    DEFAULT_NUMERIC_COLUMNS,
    DEFAULT_STR_DATETIME_COLUMNS,
    expand_column_lists,
    orderbook_meta,
)
from polymarket_pandas.utils import (
    preprocess_dataframe as _preprocess_dataframe,
)

_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
_SPORTS_URL = "wss://sports-api.polymarket.com/ws"
_RTDS_URL = "wss://ws-live-data.polymarket.com"


@dataclass
class PolymarketWebSocketSession:
    """Thin wrapper around a WebSocketApp returned by each channel method.

    Provides subscribe/unsubscribe helpers for dynamic asset management.
    See: https://docs.polymarket.com/api-reference/wss
    """

    app: WebSocketApp

    def run_forever(self, **kwargs) -> None:
        """Start the WebSocket event loop, blocking until the connection closes."""
        self.app.run_forever(**kwargs)

    def close(self) -> None:
        """Close the WebSocket connection."""
        self.app.close()

    def subscribe(
        self,
        asset_ids: list[str],
        *,
        level: int | None = None,
        custom_feature_enabled: bool | None = None,
    ) -> None:
        """Subscribe to additional asset IDs on an open connection.

        Args:
            asset_ids: CLOB token IDs to subscribe to.
            level: Order book depth level (1 or 2).
            custom_feature_enabled: Enable extended event types.
        """
        msg: dict = {"operation": "subscribe", "assets_ids": asset_ids}
        if level is not None:
            msg["level"] = level
        if custom_feature_enabled is not None:
            msg["custom_feature_enabled"] = custom_feature_enabled
        self.app.send(orjson.dumps(msg))

    def unsubscribe(
        self,
        asset_ids: list[str],
        *,
        level: int | None = None,
        custom_feature_enabled: bool | None = None,
    ) -> None:
        """Unsubscribe from asset IDs on an open connection.

        Args:
            asset_ids: CLOB token IDs to unsubscribe from.
            level: Order book depth level (1 or 2).
            custom_feature_enabled: Enable extended event types.
        """
        msg: dict = {"operation": "unsubscribe", "assets_ids": asset_ids}
        if level is not None:
            msg["level"] = level
        if custom_feature_enabled is not None:
            msg["custom_feature_enabled"] = custom_feature_enabled
        self.app.send(orjson.dumps(msg))

    def rtds_subscribe(self, subscriptions: list[dict]) -> None:
        """Subscribe to RTDS topics on an open connection.

        Args:
            subscriptions: List of subscription dicts, e.g. ``[{"topic": "crypto_prices"}]``.
        """
        msg = orjson.dumps({"action": "subscribe", "subscriptions": subscriptions})
        self.app.send(msg)

    def rtds_unsubscribe(self, subscriptions: list[dict]) -> None:
        """Unsubscribe from RTDS topics on an open connection.

        Args:
            subscriptions: List of subscription dicts to remove.
        """
        msg = orjson.dumps({"action": "unsubscribe", "subscriptions": subscriptions})
        self.app.send(msg)


@dataclass
class PolymarketWebSocket:
    """WebSocket client for Polymarket real-time data streams.

    Provides channel methods that return a ``PolymarketWebSocketSession``.
    Incoming messages are parsed into DataFrames using the same preprocessing
    pipeline as ``PolymarketPandas``. Use ``from_client()`` to share credentials
    and column config with an existing HTTP client.

    See: https://docs.polymarket.com/api-reference/wss
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
    bool_columns: tuple = field(default=DEFAULT_BOOL_COLUMNS)
    drop_columns: tuple = field(default=DEFAULT_DROP_COLUMNS)
    json_columns: tuple = field(default=DEFAULT_JSON_COLUMNS)
    dict_columns: tuple = field(default=DEFAULT_DICT_COLUMNS)

    def __post_init__(self) -> None:
        self._numeric_columns = expand_column_lists(self.numeric_columns)
        self._str_datetime_columns = expand_column_lists(self.str_datetime_columns)
        self._int_datetime_columns = expand_column_lists(self.int_datetime_columns)
        self._bool_columns = expand_column_lists(self.bool_columns)
        self._drop_columns = expand_column_lists(self.drop_columns)
        self._json_columns = expand_column_lists(self.json_columns)
        self._dict_columns = expand_column_lists(self.dict_columns)

    @classmethod
    def from_client(cls, client) -> PolymarketWebSocket:
        """Share credentials and column config with an existing PolymarketPandas HTTP client."""
        return cls(
            api_key=client._api_key,
            api_secret=client._api_secret,
            api_passphrase=client._api_passphrase,
            numeric_columns=client.numeric_columns,
            str_datetime_columns=client.str_datetime_columns,
            int_datetime_columns=client.int_datetime_columns,
            bool_columns=client.bool_columns,
            drop_columns=client.drop_columns,
            json_columns=client.json_columns,
            dict_columns=client.dict_columns,
        )

    # ── Private helpers ─────────────────────────────────────────────────

    def _preprocess(self, df: pd.DataFrame, *, int_datetime_unit: str = "s") -> pd.DataFrame:
        return _preprocess_dataframe(
            df,
            numeric_columns=self._numeric_columns,
            str_datetime_columns=self._str_datetime_columns,
            int_datetime_columns=self._int_datetime_columns,
            bool_columns=self._bool_columns,
            drop_columns=self._drop_columns,
            json_columns=self._json_columns,
            dict_columns=self._dict_columns,
            int_datetime_unit=int_datetime_unit,
        )

    def _dispatch(self, named_cb, fallback_cb, event_type: str, payload) -> None:
        if named_cb is not None:
            named_cb(payload)
        elif fallback_cb is not None:
            fallback_cb(event_type, payload)

    def _ping_thread(self, ws: WebSocketApp, interval: int, msg: str = "PING") -> None:
        def _loop():
            while True:
                time.sleep(interval)
                try:
                    ws.send(msg)
                except Exception:
                    break

        threading.Thread(target=_loop, daemon=True).start()

    # ── Channel methods ─────────────────────────────────────────────────

    def market_channel(
        self,
        asset_ids: list[str],
        *,
        on_book: Callable[[pd.DataFrame], None] | None = None,
        on_price_change: Callable[[pd.DataFrame], None] | None = None,
        on_last_trade_price: Callable[[pd.DataFrame], None] | None = None,
        on_best_bid_ask: Callable[[pd.DataFrame], None] | None = None,
        on_tick_size_change: Callable[[pd.DataFrame], None] | None = None,
        on_new_market: Callable[[dict], None] | None = None,
        on_market_resolved: Callable[[dict], None] | None = None,
        on_message: Callable[[str, pd.DataFrame | dict], None] | None = None,
        on_error: Callable | None = None,
        on_close: Callable | None = None,
        initial_dump: bool = True,
        level: int = 2,
        custom_feature_enabled: bool = True,
        ping_interval: int = 10,
    ) -> PolymarketWebSocketSession:
        """Open a market data WebSocket for the given asset IDs.

        Streams order-book snapshots, price changes, last trade prices,
        best bid/ask updates, tick-size changes, and market lifecycle events.
        Each named callback receives a preprocessed DataFrame (or dict for
        ``on_new_market`` / ``on_market_resolved``). Unhandled event types
        fall through to ``on_message``.

        Args:
            asset_ids: CLOB token IDs to subscribe to.
            level: Order-book depth level (1 or 2).
            initial_dump: Request an initial snapshot on connect.

        Returns:
            A session whose ``run_forever()`` starts the event loop.

        See: https://docs.polymarket.com/api-reference/wss/market
        """

        def _on_open(ws):
            sub = {
                "assets_ids": asset_ids,
                "type": "market",
                "initial_dump": initial_dump,
                "level": level,
                "custom_feature_enabled": custom_feature_enabled,
            }
            ws.send(orjson.dumps(sub))
            self._ping_thread(ws, ping_interval)

        def _on_message(ws, raw: str):
            if raw == "PONG":
                return
            msg = orjson.loads(raw)
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
                df = self._preprocess(pd.concat([bids, asks], ignore_index=True))
                self._dispatch(on_book, on_message, event_type, df)

            elif event_type == "price_change":
                data = pd.json_normalize(
                    [msg], record_path="price_changes", meta=["market", "timestamp"]
                )
                df = self._preprocess(data)
                self._dispatch(on_price_change, on_message, event_type, df)

            elif event_type == "last_trade_price":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_last_trade_price, on_message, event_type, df)

            elif event_type == "best_bid_ask":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_best_bid_ask, on_message, event_type, df)

            elif event_type == "tick_size_change":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_tick_size_change, on_message, event_type, df)

            elif event_type == "new_market":
                self._dispatch(on_new_market, on_message, event_type, msg)

            elif event_type == "market_resolved":
                self._dispatch(on_market_resolved, on_message, event_type, msg)

            elif on_message is not None:
                on_message(event_type, msg)

        app = WebSocketApp(
            _MARKET_URL,
            on_open=_on_open,
            on_message=_on_message,
            on_error=on_error,
            on_close=on_close,
        )
        return PolymarketWebSocketSession(app=app)

    def user_channel(
        self,
        markets: list[str],
        *,
        on_trade: Callable[[pd.DataFrame], None] | None = None,
        on_order: Callable[[pd.DataFrame], None] | None = None,
        on_message: Callable[[str, pd.DataFrame], None] | None = None,
        on_error: Callable | None = None,
        on_close: Callable | None = None,
        ping_interval: int = 10,
    ) -> PolymarketWebSocketSession:
        """Open an authenticated user WebSocket for trade and order updates.

        Requires L2 API credentials (api_key, api_secret, api_passphrase).

        Args:
            markets: Condition IDs to monitor for the authenticated user.

        Returns:
            A session whose ``run_forever()`` starts the event loop.

        See: https://docs.polymarket.com/api-reference/wss/user
        """
        if self.api_key is None or self.api_secret is None or self.api_passphrase is None:
            raise ValueError(
                "api_key, api_secret, and api_passphrase are required for the user channel."
            )

        def _on_open(ws):
            sub = {
                "auth": {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "passphrase": self.api_passphrase,
                },
                "markets": markets,
                "type": "user",
            }
            ws.send(orjson.dumps(sub))
            self._ping_thread(ws, ping_interval)

        def _on_message(ws, raw: str):
            if raw == "PONG":
                return
            msg = orjson.loads(raw)
            event_type = msg.get("event_type", "")

            if event_type == "trade":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_trade, on_message, event_type, df)

            elif event_type == "order":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_order, on_message, event_type, df)

            elif on_message is not None:
                on_message(event_type, msg)

        app = WebSocketApp(
            _USER_URL,
            on_open=_on_open,
            on_message=_on_message,
            on_error=on_error,
            on_close=on_close,
        )
        return PolymarketWebSocketSession(app=app)

    def sports_channel(
        self,
        *,
        on_sport_result: Callable[[pd.DataFrame], None] | None = None,
        on_message: Callable[[str, pd.DataFrame], None] | None = None,
        on_error: Callable | None = None,
        on_close: Callable | None = None,
    ) -> PolymarketWebSocketSession:
        """Open a WebSocket for real-time sports result events.

        Returns:
            A session whose ``run_forever()`` starts the event loop.

        See: https://docs.polymarket.com/api-reference/wss
        """

        def _on_message(ws, raw: str):
            if raw == "ping":
                ws.send("pong")
                return
            msg = orjson.loads(raw)
            event_type = msg.get("event_type", "")

            if event_type == "sport_result":
                df = self._preprocess(pd.DataFrame([msg]))
                self._dispatch(on_sport_result, on_message, event_type, df)
            elif on_message is not None:
                on_message(event_type, msg)

        app = WebSocketApp(
            _SPORTS_URL,
            on_message=_on_message,
            on_error=on_error,
            on_close=on_close,
        )
        return PolymarketWebSocketSession(app=app)

    def rtds_channel(
        self,
        subscriptions: list[dict],
        *,
        on_crypto_prices: Callable[[pd.DataFrame], None] | None = None,
        on_crypto_prices_chainlink: Callable[[pd.DataFrame], None] | None = None,
        on_comment: Callable[[dict], None] | None = None,
        on_message: Callable[[str, pd.DataFrame | dict], None] | None = None,
        on_error: Callable | None = None,
        on_close: Callable | None = None,
        ping_interval: int = 5,
    ) -> PolymarketWebSocketSession:
        """Open an RTDS WebSocket for crypto prices, Chainlink feeds, and comments.

        Args:
            subscriptions: List of topic dicts, e.g.
                ``[{"topic": "crypto_prices"}, {"topic": "comments"}]``.

        Returns:
            A session whose ``run_forever()`` starts the event loop.

        See: https://docs.polymarket.com/api-reference/wss
        """

        def _on_open(ws):
            sub = {"action": "subscribe", "subscriptions": subscriptions}
            sub = orjson.dumps(sub)
            ws.send(sub)
            self._ping_thread(ws, ping_interval)

        def _on_message(ws, raw: str):
            if raw == "PONG":
                return
            msg = orjson.loads(raw)
            topic = msg.get("topic", "")
            payload = msg.get("payload", msg)
            if topic == "crypto_prices":
                payload["source"] = "binance"
                df = self._preprocess(pd.DataFrame([payload]), int_datetime_unit="ms")
                self._dispatch(on_crypto_prices, on_message, topic, df)
            elif topic == "crypto_prices_chainlink":
                payload["source"] = "chainlink"
                df = self._preprocess(pd.DataFrame([payload]), int_datetime_unit="ms")
                self._dispatch(on_crypto_prices_chainlink, on_message, topic, df)
            elif topic == "comments":
                self._dispatch(on_comment, on_message, topic, payload)
            elif on_message is not None:
                on_message(topic, msg)

        app = WebSocketApp(
            _RTDS_URL,
            on_open=_on_open,
            on_message=_on_message,
            on_error=on_error,
            on_close=on_close,
        )
        return PolymarketWebSocketSession(app=app)
