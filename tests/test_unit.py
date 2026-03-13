"""Unit tests — no live API calls, all HTTP interactions mocked via pytest-httpx."""
import pandas as pd
import pytest
from pytest_httpx import HTTPXMock

from polymarket_pandas import (
    PolymarketAPIError,
    PolymarketAuthError,
    PolymarketPandas,
    PolymarketRateLimitError,
)
from polymarket_pandas.utils import (
    expand_column_lists,
    filter_params,
    snake_to_camel,
)

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
    result = filter_params({"end_date_min": ts})
    assert result["end_date_min"].startswith("2025-01-15")


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
    assert result["active"].dtype == bool


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
    httpx_mock.add_response(
        url="https://clob.polymarket.com/time",
        status_code=429,
        json={"error": "rate limited"},
    )
    with pytest.raises(PolymarketRateLimitError) as exc_info:
        client.get_server_time()
    assert exc_info.value.status_code == 429


def test_500_raises_api_error(client: PolymarketPandas, httpx_mock: HTTPXMock):
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


def test_private_endpoint_without_creds_raises_auth_error(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
    with pytest.raises(PolymarketAuthError):
        client.get_active_orders()


def test_private_endpoint_with_creds_calls_api(
    authed_client: PolymarketPandas, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        url="https://clob.polymarket.com/data/orders",
        json=[],
    )
    result = authed_client.get_active_orders()
    assert isinstance(result, pd.DataFrame)


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


def test_get_orderbook_returns_dataframe(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
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


def test_get_markets_returns_dataframe(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
    # expand_* are Python-side flags — not passed as query params
    httpx_mock.add_response(
        url="https://gamma-api.polymarket.com/markets?limit=500",
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


def test_get_sampling_markets_returns_dict(
    client: PolymarketPandas, httpx_mock: HTTPXMock
):
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
