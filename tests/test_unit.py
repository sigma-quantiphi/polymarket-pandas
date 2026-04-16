"""Unit tests — no live API calls, all HTTP interactions mocked via pytest-httpx."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import orjson
import pandas as pd
import pytest
from pytest_httpx import HTTPXMock

from polymarket_pandas import (
    PlaceOrderSchema,
    PolymarketAPIError,
    PolymarketAuthError,
    PolymarketPandas,
    PolymarketRateLimitError,
    PolymarketWebSocket,
    SubmitOrderSchema,
    XTrackerDailyStatSchema,
    XTrackerMetricSchema,
    XTrackerPostSchema,
    XTrackerTrackingSchema,
    XTrackerUserSchema,
)
from polymarket_pandas.client import (
    _decimal_places,
    _round_down,
    _round_normal,
    _round_up,
    _to_token_decimals,
)
from polymarket_pandas.utils import (
    expand_column_lists,
    filter_params,
    snake_to_camel,
)

FIXTURES = Path(__file__).parent / "fixtures"

# ── Utility: snake_to_camel ──────────────────────────────────────────────────


def test_snake_to_camel_basic():
    assert snake_to_camel("end_date") == "endDate"


def test_snake_to_camel_already_camel():
    assert snake_to_camel("endDate") == "endDate"


def test_snake_to_camel_multiple_segments():
    assert snake_to_camel("events_end_date") == "eventsEndDate"


def test_snake_to_camel_no_underscore():
    assert snake_to_camel("volume") == "volume"


# ── Utility: filter_params ───────────────────────────────────────────────────


def test_filter_params_none_returns_empty_dict():
    assert filter_params(None) == {}


def test_filter_params_removes_none_values():
    assert filter_params({"a": 1, "b": None}) == {"a": 1}


def test_filter_params_removes_empty_lists():
    assert filter_params({"a": [], "b": [1]}) == {"b": [1]}


def test_filter_params_keeps_nonempty_lists():
    result = filter_params({"ids": ["x", "y"]})
    assert result == {"ids": ["x", "y"]}


def test_filter_params_converts_timestamp():
    ts = pd.Timestamp("2025-01-15T12:00:00", tz="UTC")
    result = filter_params({"startTs": ts})
    assert result["startTs"] == int(ts.timestamp())


def test_filter_params_converts_any_timestamp_key():
    ts = pd.Timestamp("2025-06-01T08:00:00", tz="UTC")
    result = filter_params({"before": ts, "after": ts})
    assert result["before"] == int(ts.timestamp())
    assert result["after"] == int(ts.timestamp())


def test_filter_params_converts_naive_timestamp():
    ts = pd.Timestamp("2025-03-01T12:00:00")
    result = filter_params({"start": ts})
    assert result["start"] == int(ts.timestamp())


def test_filter_params_all_none_returns_empty():
    assert filter_params({"a": None, "b": None}) == {}


# ── Utility: expand_column_lists ─────────────────────────────────────────────


def test_expand_column_lists_includes_base():
    result = expand_column_lists(("price",), prefixes=("events",))
    assert "price" in result


def test_expand_column_lists_generates_prefixed_camel():
    result = expand_column_lists(("end_date",), prefixes=("events",))
    assert "eventsEndDate" in result


def test_expand_column_lists_default_prefixes():
    result = expand_column_lists(("price",))
    assert "eventsPrice" in result
    assert "marketsPrice" in result
    assert "eventsTagsPrice" in result
    assert "eventsSeriesPrice" in result
    # removed "series" prefix — should not appear
    assert "seriesPrice" not in result


# ── Utility: preprocess_dataframe ────────────────────────────────────────────


def test_preprocess_dataframe_numeric_coercion(client: PolymarketPandas):
    df = pd.DataFrame([{"price": "0.75", "size": "100"}])
    result = client.preprocess_dataframe(df)
    assert pd.api.types.is_numeric_dtype(result["price"])
    assert pd.api.types.is_numeric_dtype(result["size"])


def test_preprocess_dataframe_datetime_str_coercion(client: PolymarketPandas):
    df = pd.DataFrame([{"endDate": "2025-06-01T00:00:00Z"}])
    result = client.preprocess_dataframe(df)
    assert pd.api.types.is_datetime64_any_dtype(result["endDate"])


def test_preprocess_dataframe_bool_coercion(client: PolymarketPandas):
    df = pd.DataFrame([{"active": "True"}])
    result = client.preprocess_dataframe(df)
    assert result["active"].dtype == pd.BooleanDtype()


def test_preprocess_dataframe_drops_icon_image(client: PolymarketPandas):
    df = pd.DataFrame([{"slug": "x", "icon": "url", "image": "url2"}])
    result = client.preprocess_dataframe(df)
    assert "icon" not in result.columns
    assert "image" not in result.columns


def test_preprocess_dataframe_snake_renamed_to_camel(client: PolymarketPandas):
    df = pd.DataFrame([{"end_date": "2025-01-01"}])
    result = client.preprocess_dataframe(df)
    assert "endDate" in result.columns
    assert "end_date" not in result.columns


# ── HTTP error mapping ───────────────────────────────────────────────────────


def test_401_raises_auth_error(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        status_code=401,
        json={"error": "unauthorized"},
    )
    with pytest.raises(PolymarketAuthError) as exc_info:
        client.get_server_time()
    assert exc_info.value.status_code == 401


def test_403_raises_auth_error(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        status_code=403,
        json={"error": "forbidden"},
    )
    with pytest.raises(PolymarketAuthError) as exc_info:
        client.get_server_time()
    assert exc_info.value.status_code == 403


def test_429_raises_rate_limit_error(client: PolymarketPandas, httpx_mock: HTTPXMock):
    # Client retries 429 with exponential backoff; disable here so the test
    # verifies exception mapping without burning attempts.
    client.max_retries = 0
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        status_code=429,
        json={"error": "rate limited"},
    )
    with pytest.raises(PolymarketRateLimitError) as exc_info:
        client.get_server_time()
    assert exc_info.value.status_code == 429


def test_500_raises_api_error(client: PolymarketPandas, httpx_mock: HTTPXMock):
    # Disable retries — 5xx is retried by default, but here we verify the
    # exception mapping, not retry behavior.
    client.max_retries = 0
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        status_code=500,
        json={"error": "internal server error"},
    )
    with pytest.raises(PolymarketAPIError) as exc_info:
        client.get_server_time()
    assert exc_info.value.status_code == 500


def test_api_error_is_base_for_auth_error():
    err = PolymarketAuthError(401, "http://x", "bad")
    assert isinstance(err, PolymarketAPIError)


def test_api_error_is_base_for_rate_limit_error():
    err = PolymarketRateLimitError(429, "http://x", "slow down")
    assert isinstance(err, PolymarketAPIError)


# ── Auth guards ──────────────────────────────────────────────────────────────


def test_private_endpoint_without_creds_raises_auth_error(client: PolymarketPandas):
    with pytest.raises(PolymarketAuthError):
        client.get_active_orders()


def test_private_endpoint_with_creds_calls_api(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/data/orders",
        json={"data": [], "next_cursor": "LTE=", "count": 0, "limit": 100},
    )
    result = authed_client.get_active_orders()
    assert isinstance(result, dict)
    assert isinstance(result["data"], pd.DataFrame)


# ── Context manager ──────────────────────────────────────────────────────────


def test_context_manager_closes_client():
    with PolymarketPandas(use_tqdm=False) as c:
        assert not c._client.is_closed
    assert c._client.is_closed


# ── Public endpoint happy paths ──────────────────────────────────────────────


def test_get_server_time(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        json={"time": "1700000000"},
    )
    result = client.get_server_time()
    assert result == {"time": "1700000000"}


def test_get_orderbook_returns_dataframe(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/book?token_id=abc123",
        json={
            "market": "0xabc",
            "asset_id": "abc123",
            "timestamp": "1700000000",
            "hash": "0x1",
            "min_order_size": "1",
            "tick_size": "0.01",
            "neg_risk": False,
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "200"}],
        },
    )
    df = client.get_orderbook("abc123")
    assert isinstance(df, pd.DataFrame)
    assert set(df["side"].unique()) == {"bids", "asks"}
    assert df["price"].dtype == float


def test_get_markets_returns_dataframe(client: PolymarketPandas, httpx_mock: HTTPXMock):
    # expand_* are Python-side flags — not passed as query params
    httpx_mock.add_response(
        url="https://gamma-api.polymarket.com/markets?limit=300",
        json=[
            {
                "id": 1,
                "slug": "test-market",
                "clobTokenIds": '["tok1"]',
                "active": True,
                "closed": False,
                "volume24hr": "5000",
            }
        ],
    )
    df = client.get_markets(expand_events=False, expand_series=False)
    assert isinstance(df, pd.DataFrame)
    assert "slug" in df.columns


def test_get_markets_keyset_returns_page(client: PolymarketPandas, httpx_mock: HTTPXMock):
    import re

    httpx_mock.add_response(
        url=re.compile(r"https://gamma-api\.polymarket\.com/markets/keyset\?.*"),
        json={
            "markets": [
                {
                    "id": 1,
                    "slug": "kset-market",
                    "clobTokenIds": '["tok1"]',
                    "active": True,
                    "closed": False,
                    "volume24hr": "100",
                }
            ],
            "next_cursor": "CURSOR_X",
        },
    )
    page = client.get_markets_keyset(expand_events=False, expand_series=False, limit=5)
    assert isinstance(page, dict)
    assert isinstance(page["data"], pd.DataFrame)
    assert page["data"]["slug"].iloc[0] == "kset-market"
    assert page["next_cursor"] == "CURSOR_X"


def test_get_markets_keyset_all_follows_cursor(client: PolymarketPandas, httpx_mock: HTTPXMock):
    import re

    # page 1: has next_cursor
    httpx_mock.add_response(
        url=re.compile(r"https://gamma-api\.polymarket\.com/markets/keyset\?.*"),
        json={
            "markets": [
                {"id": 1, "slug": "a", "clobTokenIds": '["t1"]', "closed": False},
            ],
            "next_cursor": "PAGE2",
        },
    )
    # page 2: no next_cursor — stops
    httpx_mock.add_response(
        url=re.compile(
            r"https://gamma-api\.polymarket\.com/markets/keyset\?.*after_cursor=PAGE2.*"
        ),
        json={
            "markets": [
                {"id": 2, "slug": "b", "clobTokenIds": '["t2"]', "closed": False},
            ],
        },
    )
    df = client.get_markets_keyset_all(expand_events=False, expand_series=False, limit=5)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert set(df["slug"]) == {"a", "b"}


def test_fetch_sports_event_filters_by_condition_id(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """fetch_sports_event uses conditionId from the markets query to slice
    the parent event response, dropping markets of other types."""
    import re

    cond_a = "0xaaa"
    cond_b = "0xbbb"
    cond_other = "0xccc"

    httpx_mock.add_response(
        url=re.compile(r"https://gamma-api\.polymarket\.com/markets\?.*"),
        json=[
            {
                "id": 1,
                "conditionId": cond_a,
                "question": "Spread: A (-1.5)",
                "groupItemTitle": "Spread -1.5",
                "events": [{"id": 99, "slug": "game-event"}],
            },
            {
                "id": 2,
                "conditionId": cond_b,
                "question": "Spread: B (+1.5)",
                "groupItemTitle": "Spread +1.5",
                "events": [{"id": 99, "slug": "game-event"}],
            },
        ],
    )
    httpx_mock.add_response(
        url=re.compile(r"https://gamma-api\.polymarket\.com/events\?.*"),
        json=[
            {
                "id": 99,
                "slug": "game-event",
                "title": "Game Event",
                "markets": [
                    {"conditionId": cond_a, "question": "Spread A"},
                    {"conditionId": cond_b, "question": "Spread B"},
                    {"conditionId": cond_other, "question": "Moneyline"},
                ],
            }
        ],
    )

    result = client.fetch_sports_event("spreads")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert set(result["marketsConditionId"]) == {cond_a, cond_b}


def test_fetch_sports_event_empty_markets(client: PolymarketPandas, httpx_mock: HTTPXMock):
    """If the discovery query returns nothing, return an empty DataFrame."""
    import re

    httpx_mock.add_response(
        url=re.compile(r"https://gamma-api\.polymarket\.com/markets\?.*"),
        json=[],
    )
    result = client.fetch_sports_event("totals")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_get_tags_returns_dataframe(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://gamma-api.polymarket.com/tags?limit=300",
        json=[{"id": 1, "label": "crypto"}, {"id": 2, "label": "sports"}],
    )
    df = client.get_tags()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


def test_get_midpoint_price(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/midpoint?token_id=tok1",
        json={"mid": "0.62"},
    )
    result = client.get_midpoint_price("tok1")
    assert result == pytest.approx(0.62)
    assert isinstance(result, float)


def test_get_sampling_markets_returns_dict(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/sampling-markets",
        json={
            "limit": 500,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [{"condition_id": "0xabc", "active": True}],
        },
    )
    result = client.get_sampling_markets()
    assert isinstance(result["data"], pd.DataFrame)
    assert result["next_cursor"] == "LTE="


# ── WebSocket: from_client ──────────────────────────────────────────────────


def test_websocket_from_client():
    client = PolymarketPandas(
        use_tqdm=False,
        _api_key="key1",
        _api_secret="secret1",
        _api_passphrase="pass1",
    )
    ws = PolymarketWebSocket.from_client(client)
    assert ws.api_key == "key1"
    assert ws.api_secret == "secret1"
    assert ws.api_passphrase == "pass1"
    assert ws.numeric_columns == client.numeric_columns
    assert ws.bool_columns == client.bool_columns


def test_websocket_from_client_no_creds():
    client = PolymarketPandas(use_tqdm=False)
    ws = PolymarketWebSocket.from_client(client)
    assert ws.api_key is None
    assert ws.api_secret is None


# ── WebSocket: market_channel dispatch ──────────────────────────────────────


@pytest.fixture
def ws() -> PolymarketWebSocket:
    return PolymarketWebSocket(
        api_key=None,
        api_secret=None,
        api_passphrase=None,
    )


def _get_on_message(session) -> callable:
    """Extract the _on_message callback from the WebSocketApp."""
    return session.app.on_message


def test_market_channel_pong_ignored(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_message=lambda et, data: received.append((et, data)),
    )
    _get_on_message(session)(MagicMock(), "PONG")
    assert received == []


def test_market_channel_book_event(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_book=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "book",
            "market": "0xabc",
            "asset_id": "tok1",
            "timestamp": "1700000000",
            "hash": "0x1",
            "min_order_size": "1",
            "tick_size": "0.01",
            "neg_risk": False,
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "200"}],
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    df = received[0]
    assert isinstance(df, pd.DataFrame)
    assert set(df["side"].unique()) == {"bids", "asks"}
    assert pd.api.types.is_numeric_dtype(df["price"])


def test_market_channel_price_change(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_price_change=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "price_change",
            "market": "0xabc",
            "timestamp": "1700000000",
            "price_changes": [
                {"asset_id": "tok1", "price": "0.60", "size": "50"},
            ],
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert pd.api.types.is_numeric_dtype(received[0]["price"])


def test_market_channel_last_trade_price(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_last_trade_price=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "last_trade_price",
            "asset_id": "tok1",
            "price": "0.48",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1


def test_market_channel_best_bid_ask(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_best_bid_ask=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "best_bid_ask",
            "asset_id": "tok1",
            "best_bid": "0.44",
            "best_ask": "0.56",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1


def test_market_channel_new_market_dispatches_dict(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_new_market=lambda d: received.append(d),
    )
    msg = orjson.dumps(
        {
            "event_type": "new_market",
            "market": "0xnew",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert isinstance(received[0], dict)
    assert received[0]["market"] == "0xnew"


def test_market_channel_fallback_on_message(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_message=lambda et, data: received.append((et, data)),
    )
    msg = orjson.dumps(
        {
            "event_type": "price_change",
            "market": "0xabc",
            "timestamp": "1700000000",
            "price_changes": [
                {"asset_id": "tok1", "price": "0.60"},
            ],
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert received[0][0] == "price_change"
    assert isinstance(received[0][1], pd.DataFrame)


def test_market_channel_unknown_event_to_fallback(ws: PolymarketWebSocket):
    received = []
    session = ws.market_channel(
        asset_ids=["tok1"],
        on_message=lambda et, data: received.append((et, data)),
    )
    msg = orjson.dumps(
        {
            "event_type": "something_new",
            "data": "test",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert received[0][0] == "something_new"


# ── WebSocket: user_channel ─────────────────────────────────────────────────


def test_user_channel_requires_creds():
    ws = PolymarketWebSocket(api_key=None, api_secret=None, api_passphrase=None)
    with pytest.raises(ValueError, match="api_key"):
        ws.user_channel(markets=["0xabc"])


def test_user_channel_trade_event():
    ws = PolymarketWebSocket(api_key="k", api_secret="s", api_passphrase="p")
    received = []
    session = ws.user_channel(
        markets=["0xabc"],
        on_trade=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "trade",
            "asset_id": "tok1",
            "price": "0.55",
            "size": "10",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert isinstance(received[0], pd.DataFrame)


def test_user_channel_order_event():
    ws = PolymarketWebSocket(api_key="k", api_secret="s", api_passphrase="p")
    received = []
    session = ws.user_channel(
        markets=["0xabc"],
        on_order=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "event_type": "order",
            "asset_id": "tok1",
            "price": "0.50",
            "original_size": "25",
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1


# ── WebSocket: sports_channel ───────────────────────────────────────────────


def test_sports_channel_ping_pong(ws: PolymarketWebSocket):
    session = ws.sports_channel()
    mock_ws = MagicMock()
    _get_on_message(session)(mock_ws, "ping")
    mock_ws.send.assert_called_once_with("pong")


# ── WebSocket: rtds_channel ─────────────────────────────────────────────────


def test_rtds_channel_crypto_prices(ws: PolymarketWebSocket):
    received = []
    session = ws.rtds_channel(
        subscriptions=[{"channel": "crypto_prices", "symbols": ["BTC"]}],
        on_crypto_prices=lambda df: received.append(df),
    )
    msg = orjson.dumps(
        {
            "topic": "crypto_prices",
            "payload": {"symbol": "BTC", "price": "83000.50"},
        }
    ).decode()
    _get_on_message(session)(MagicMock(), msg)
    assert len(received) == 1
    assert isinstance(received[0], pd.DataFrame)


def test_rtds_channel_pong_ignored(ws: PolymarketWebSocket):
    received = []
    session = ws.rtds_channel(
        subscriptions=[],
        on_message=lambda t, d: received.append((t, d)),
    )
    _get_on_message(session)(MagicMock(), "PONG")
    assert received == []


# ── CTF Mixin ───────────────────────────────────────────────────────────────

STUB_CONDITION_ID = "0x" + "ab" * 32


@pytest.fixture
def ctf_client() -> PolymarketPandas:
    """Client with a private key for CTF operation tests (no proxy wallet)."""
    from eth_account import Account

    pk = "0x" + "ab" * 32
    return PolymarketPandas(
        use_tqdm=False,
        address=Account.from_key(pk).address,  # match EOA so no proxy
        private_key=pk,
    )


def test_ctf_requires_private_key(client: PolymarketPandas):
    """CTF methods raise PolymarketAuthError when private_key is not set."""
    with pytest.raises(PolymarketAuthError, match="private_key"):
        client.split_position(STUB_CONDITION_ID, 1_000_000)


def test_ctf_requires_web3_import(ctf_client: PolymarketPandas, monkeypatch):
    """CTF methods raise ImportError with install hint when web3 is absent."""
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "web3":
            raise ImportError("No module named 'web3'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    # Clear any cached _w3 from a prior call
    if hasattr(ctf_client, "_w3"):
        delattr(ctf_client, "_w3")

    with pytest.raises(ImportError, match="pip install polymarket-pandas\\[ctf\\]"):
        ctf_client.split_position(STUB_CONDITION_ID, 1_000_000)


def test_to_bytes32_hex_string():
    """_to_bytes32 normalises a hex string to 32 bytes."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    result = CTFMixin._to_bytes32("0x" + "ab" * 32)
    assert result == b"\xab" * 32
    assert len(result) == 32


def test_to_bytes32_no_prefix():
    """_to_bytes32 works without 0x prefix."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    result = CTFMixin._to_bytes32("ab" * 32)
    assert result == b"\xab" * 32


def test_to_bytes32_passthrough_bytes():
    """_to_bytes32 passes bytes through unchanged."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    raw = b"\xcd" * 32
    assert CTFMixin._to_bytes32(raw) is raw


def _mock_web3(ctf_client, monkeypatch):
    """Inject a mock web3 instance and contracts into a CTF client."""
    mock_w3 = MagicMock()
    mock_w3.eth.get_transaction_count.return_value = 0
    mock_w3.eth.gas_price = 30_000_000_000
    mock_w3.eth.estimate_gas.return_value = 200_000
    mock_w3.to_checksum_address = lambda a: a

    mock_receipt = {
        "blockNumber": 12345,
        "status": 1,
        "gasUsed": 150_000,
    }
    mock_w3.eth.wait_for_transaction_receipt.return_value = mock_receipt

    mock_account = MagicMock()
    mock_account.address = "0x" + "ab" * 20
    mock_signed = MagicMock()
    mock_signed.raw_transaction = b"\x00"
    mock_account.sign_transaction.return_value = mock_signed
    mock_w3.eth.account.from_key.return_value = mock_account
    mock_w3.eth.send_raw_transaction.return_value = b"\x01" * 32

    ct = MagicMock()
    nr = MagicMock()
    usdc = MagicMock()

    # Make build_transaction return a plain dict
    for contract in (ct, nr, usdc):
        for fn_name in (
            "splitPosition",
            "mergePositions",
            "redeemPositions",
            "convertPositions",
            "approve",
        ):
            fn = getattr(contract.functions, fn_name, MagicMock())
            fn.return_value.build_transaction.return_value = {"data": "0x"}

    ctf_client._w3 = mock_w3
    ctf_client._ct_contract = ct
    ctf_client._nr_contract = nr
    ctf_client._usdc_contract = usdc
    return ct, nr, usdc


def test_split_position_standard(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.split_position(STUB_CONDITION_ID, 1_000_000)
    ct.functions.splitPosition.assert_called_once()
    nr.functions.splitPosition.assert_not_called()
    assert result["status"] == 1
    assert "txHash" in result


def test_split_position_neg_risk(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.split_position(STUB_CONDITION_ID, 1_000_000, neg_risk=True)
    nr.functions.splitPosition.assert_called_once()
    ct.functions.splitPosition.assert_not_called()
    assert result["status"] == 1


def test_merge_positions_standard(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.merge_positions(STUB_CONDITION_ID, 1_000_000)
    ct.functions.mergePositions.assert_called_once()
    nr.functions.mergePositions.assert_not_called()
    assert result["status"] == 1


def test_merge_positions_neg_risk(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.merge_positions(STUB_CONDITION_ID, 1_000_000, neg_risk=True)
    nr.functions.mergePositions.assert_called_once()
    ct.functions.mergePositions.assert_not_called()
    assert result["status"] == 1


def test_merge_positions_estimate(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    ctf_client._w3.eth.get_balance.return_value = 10**18  # 1 MATIC
    result = ctf_client.merge_positions(STUB_CONDITION_ID, 1_000_000, estimate=True)
    # Should NOT send a transaction
    ctf_client._w3.eth.send_raw_transaction.assert_not_called()
    # Should return GasEstimate fields
    assert result["gas"] == 200_000
    assert result["gasPrice"] == 30_000_000_000
    assert result["costWei"] == 200_000 * 30_000_000_000
    assert result["eoaBalance"] == 10**18
    assert isinstance(result["costMatic"], float)


def test_split_position_estimate(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    ctf_client._w3.eth.get_balance.return_value = 10**18
    result = ctf_client.split_position(STUB_CONDITION_ID, 1_000_000, estimate=True)
    ctf_client._w3.eth.send_raw_transaction.assert_not_called()
    assert result["gas"] == 200_000
    assert isinstance(result["costMatic"], float)


def test_merge_positions_relayed(monkeypatch):
    """When address differs from EOA, merge routes through the relayer."""
    pk = "0x" + "ab" * 32
    proxy = "0xDEADBEEFdeadbeefDEADBEEFdeadbeef00000000"
    client = PolymarketPandas(
        use_tqdm=False,
        address=proxy,
        private_key=pk,
        _builder_api_key="test-key",
        _builder_api_secret="dGVzdC1zZWNyZXQ=",  # base64("test-secret")
        _builder_api_passphrase="test-pass",
    )
    ct, nr, _ = _mock_web3(client, monkeypatch)

    # build_transaction must return real hex data for proxy encoding
    ct.functions.mergePositions.return_value.build_transaction.return_value = {
        "data": "0x" + "ab" * 32,
    }

    # Mock _encode_proxy_calls to return valid hex
    monkeypatch.setattr(client, "_encode_proxy_calls", lambda calls: "0x" + "cd" * 64)
    # Mock relayer methods
    monkeypatch.setattr(
        client,
        "get_relay_payload",
        lambda **kw: {"address": "0x" + "ee" * 20, "nonce": "42"},
    )
    mock_submit = MagicMock(return_value={"transactionID": "abc", "transactionHash": "0x123"})
    monkeypatch.setattr(client, "submit_transaction", mock_submit)

    result = client.merge_positions(STUB_CONDITION_ID, 1_000_000)

    # Should NOT send direct tx
    client._w3.eth.send_raw_transaction.assert_not_called()
    # Should call submit_transaction with correct args
    mock_submit.assert_called_once()
    call_kwargs = mock_submit.call_args[1]
    assert call_kwargs["proxy_wallet"] == proxy
    assert call_kwargs["type"] == "PROXY"
    assert call_kwargs["to"] == "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
    assert result["transactionHash"] == "0x123"


def test_redeem_positions(ctf_client: PolymarketPandas, monkeypatch):
    ct, _, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.redeem_positions(STUB_CONDITION_ID)
    ct.functions.redeemPositions.assert_called_once()
    assert result["status"] == 1


def test_redeem_positions_neg_risk(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.redeem_positions(STUB_CONDITION_ID, neg_risk=True, amounts=[1_000_000, 0])
    nr.functions.redeemPositions.assert_called_once()
    ct.functions.redeemPositions.assert_not_called()
    assert result["status"] == 1


def test_redeem_positions_neg_risk_missing_amounts(ctf_client: PolymarketPandas, monkeypatch):
    _mock_web3(ctf_client, monkeypatch)
    with pytest.raises(ValueError, match="amounts="):
        ctf_client.redeem_positions(STUB_CONDITION_ID, neg_risk=True)


def test_approve_collateral_max(ctf_client: PolymarketPandas, monkeypatch):
    _, _, usdc = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.approve_collateral()
    usdc.functions.approve.assert_called_once()
    args = usdc.functions.approve.call_args[0]
    assert args[1] == 2**256 - 1
    assert result["status"] == 1


def test_approve_collateral_specific(ctf_client: PolymarketPandas, monkeypatch):
    _, _, usdc = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.approve_collateral(amount=5_000_000)
    args = usdc.functions.approve.call_args[0]
    assert args[1] == 5_000_000
    assert result["status"] == 1


def test_send_ctf_tx_no_wait(ctf_client: PolymarketPandas, monkeypatch):
    _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.split_position(STUB_CONDITION_ID, 1_000_000, wait=False)
    assert "txHash" in result
    assert "blockNumber" not in result


# ── convert_positions ─────────────────────────────────────────────────────


def test_convert_positions(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.convert_positions(STUB_CONDITION_ID, index_set=31, amount=1_000_000)
    nr.functions.convertPositions.assert_called_once()
    assert result["status"] == 1
    assert "txHash" in result


def test_convert_positions_amount_usdc(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    result = ctf_client.convert_positions(STUB_CONDITION_ID, index_set=7, amount_usdc=5.0)
    nr.functions.convertPositions.assert_called_once()
    assert result["status"] == 1


def test_convert_positions_estimate(ctf_client: PolymarketPandas, monkeypatch):
    ct, nr, _ = _mock_web3(ctf_client, monkeypatch)
    ctf_client._w3.eth.get_balance.return_value = 10**18
    result = ctf_client.convert_positions(
        STUB_CONDITION_ID, index_set=31, amount=1_000_000, estimate=True
    )
    ctf_client._w3.eth.send_raw_transaction.assert_not_called()
    assert result["gas"] == 200_000
    assert isinstance(result["costMatic"], float)


# ── batch_ctf_ops ────────────────────────────────────────────────────────


def _proxy_ctf_client(monkeypatch):
    """Build a proxy-wallet CTF client with mocked web3 + relayer."""
    pk = "0x" + "ab" * 32
    proxy = "0xDEADBEEFdeadbeefDEADBEEFdeadbeef00000000"
    c = PolymarketPandas(
        use_tqdm=False,
        address=proxy,
        private_key=pk,
        _builder_api_key="test-key",
        _builder_api_secret="dGVzdC1zZWNyZXQ=",
        _builder_api_passphrase="test-pass",
    )
    _mock_web3(c, monkeypatch)
    # Proxy call tx data must be real hex
    for contract_attr in ("_ct_contract", "_nr_contract"):
        contract = getattr(c, contract_attr)
        for fn_name in ("splitPosition", "mergePositions", "redeemPositions", "convertPositions"):
            getattr(contract.functions, fn_name).return_value.build_transaction.return_value = {
                "data": "0x" + "ab" * 32,
            }
    captured: dict = {}

    def fake_encode(calls):
        captured["calls"] = calls
        return "0x" + "cd" * 64

    monkeypatch.setattr(c, "_encode_proxy_calls", fake_encode)
    monkeypatch.setattr(
        c,
        "get_relay_payload",
        lambda **kw: {"address": "0x" + "ee" * 20, "nonce": "42"},
    )
    submit = MagicMock(return_value={"transactionID": "abc", "transactionHash": "0x123"})
    monkeypatch.setattr(c, "submit_transaction", submit)
    return c, captured, submit


def test_batch_ctf_ops_bundles_three_calls(monkeypatch):
    c, captured, submit = _proxy_ctf_client(monkeypatch)
    ops = [
        {"op": "split", "condition_id": STUB_CONDITION_ID, "amount": 1_000_000},
        {"op": "merge", "condition_id": STUB_CONDITION_ID, "amount": 500_000},
        {"op": "redeem", "condition_id": STUB_CONDITION_ID},
    ]
    result = c.batch_ctf_ops(ops)
    assert len(captured["calls"]) == 3
    submit.assert_called_once()
    assert submit.call_args[1]["to"] == "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
    assert result["transactionHash"] == "0x123"


def test_batch_ctf_ops_dataframe_input(monkeypatch):
    import pandas as pd

    c, captured, _ = _proxy_ctf_client(monkeypatch)
    df = pd.DataFrame(
        [
            {"op": "split", "condition_id": STUB_CONDITION_ID, "amount": 1_000_000},
            {"op": "merge", "condition_id": STUB_CONDITION_ID, "amount": 500_000},
        ]
    )
    c.batch_ctf_ops(df)
    assert len(captured["calls"]) == 2


def test_batch_ctf_ops_aggregates_approvals(monkeypatch):
    c, _, _ = _proxy_ctf_client(monkeypatch)
    # Current allowance is below the total so approval must fire exactly once
    c._usdc_contract.functions.allowance.return_value.call.return_value = 0
    ensure_calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        c,
        "_ensure_allowance",
        lambda spender, amount: ensure_calls.append((spender, amount)),
    )
    ops = [
        {"op": "split", "condition_id": STUB_CONDITION_ID, "amount": 1_000_000, "neg_risk": False},
        {"op": "merge", "condition_id": STUB_CONDITION_ID, "amount": 2_000_000, "neg_risk": False},
        {"op": "redeem", "condition_id": STUB_CONDITION_ID},  # no approval
    ]
    c.batch_ctf_ops(ops, auto_approve=True)
    # Single aggregated approval for CONDITIONAL_TOKENS spender
    assert len(ensure_calls) == 1
    assert ensure_calls[0] == (
        "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
        3_000_000,
    )


def test_batch_ctf_ops_rejects_eoa(ctf_client: PolymarketPandas, monkeypatch):
    _mock_web3(ctf_client, monkeypatch)
    with pytest.raises(PolymarketAuthError, match="proxy wallet"):
        ctf_client.batch_ctf_ops(
            [{"op": "merge", "condition_id": STUB_CONDITION_ID, "amount": 1_000_000}]
        )


def test_batch_ctf_ops_empty_raises(monkeypatch):
    c, _, _ = _proxy_ctf_client(monkeypatch)
    with pytest.raises(ValueError, match="non-empty"):
        c.batch_ctf_ops([])


def test_batch_ctf_ops_unknown_op_raises(monkeypatch):
    c, _, _ = _proxy_ctf_client(monkeypatch)
    with pytest.raises(ValueError, match="op must be one of"):
        c.batch_ctf_ops([{"op": "swap", "condition_id": STUB_CONDITION_ID}])


def test_batch_ctf_ops_neg_risk_redeem_requires_amounts(monkeypatch):
    c, _, _ = _proxy_ctf_client(monkeypatch)
    with pytest.raises(ValueError, match="amounts="):
        c.batch_ctf_ops([{"op": "redeem", "condition_id": STUB_CONDITION_ID, "neg_risk": True}])


def test_batch_ctf_ops_estimate(monkeypatch):
    c, _, submit = _proxy_ctf_client(monkeypatch)
    c._w3.eth.get_balance.return_value = 10**18
    result = c.batch_ctf_ops(
        [{"op": "merge", "condition_id": STUB_CONDITION_ID, "amount": 1_000_000}],
        estimate=True,
    )
    submit.assert_not_called()
    assert result["gas"] == 200_000
    assert isinstance(result["costMatic"], float)


# ── build_order ─────────────────────────────────────────────────────────────


def test_submit_order_requires_auth(client: PolymarketPandas):
    """submit_order raises PolymarketAuthError when credentials are missing."""
    with pytest.raises(PolymarketAuthError, match="CLOB API credentials"):
        client.submit_order("123", 0.5, 1.0, "BUY")


# ── Order amount calculation helpers ─────────────────────────────────────


def test_round_normal_matches_clob():
    """_round_normal uses integer-arithmetic rounding, not banker's rounding."""
    # Python round(0.5) == 0 (banker's), but round(0.5 * 10) / 10 == 1.0
    assert _round_normal(0.85, 1) == 0.9
    assert _round_normal(0.86, 2) == 0.86
    assert _round_normal(0.001, 3) == 0.001


def test_round_up():
    """_round_up matches py-clob-client's ceil-based rounding."""
    assert _round_up(4.30001, 4) == 4.3001
    assert _round_up(1.0, 2) == 1.0
    assert _round_up(1.001, 2) == 1.01


def test_round_down():
    assert _round_down(1.999, 2) == 1.99
    assert _round_down(5.0, 0) == 5.0


def test_decimal_places():
    """_decimal_places uses Decimal for precision."""
    assert _decimal_places(1.0) == 1
    assert _decimal_places(1.23) == 2
    assert _decimal_places(1.230) == 2
    assert _decimal_places(100) == 0


def test_to_token_decimals():
    assert _to_token_decimals(1.0) == 1_000_000
    assert _to_token_decimals(0.5) == 500_000
    assert _to_token_decimals(0.123456) == 123_456


def test_get_order_amounts_buy():
    """BUY amounts match py-clob-client for a standard order."""
    side_int, maker, taker = PolymarketPandas._get_order_amounts("BUY", 0.50, 10.0, "0.01")
    assert side_int == 0
    assert taker == 10_000_000  # 10 shares
    assert maker == 5_000_000  # 10 * 0.5 = 5 USDC


def test_get_order_amounts_sell():
    """SELL amounts match py-clob-client for a standard order."""
    side_int, maker, taker = PolymarketPandas._get_order_amounts("SELL", 0.50, 10.0, "0.01")
    assert side_int == 1
    assert maker == 10_000_000  # 10 shares
    assert taker == 5_000_000  # 10 * 0.5 = 5 USDC


def test_build_order_salt_is_int(authed_client: PolymarketPandas):
    """build_order returns salt as int, not str (CLOB API requires numeric)."""
    authed_client.private_key = "0x" + "ab" * 32  # dummy key for signing
    authed_client.address = "0x" + "00" * 20
    order = authed_client.build_order(
        token_id="12345678901234567890",
        price=0.50,
        size=10.0,
        side="BUY",
        tick_size="0.01",
        neg_risk=False,
        fee_rate_bps=0,
    )
    assert isinstance(order["salt"], int), f"salt should be int, got {type(order['salt'])}"
    assert isinstance(order["signatureType"], int)
    # These should be strings per CLOB API
    assert isinstance(order["makerAmount"], str)
    assert isinstance(order["takerAmount"], str)
    assert isinstance(order["tokenId"], str)


# ── submit_orders (DataFrame) ──────────────────────────────────────────


def test_submit_orders_dataframe(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    """submit_orders accepts a DataFrame and batch-submits via /orders."""
    authed_client.private_key = "0x" + "ab" * 32
    authed_client.address = "0x" + "00" * 20

    # Mock the market-param endpoints (auto-fetched by build_order)
    httpx_mock.add_response(
        url="https://clob.polymarket.com/neg-risk?token_id=11111111111111111111",
        json={"neg_risk": False},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/tick-size?token_id=11111111111111111111",
        json={"minimum_tick_size": 0.01},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/fee-rate?token_id=11111111111111111111",
        json={"base_fee": 1000},
    )
    # Mock the batch /orders endpoint
    httpx_mock.add_response(
        url="https://clob.polymarket.com/orders",
        json=[{"orderID": "0xabc", "status": "matched"}],
    )

    orders_df = pd.DataFrame(
        {
            "tokenId": ["11111111111111111111", "11111111111111111111"],
            "price": [0.50, 0.60],
            "size": [10.0, 5.0],
            "side": ["BUY", "SELL"],
        }
    )
    result = authed_client.submit_orders(orders_df)
    assert isinstance(result, pd.DataFrame)
    assert not result.empty

    # Verify /orders was called (not /order)
    requests = httpx_mock.get_requests()
    orders_requests = [r for r in requests if r.url.path == "/orders"]
    assert len(orders_requests) == 1
    body = orjson.loads(orders_requests[0].content)
    assert len(body) == 2
    assert "order" in body[0]
    assert body[0]["orderType"] == "GTC"


def test_submit_orders_post_only(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    """submit_orders passes postOnly flag through to the /orders payload."""
    authed_client.private_key = "0x" + "ab" * 32
    authed_client.address = "0x" + "00" * 20

    httpx_mock.add_response(
        url="https://clob.polymarket.com/neg-risk?token_id=11111111111111111111",
        json={"neg_risk": False},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/tick-size?token_id=11111111111111111111",
        json={"minimum_tick_size": 0.01},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/fee-rate?token_id=11111111111111111111",
        json={"base_fee": 1000},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/orders",
        json=[{"orderID": "0xabc", "status": "live"}],
    )

    orders_df = pd.DataFrame(
        {
            "tokenId": ["11111111111111111111"],
            "price": [0.50],
            "size": [10.0],
            "side": ["BUY"],
            "postOnly": [True],
        }
    )
    result = authed_client.submit_orders(orders_df)
    assert isinstance(result, pd.DataFrame)

    orders_requests = [r for r in httpx_mock.get_requests() if r.url.path == "/orders"]
    body = orjson.loads(orders_requests[0].content)
    assert body[0]["postOnly"] is True


def test_place_order_post_only_rejects_fok(authed_client: PolymarketPandas):
    """place_order raises ValueError when post_only is used with FOK."""
    with pytest.raises(ValueError, match="post_only is only valid with GTC or GTD"):
        authed_client.place_order(
            order={"fake": "order"},
            owner="key",
            orderType="FOK",
            post_only=True,
        )


def test_submit_orders_batches_over_15(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    """submit_orders splits >15 orders into multiple /orders calls."""
    authed_client.private_key = "0x" + "ab" * 32
    authed_client.address = "0x" + "00" * 20

    httpx_mock.add_response(
        url="https://clob.polymarket.com/neg-risk?token_id=22222222222222222222",
        json={"neg_risk": False},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/tick-size?token_id=22222222222222222222",
        json={"minimum_tick_size": 0.01},
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/fee-rate?token_id=22222222222222222222",
        json={"base_fee": 0},
    )
    # Two batch responses
    httpx_mock.add_response(
        url="https://clob.polymarket.com/orders",
        json=[{"orderID": f"0x{i:04x}", "status": "live"} for i in range(15)],
    )
    httpx_mock.add_response(
        url="https://clob.polymarket.com/orders",
        json=[{"orderID": "0x000f", "status": "live"}],
    )

    orders_df = pd.DataFrame(
        {
            "tokenId": ["22222222222222222222"] * 16,
            "price": [0.50] * 16,
            "size": [1.0] * 16,
            "side": ["BUY"] * 16,
        }
    )
    result = authed_client.submit_orders(orders_df)
    assert isinstance(result, pd.DataFrame)

    # Should have made 2 batch calls: 15 + 1
    orders_requests = [r for r in httpx_mock.get_requests() if r.url.path == "/orders"]
    assert len(orders_requests) == 2
    first_batch = orjson.loads(orders_requests[0].content)
    second_batch = orjson.loads(orders_requests[1].content)
    assert len(first_batch) == 15
    assert len(second_batch) == 1


# ── Builder attribution headers ──────────────────────────────────────────────


_BUILDER_HEADERS = {
    "POLY_BUILDER_API_KEY",
    "POLY_BUILDER_PASSPHRASE",
    "POLY_BUILDER_TIMESTAMP",
    "POLY_BUILDER_SIGNATURE",
}


def test_place_order_attaches_builder_headers_when_set(
    builder_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """When builder creds are set, place_order attaches POLY_BUILDER_* headers."""
    httpx_mock.add_response(
        url="https://clob.polymarket.com/order",
        json={"orderID": "0xabc", "status": "live"},
    )
    builder_client.place_order(
        order={"fake": "signed-order"},
        owner="test-api-key",
        orderType="GTC",
    )
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/order")
    assert "POLY_API_KEY" in req.headers  # L2 still attached
    for h in _BUILDER_HEADERS:
        assert h in req.headers, f"missing builder header {h}"
    assert req.headers["POLY_BUILDER_API_KEY"] == "test-builder-api-key"
    assert req.headers["POLY_BUILDER_PASSPHRASE"] == "test-builder-passphrase"


def test_place_order_no_builder_headers_when_unset(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """Without builder creds, place_order sends only L2 headers."""
    httpx_mock.add_response(
        url="https://clob.polymarket.com/order",
        json={"orderID": "0xabc", "status": "live"},
    )
    authed_client.place_order(
        order={"fake": "signed-order"},
        owner="test-api-key",
        orderType="GTC",
    )
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/order")
    assert "POLY_API_KEY" in req.headers
    for h in _BUILDER_HEADERS:
        assert h not in req.headers, f"unexpected builder header {h}"


def test_place_orders_attaches_builder_headers_when_set(
    builder_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """When builder creds are set, place_orders attaches POLY_BUILDER_* headers."""
    httpx_mock.add_response(
        url="https://clob.polymarket.com/orders",
        json=[{"orderID": "0xabc", "status": "live"}],
    )
    # Build a minimal valid signed-order DataFrame matching PlaceOrderSchema.
    orders_df = pd.DataFrame(
        [
            {
                "salt": "1",
                "maker": "0x" + "00" * 20,
                "signer": "0x" + "00" * 20,
                "taker": "0x" + "00" * 20,
                "tokenId": "1" * 20,
                "makerAmount": "1000000",
                "takerAmount": "2000000",
                "expiration": "0",
                "nonce": "0",
                "feeRateBps": "0",
                "side": "BUY",
                "signatureType": 1,
                "signature": "0x" + "ab" * 32,
                "owner": "test-api-key",
                "orderType": "GTC",
            }
        ]
    )
    builder_client.place_orders(orders_df)
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/orders")
    for h in _BUILDER_HEADERS:
        assert h in req.headers, f"missing builder header {h}"


def test_get_active_orders_does_not_attach_builder_headers(
    builder_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """Non-order private endpoints (attribute=False default) skip builder headers."""
    httpx_mock.add_response(
        url="https://clob.polymarket.com/data/orders",
        json={"data": [], "next_cursor": "LTE=", "count": 0, "limit": 100},
    )
    builder_client.get_active_orders()
    req = next(r for r in httpx_mock.get_requests() if r.url.path == "/data/orders")
    assert "POLY_API_KEY" in req.headers
    for h in _BUILDER_HEADERS:
        assert h not in req.headers, f"unexpected builder header {h} on get_active_orders"


# ── Rewards: Public endpoints ────────────────────────────────────────────────


_REWARDS_CURRENT_PAYLOAD = {
    "limit": 500,
    "count": 1,
    "next_cursor": "LTE=",
    "data": [
        {
            "condition_id": "0xabc",
            "rewards_max_spread": 99,
            "rewards_min_size": 10,
            "rewards_config": [
                {
                    "id": 0,
                    "asset_address": "0x9c4E1703476E875070EE25b56A58B008CFb8FA78",
                    "start_date": "2024-03-01",
                    "end_date": "2500-12-31",
                    "rate_per_day": 2,
                    "total_rewards": 92,
                },
                {
                    "id": 0,
                    "asset_address": "0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
                    "start_date": "2024-03-01",
                    "end_date": "2500-12-31",
                    "rate_per_day": 1,
                    "total_rewards": 46,
                },
            ],
            "sponsored_daily_rate": 0.5,
            "sponsors_count": 2,
            "native_daily_rate": 2.5,
            "total_daily_rate": 3,
        }
    ],
}


def test_get_rewards_markets_current(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/current",
        json=_REWARDS_CURRENT_PAYLOAD,
    )
    result = client.get_rewards_markets_current()
    assert isinstance(result["data"], pd.DataFrame)
    assert result["next_cursor"] == "LTE="
    assert len(result["data"]) == 1
    # Without expansion, rewardsConfig is an opaque list column
    assert "rewardsConfig" in result["data"].columns


def test_get_rewards_markets_current_expand(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/current",
        json=_REWARDS_CURRENT_PAYLOAD,
    )
    result = client.get_rewards_markets_current(expand_rewards_config=True)
    df = result["data"]
    assert isinstance(df, pd.DataFrame)
    # 1 market × 2 config entries = 2 rows
    assert len(df) == 2
    # Expanded columns are present
    assert "rewardsConfigAssetAddress" in df.columns
    assert "rewardsConfigRatePerDay" in df.columns
    assert "rewardsConfigTotalRewards" in df.columns
    # Meta columns are repeated
    assert df["conditionId"].tolist() == ["0xabc", "0xabc"]
    assert df["rewardsConfigRatePerDay"].tolist() == [2.0, 1.0]


def test_get_rewards_markets_multi(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/multi",
        json={
            "limit": 100,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "condition_id": "0xabc",
                    "market_id": "m1",
                    "question": "Test?",
                    "rewards_max_spread": 0.05,
                    "rewards_min_size": 50,
                    "rewards_config": [
                        {
                            "id": 0,
                            "asset_address": "0xABC",
                            "start_date": "2024-01-01",
                            "end_date": "2500-12-31",
                            "rate_per_day": 5,
                            "total_rewards": 100,
                        }
                    ],
                }
            ],
        },
    )
    result = client.get_rewards_markets_multi()
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


def test_get_rewards_markets_multi_expand(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/multi",
        json={
            "limit": 100,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "condition_id": "0xabc",
                    "market_id": "m1",
                    "question": "Test?",
                    "rewards_max_spread": 0.05,
                    "rewards_min_size": 50,
                    "rewards_config": [
                        {
                            "id": 0,
                            "asset_address": "0xABC",
                            "start_date": "2024-01-01",
                            "end_date": "2500-12-31",
                            "rate_per_day": 5,
                            "total_rewards": 100,
                        }
                    ],
                }
            ],
        },
    )
    result = client.get_rewards_markets_multi(expand_rewards_config=True)
    df = result["data"]
    assert len(df) == 1
    assert "rewardsConfigAssetAddress" in df.columns
    assert df["rewardsConfigRatePerDay"].iloc[0] == 5.0


def test_get_rewards_markets_multi_expand_tokens(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/multi",
        json={
            "limit": 100,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "condition_id": "0xabc",
                    "market_id": "m1",
                    "question": "Test?",
                    "rewards_max_spread": 0.05,
                    "rewards_min_size": 50,
                    "tokens": [
                        {"token_id": "tok1", "outcome": "YES", "price": 0.8},
                        {"token_id": "tok2", "outcome": "NO", "price": 0.2},
                    ],
                    "rewards_config": [
                        {
                            "id": 0,
                            "asset_address": "0xABC",
                            "start_date": "2024-01-01",
                            "end_date": "2500-12-31",
                            "rate_per_day": 5,
                            "total_rewards": 100,
                        }
                    ],
                }
            ],
        },
    )
    result = client.get_rewards_markets_multi(expand_tokens=True, expand_rewards_config=True)
    df = result["data"]
    # 1 market × 2 tokens × 1 reward config = 2 rows
    assert len(df) == 2
    assert "tokensTokenId" in df.columns
    assert "tokensOutcome" in df.columns
    assert "rewardsConfigAssetAddress" in df.columns
    assert df["tokensOutcome"].tolist() == ["YES", "NO"]


def test_get_rewards_market(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/markets/0xabc123",
        json={
            "limit": 500,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "condition_id": "0xabc123",
                    "question": "Test market?",
                    "rewards_max_spread": 0.03,
                    "rewards_min_size": 100,
                }
            ],
        },
    )
    result = client.get_rewards_market("0xabc123")
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


# ── Rewards: Private endpoints ───────────────────────────────────────────────


def test_get_rewards_earnings(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/user?date=2025-01-01",
        json={
            "limit": 100,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "date": "2025-01-01",
                    "condition_id": "0xabc",
                    "asset_address": "0xdef",
                    "maker_address": "0x123",
                    "earnings": 1.5,
                    "asset_rate": 100.0,
                }
            ],
        },
    )
    result = authed_client.get_rewards_earnings(date="2025-01-01")
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


def test_get_rewards_earnings_total(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/user/total?date=2025-01-01",
        json=[
            {
                "date": "2025-01-01",
                "asset_address": "0xdef",
                "maker_address": "0x123",
                "earnings": 10.5,
                "asset_rate": 100.0,
            }
        ],
    )
    result = authed_client.get_rewards_earnings_total(date="2025-01-01")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1


def test_get_rewards_percentages(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/user/percentages",
        json={"0xabc": 20, "0xdef": 15},
    )
    result = authed_client.get_rewards_percentages()
    assert isinstance(result, dict)
    assert result["0xabc"] == 20
    assert result["0xdef"] == 15


def test_get_rewards_user_markets(authed_client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/rewards/user/markets",
        json={
            "limit": 100,
            "count": 1,
            "next_cursor": "LTE=",
            "data": [
                {
                    "condition_id": "0xabc",
                    "market_id": "m1",
                    "question": "Test?",
                    "earning_percentage": 5.0,
                    "earnings": [],
                }
            ],
        },
    )
    result = authed_client.get_rewards_user_markets()
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


def test_get_rewards_earnings_requires_auth(client: PolymarketPandas):
    """Private rewards endpoints require L2 auth."""
    from polymarket_pandas import PolymarketAuthError

    with pytest.raises(PolymarketAuthError):
        client.get_rewards_earnings(date="2025-01-01")


# ── to_unix_timestamp ────────────────────────────────────────────────────────


def test_to_unix_timestamp_int_passthrough():
    from polymarket_pandas.utils import to_unix_timestamp

    assert to_unix_timestamp(0) == 0
    assert to_unix_timestamp(1700000000) == 1700000000


def test_to_unix_timestamp_float_passthrough():
    from polymarket_pandas.utils import to_unix_timestamp

    assert to_unix_timestamp(1700000000.5) == 1700000000


def test_to_unix_timestamp_from_pd_timestamp():
    from polymarket_pandas.utils import to_unix_timestamp

    ts = pd.Timestamp("2024-01-01T00:00:00Z")
    assert to_unix_timestamp(ts) == 1704067200


def test_to_unix_timestamp_from_naive_pd_timestamp():
    from polymarket_pandas.utils import to_unix_timestamp

    ts = pd.Timestamp("2024-01-01T00:00:00")
    assert to_unix_timestamp(ts) == 1704067200


def test_to_unix_timestamp_from_string():
    from polymarket_pandas.utils import to_unix_timestamp

    assert to_unix_timestamp("2024-01-01T00:00:00Z") == 1704067200


def test_to_unix_timestamp_from_datetime():
    from datetime import UTC, datetime

    from polymarket_pandas.utils import to_unix_timestamp

    dt = datetime(2024, 1, 1, tzinfo=UTC)
    assert to_unix_timestamp(dt) == 1704067200


def test_to_unix_timestamp_invalid_type():
    from polymarket_pandas.utils import to_unix_timestamp

    with pytest.raises(TypeError, match="Cannot convert"):
        to_unix_timestamp([1, 2, 3])


# ── Schema smoke tests ───────────────────────────────────────────────────────


def test_market_schema_validates_good_data():
    from polymarket_pandas.schemas import MarketSchema

    df = pd.DataFrame(
        [
            {
                "id": "123",
                "conditionId": "0xabc",
                "slug": "test-market",
                "question": "Will it rain?",
                "volume": 1000.0,
                "liquidity": 500.0,
                "active": True,
                "closed": False,
            }
        ]
    )
    validated = MarketSchema.validate(df)
    assert len(validated) == 1


def test_orderbook_schema_validates_good_data():
    from polymarket_pandas.schemas import OrderbookSchema

    df = pd.DataFrame([{"price": 0.5, "size": 100.0}, {"price": 0.6, "size": 200.0}])
    validated = OrderbookSchema.validate(df)
    assert len(validated) == 2


def test_schema_allows_extra_columns():
    """strict=False means extra columns don't cause validation errors."""
    from polymarket_pandas.schemas import PriceHistorySchema

    df = pd.DataFrame([{"t": 1700000000, "p": 0.5, "extra_col": "hello"}])
    validated = PriceHistorySchema.validate(df)
    assert "extra_col" in validated.columns


# ── TypedDict type assertions ────────────────────────────────────────────────


def test_typed_imports():
    """All TypedDicts and schemas are importable from the top-level package."""
    from polymarket_pandas import (
        ActiveOrderSchema,
        ApiCredentials,
        BalanceAllowance,
        BridgeAddress,
        CancelOrdersResponse,
        CursorPage,
        EventSchema,
        LastTradePrice,
        LeaderboardSchema,
        MarketSchema,
        OrderbookSchema,
        OrdersCursorPage,
        PositionSchema,
        PriceHistorySchema,
        RelayPayload,
        SendOrderResponse,
        SignedOrder,
        SubmitTransactionResponse,
        TransactionReceipt,
        UserTradesCursorPage,
    )

    # Ensure they're all types (not None)
    for t in [
        ActiveOrderSchema,
        ApiCredentials,
        BalanceAllowance,
        BridgeAddress,
        CancelOrdersResponse,
        CursorPage,
        EventSchema,
        LastTradePrice,
        LeaderboardSchema,
        MarketSchema,
        OrderbookSchema,
        OrdersCursorPage,
        PositionSchema,
        PriceHistorySchema,
        RelayPayload,
        SendOrderResponse,
        SignedOrder,
        SubmitTransactionResponse,
        TransactionReceipt,
        UserTradesCursorPage,
    ]:
        assert t is not None


# ── get_active_orders returns CursorPage ─────────────────────────────────────


def test_get_active_orders_returns_cursor_page(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/data/orders",
        json={
            "data": [
                {
                    "id": "order-1",
                    "market": "0xabc",
                    "asset_id": "tok-1",
                    "side": "BUY",
                    "price": "0.5",
                    "original_size": "100",
                    "size_matched": "0",
                    "status": "live",
                    "outcome": "Yes",
                    "order_type": "GTC",
                }
            ],
            "next_cursor": "LTE=",
            "count": 1,
            "limit": 100,
        },
    )
    result = authed_client.get_active_orders()
    assert isinstance(result, dict)
    assert "data" in result
    assert "next_cursor" in result
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


# ── get_user_trades returns CursorPage ───────────────────────────────────────


def test_get_user_trades_returns_cursor_page(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/data/trades",
        json={
            "data": [
                {
                    "id": "trade-1",
                    "market": "0xabc",
                    "asset_id": "tok-1",
                    "side": "BUY",
                    "size": "10",
                    "price": "0.5",
                }
            ],
            "next_cursor": "LTE=",
            "count": 1,
            "limit": 100,
        },
    )
    result = authed_client.get_user_trades()
    assert isinstance(result, dict)
    assert "data" in result
    assert "next_cursor" in result
    assert isinstance(result["data"], pd.DataFrame)
    assert len(result["data"]) == 1


# ── Order input validation schemas ────────────────────────────────────


def test_place_order_schema_valid():
    """PlaceOrderSchema accepts a well-formed signed-order DataFrame."""
    df = pd.DataFrame(
        [
            {
                "salt": 12345,
                "maker": "0x" + "ab" * 20,
                "signer": "0x" + "cd" * 20,
                "taker": "0x" + "00" * 20,
                "tokenId": "111222333",
                "makerAmount": "5000000",
                "takerAmount": "10000000",
                "side": "BUY",
                "expiration": "0",
                "nonce": "0",
                "feeRateBps": "30",
                "signature": "0xdeadbeef",
                "signatureType": 1,
                "owner": "my-api-key",
                "orderType": "GTC",
            }
        ]
    )
    validated = PlaceOrderSchema.validate(df)
    assert len(validated) == 1


def test_place_order_schema_rejects_bad_side():
    """PlaceOrderSchema rejects invalid side values."""
    import pandera

    df = pd.DataFrame(
        [
            {
                "salt": 1,
                "maker": "0x" + "ab" * 20,
                "signer": "0x" + "cd" * 20,
                "taker": "0x" + "00" * 20,
                "tokenId": "111",
                "makerAmount": "100",
                "takerAmount": "200",
                "side": "HOLD",
                "expiration": "0",
                "nonce": "0",
                "feeRateBps": "0",
                "signature": "0xaa",
                "signatureType": 1,
                "owner": "key",
                "orderType": "GTC",
            }
        ]
    )
    with pytest.raises(pandera.errors.SchemaError):
        PlaceOrderSchema.validate(df)


def test_place_order_schema_rejects_bad_address():
    """PlaceOrderSchema rejects malformed Ethereum addresses."""
    import pandera

    df = pd.DataFrame(
        [
            {
                "salt": 1,
                "maker": "not-an-address",
                "signer": "0x" + "cd" * 20,
                "taker": "0x" + "00" * 20,
                "tokenId": "111",
                "makerAmount": "100",
                "takerAmount": "200",
                "side": "BUY",
                "expiration": "0",
                "nonce": "0",
                "feeRateBps": "0",
                "signature": "0xaa",
                "signatureType": 1,
                "owner": "key",
                "orderType": "GTC",
            }
        ]
    )
    with pytest.raises(pandera.errors.SchemaError):
        PlaceOrderSchema.validate(df)


def test_submit_order_schema_valid():
    """SubmitOrderSchema accepts a well-formed intent DataFrame."""
    df = pd.DataFrame(
        {
            "tokenId": ["111222333"],
            "price": [0.55],
            "size": [10.0],
            "side": ["BUY"],
        }
    )
    validated = SubmitOrderSchema.validate(df)
    assert len(validated) == 1


def test_submit_order_schema_rejects_bad_price():
    """SubmitOrderSchema rejects price > 1."""
    import pandera

    df = pd.DataFrame(
        {
            "tokenId": ["111"],
            "price": [1.5],
            "size": [10.0],
            "side": ["BUY"],
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        SubmitOrderSchema.validate(df)


def test_submit_order_schema_rejects_zero_size():
    """SubmitOrderSchema rejects size <= 0."""
    import pandera

    df = pd.DataFrame(
        {
            "tokenId": ["111"],
            "price": [0.5],
            "size": [0.0],
            "side": ["BUY"],
        }
    )
    with pytest.raises(pandera.errors.SchemaError):
        SubmitOrderSchema.validate(df)


def test_place_orders_rejects_over_15(authed_client: PolymarketPandas):
    """place_orders raises ValueError when given >15 orders."""
    df = pd.DataFrame(
        {
            "salt": range(16),
            "maker": ["0x" + "ab" * 20] * 16,
            "signer": ["0x" + "cd" * 20] * 16,
            "taker": ["0x" + "00" * 20] * 16,
            "tokenId": ["111"] * 16,
            "makerAmount": ["100"] * 16,
            "takerAmount": ["200"] * 16,
            "side": ["BUY"] * 16,
            "expiration": ["0"] * 16,
            "nonce": ["0"] * 16,
            "feeRateBps": ["0"] * 16,
            "signature": ["0xaa"] * 16,
            "signatureType": [1] * 16,
            "owner": ["key"] * 16,
            "orderType": ["GTC"] * 16,
        }
    )
    with pytest.raises(ValueError, match="at most 15"):
        authed_client.place_orders(df)


# ─────────────────────────────────────────────────────────────────────────
# xtracker API tests (fixtures captured from the live service)
# ─────────────────────────────────────────────────────────────────────────


def _xt_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"xtracker_{name}.json").read_text())


def test_get_xtracker_users(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://xtracker.polymarket.com/api/users?platform=X",
        json=_xt_fixture("users"),
    )
    df = client.get_xtracker_users(platform="X")
    assert isinstance(df, pd.DataFrame)
    assert {"id", "handle", "platform"} <= set(df.columns)
    XTrackerUserSchema.validate(df)


def test_get_xtracker_user(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://xtracker.polymarket.com/api/users/ZelenskyyUa?platform=X",
        json=_xt_fixture("user"),
    )
    user = client.get_xtracker_user("ZelenskyyUa", platform="X")
    assert isinstance(user, dict)
    assert user["handle"] == "ZelenskyyUa"
    assert user["platform"] == "X"


def test_get_xtracker_user_posts(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=(
            "https://xtracker.polymarket.com/api/users/ZelenskyyUa/posts"
            "?platform=X&startDate=2026-04-02&endDate=2026-04-09&timezone=EST"
        ),
        json=_xt_fixture("user_posts"),
    )
    df = client.get_xtracker_user_posts(
        "ZelenskyyUa",
        platform="X",
        start_date="2026-04-02",
        end_date="2026-04-09",
    )
    assert isinstance(df, pd.DataFrame)
    assert {"id", "userId", "content"} <= set(df.columns)
    XTrackerPostSchema.validate(df)


def test_get_xtracker_user_trackings(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://xtracker.polymarket.com/api/users/ZelenskyyUa/trackings?activeOnly=true",
        json=_xt_fixture("user_trackings"),
    )
    df = client.get_xtracker_user_trackings("ZelenskyyUa", active_only=True)
    assert isinstance(df, pd.DataFrame)
    XTrackerTrackingSchema.validate(df)


def test_get_xtracker_trackings(client: PolymarketPandas, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://xtracker.polymarket.com/api/trackings?activeOnly=true",
        json=_xt_fixture("trackings"),
    )
    df = client.get_xtracker_trackings(active_only=True)
    assert isinstance(df, pd.DataFrame)
    assert "marketLink" in df.columns
    XTrackerTrackingSchema.validate(df)


def test_get_xtracker_tracking_with_stats(client: PolymarketPandas, httpx_mock: HTTPXMock):
    fixture = _xt_fixture("tracking")
    tid = fixture["data"]["id"]
    httpx_mock.add_response(
        url=f"https://xtracker.polymarket.com/api/trackings/{tid}?includeStats=true",
        json=fixture,
    )
    res = client.get_xtracker_tracking(tid, include_stats=True)
    assert isinstance(res, dict)
    assert res["id"] == tid
    # `stats` was materialised as a DataFrame and the scalar aggregates
    # were lifted onto .attrs
    assert isinstance(res["stats"], pd.DataFrame)
    assert {"date", "count", "cumulative"} <= set(res["stats"].columns)
    assert "total" in res["stats"].attrs
    assert "pace" in res["stats"].attrs
    XTrackerDailyStatSchema.validate(res["stats"])


def test_get_xtracker_metrics(client: PolymarketPandas, httpx_mock: HTTPXMock):
    fixture = _xt_fixture("metrics")
    user_id = fixture["data"][0]["userId"]
    httpx_mock.add_response(
        url=(
            f"https://xtracker.polymarket.com/api/metrics/{user_id}"
            "?type=daily&startDate=2026-03-26&endDate=2026-04-09"
        ),
        json=fixture,
    )
    df = client.get_xtracker_metrics(
        user_id,
        type="daily",
        start_date="2026-03-26",
        end_date="2026-04-09",
    )
    assert isinstance(df, pd.DataFrame)
    # nested `data` object flattened with sep="_"
    assert {"dataCount", "dataCumulative", "dataTrackingId"} <= set(df.columns)
    XTrackerMetricSchema.validate(df)


def test_xtracker_envelope_unwrap_raises_on_failure(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """When xtracker returns {success: false, error: ...} we raise PolymarketAPIError."""
    httpx_mock.add_response(
        url="https://xtracker.polymarket.com/api/trackings?activeOnly=true",
        json={"success": False, "error": "kaboom"},
    )
    with pytest.raises(PolymarketAPIError, match="kaboom"):
        client.get_xtracker_trackings(active_only=True)


# ── get_balance_allowance parameter shape ────────────────────────────────────


def _balance_allowance_mock(httpx_mock: HTTPXMock, expected_query: str):
    """Helper: mock the CLOB balance-allowance endpoint with an exact
    query-string match so failing tests point at param-shape regressions."""
    httpx_mock.add_response(
        method="GET",
        url=f"https://clob.polymarket.com/balance-allowance?{expected_query}",
        json={"balance": "100", "allowances": {}},
    )


def test_get_balance_allowance_int_asset_type_maps_to_enum(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """asset_type=0 (int) must be sent to the server as 'COLLATERAL'."""
    _balance_allowance_mock(httpx_mock, "asset_type=COLLATERAL&signatureType=1")
    out = authed_client.get_balance_allowance(asset_type=0)
    assert out["balance"] == "100"


def test_get_balance_allowance_int_conditional_maps_to_enum(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    _balance_allowance_mock(
        httpx_mock,
        "asset_type=CONDITIONAL&token_id=tok123&signatureType=1",
    )
    out = authed_client.get_balance_allowance(asset_type=1, token_id="tok123")
    assert out["balance"] == "100"


def test_get_balance_allowance_string_asset_type_passthrough(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """Callers who already pass the string enum should see it untouched."""
    _balance_allowance_mock(httpx_mock, "asset_type=COLLATERAL&signatureType=1")
    out = authed_client.get_balance_allowance(asset_type="COLLATERAL")
    assert out["balance"] == "100"


def test_get_balance_allowance_omits_signature_type_when_unset(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    """A client with signature_type=None should not tack signatureType onto
    the query (server would reject a null value)."""
    authed_client.signature_type = None
    httpx_mock.add_response(
        method="GET",
        url="https://clob.polymarket.com/balance-allowance?asset_type=COLLATERAL",
        json={"balance": "0", "allowances": {}},
    )
    authed_client.get_balance_allowance(asset_type=0)


# ════════════════════════════════════════════════════════════════════
#  UMA resolution / dispute (_uma.py)
# ════════════════════════════════════════════════════════════════════


STUB_QUESTION_ID = "0x" + "cd" * 32


def _mock_uma(ctf_client, monkeypatch, *, state_idx: int = 1):
    """Inject a mock web3 + UMA adapter/OOv2 into ``ctf_client``.

    ``state_idx`` maps to the ``_OO_STATES`` tuple (0=Invalid, 1=Requested,
    2=Proposed, ...).
    """
    ct, nr, usdc = _mock_web3(ctf_client, monkeypatch)

    adapter = MagicMock()
    nr_adapter = MagicMock()
    oo = MagicMock()

    ctf_client._w3.eth.contract = MagicMock(side_effect=[adapter, nr_adapter, oo])

    usdc.functions.allowance.return_value.call.return_value = 0

    question_tuple = (
        1_700_000_000,
        2_000_000,
        500_000_000,
        7200,
        0,
        False,
        False,
        False,
        False,
        "0x" + "11" * 20,
        "0x" + "22" * 20,
        b"q?",
    )
    adapter.functions.getQuestion.return_value.call.return_value = question_tuple
    nr_adapter.functions.getQuestion.return_value.call.return_value = question_tuple
    adapter.functions.ready.return_value.call.return_value = True
    nr_adapter.functions.ready.return_value.call.return_value = True

    oo.functions.getState.return_value.call.return_value = state_idx
    oo.functions.getRequest.return_value.call.return_value = (
        "0x" + "33" * 20,
        "0x" + "00" * 20,
        "0x" + "44" * 20,
        False,
        (False, False, False, False, False, 500_000_000, 0),
        0,
        0,
        1_700_007_200,
        2_000_000,
        1_500_000_000,
    )

    for contract in (adapter, nr_adapter, oo):
        for fn_name in ("proposePrice", "disputePrice", "settle", "resolve"):
            fn = getattr(contract.functions, fn_name, MagicMock())
            fn.return_value.build_transaction.return_value = {"data": "0x"}

    return adapter, nr_adapter, oo, usdc


def test_uma_requires_private_key(client: PolymarketPandas):
    with pytest.raises(PolymarketAuthError, match="private_key"):
        client.propose_price(STUB_QUESTION_ID, 10**18)


def test_uma_invalid_proposed_price(ctf_client: PolymarketPandas, monkeypatch):
    _mock_uma(ctf_client, monkeypatch)
    with pytest.raises(ValueError, match="Invalid proposed price"):
        ctf_client.propose_price(STUB_QUESTION_ID, 42)


def test_uma_get_uma_state_decodes_enum(ctf_client: PolymarketPandas, monkeypatch):
    _mock_uma(ctf_client, monkeypatch, state_idx=2)
    assert ctf_client.get_uma_state(STUB_QUESTION_ID) == "Proposed"


def test_uma_propose_price_happy(ctf_client: PolymarketPandas, monkeypatch):
    from polymarket_pandas.mixins._uma import (
        OPTIMISTIC_ORACLE_V2,
        UMA_CTF_ADAPTER,
        YES_OR_NO_IDENTIFIER,
    )

    adapter, nr_adapter, oo, usdc = _mock_uma(ctf_client, monkeypatch, state_idx=1)
    ctf_client.propose_price(STUB_QUESTION_ID, 10**18)

    oo.functions.proposePrice.assert_called_once()
    args = oo.functions.proposePrice.call_args[0]
    assert args[0] == UMA_CTF_ADAPTER
    assert args[1] == YES_OR_NO_IDENTIFIER
    assert args[2] == 1_700_000_000
    assert args[4] == 10**18

    usdc.functions.approve.assert_called_once()
    approve_args = usdc.functions.approve.call_args[0]
    assert approve_args[0] == OPTIMISTIC_ORACLE_V2
    nr_adapter.functions.proposePrice.assert_not_called()


def test_uma_propose_price_rejects_bad_state(ctf_client: PolymarketPandas, monkeypatch):
    _mock_uma(ctf_client, monkeypatch, state_idx=2)
    with pytest.raises(ValueError, match="state is 'Proposed'"):
        ctf_client.propose_price(STUB_QUESTION_ID, 10**18)


def test_uma_dispute_approves_bond_only(ctf_client: PolymarketPandas, monkeypatch):
    from polymarket_pandas.mixins._uma import OPTIMISTIC_ORACLE_V2

    _adapter, _nr, oo, usdc = _mock_uma(ctf_client, monkeypatch, state_idx=2)
    ctf_client.dispute_price(STUB_QUESTION_ID)

    oo.functions.disputePrice.assert_called_once()
    usdc.functions.approve.assert_called_once()
    allowance_args = usdc.functions.allowance.call_args[0]
    assert allowance_args[1] == OPTIMISTIC_ORACLE_V2


def test_uma_dispute_rejects_bad_state(ctf_client: PolymarketPandas, monkeypatch):
    _mock_uma(ctf_client, monkeypatch, state_idx=1)
    with pytest.raises(ValueError, match="state is 'Requested'"):
        ctf_client.dispute_price(STUB_QUESTION_ID)


def test_uma_neg_risk_routes_through_nr_adapter(ctf_client: PolymarketPandas, monkeypatch):
    from polymarket_pandas.mixins._uma import NEG_RISK_UMA_CTF_ADAPTER

    _adapter, nr_adapter, oo, _usdc = _mock_uma(ctf_client, monkeypatch, state_idx=1)
    ctf_client.propose_price(STUB_QUESTION_ID, 0, neg_risk=True)

    nr_adapter.functions.getQuestion.assert_called()
    args = oo.functions.proposePrice.call_args[0]
    assert args[0] == NEG_RISK_UMA_CTF_ADAPTER


def test_uma_resolve_market_calls_adapter(ctf_client: PolymarketPandas, monkeypatch):
    adapter, _nr, _oo, _usdc = _mock_uma(ctf_client, monkeypatch)
    ctf_client.resolve_market(STUB_QUESTION_ID)
    adapter.functions.resolve.assert_called_once()


def test_uma_propose_price_estimate(ctf_client: PolymarketPandas, monkeypatch):
    _mock_uma(ctf_client, monkeypatch, state_idx=1)
    ctf_client._w3.eth.get_balance.return_value = 10**18
    out = ctf_client.propose_price(STUB_QUESTION_ID, 10**18, estimate=True)
    ctf_client._w3.eth.send_raw_transaction.assert_not_called()
    assert out["gas"] == 200_000
