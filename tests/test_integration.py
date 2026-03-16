"""
Integration tests for PolymarketPandas — hit live APIs, no mocking.

Run with:
    pytest tests/test_integration.py -v
"""

import time

import pandas as pd
import pytest

from polymarket_pandas import PolymarketPandas

# ---------------------------------------------------------------------------
# Session-scoped fixtures — expensive API calls run once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client() -> PolymarketPandas:
    return PolymarketPandas(use_tqdm=False)


@pytest.fixture(scope="session")
def crypto_slugs(client: PolymarketPandas) -> list[str]:
    series = client.get_series(expand_events=True, expand_event_tags=True)
    assert isinstance(series, pd.DataFrame)
    assert not series.empty

    active = series.loc[
        (series["eventsEndDate"] >= pd.Timestamp.now(tz="UTC")) & ~series["eventsClosed"]
    ].query("active")
    assert not active.empty, "No active crypto series found — check market data"

    crypto = active.loc[active["slug"].str.contains("btc|eth|sol|xrp|doge")]
    slugs = crypto["eventsSlug"].unique().tolist()[:200]
    assert slugs, "No crypto event slugs found"
    return slugs


@pytest.fixture(scope="session")
def markets(client: PolymarketPandas, crypto_slugs: list[str]) -> pd.DataFrame:
    time.sleep(1)
    df = client.get_markets(slug=crypto_slugs, expand_clob_token_ids=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    return df


@pytest.fixture(scope="session")
def events(client: PolymarketPandas, crypto_slugs: list[str]) -> pd.DataFrame:
    time.sleep(1)
    df = client.get_events(slug=crypto_slugs, expand_markets=True, expand_clob_token_ids=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    return df


@pytest.fixture(scope="session")
def token(markets: pd.DataFrame) -> str:
    return str(markets["clobTokenIds"].iloc[0])


@pytest.fixture(scope="session")
def active_token_ids(events: pd.DataFrame) -> pd.DataFrame:
    active = events.loc[
        (events["marketsStartDate"] <= pd.Timestamp.now(tz="UTC"))
        & ~events["marketsClosed"]
        & events["marketsActive"]
    ]
    return (
        active[["marketsClobTokenIds"]]
        .rename(columns={"marketsClobTokenIds": "token_id"})
        .head(400)
    )


# ---------------------------------------------------------------------------
# Gamma API tests
# ---------------------------------------------------------------------------


def test_get_teams(client: PolymarketPandas) -> None:
    df = client.get_teams()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_sports_metadata(client: PolymarketPandas) -> None:
    df = client.get_sports_metadata()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_tags(client: PolymarketPandas) -> None:
    df = client.get_tags()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "id" in df.columns


def test_get_series_returns_dataframe(client: PolymarketPandas) -> None:
    df = client.get_series(expand_events=True, expand_event_tags=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_markets(markets: pd.DataFrame) -> None:
    assert isinstance(markets, pd.DataFrame)
    assert not markets.empty
    assert "clobTokenIds" in markets.columns


def test_get_events(events: pd.DataFrame) -> None:
    assert isinstance(events, pd.DataFrame)
    assert not events.empty
    assert "marketsClobTokenIds" in events.columns


# ---------------------------------------------------------------------------
# CLOB API — public market data tests
# ---------------------------------------------------------------------------


def test_get_orderbook(client: PolymarketPandas, token: str) -> None:
    df = client.get_orderbook(token_id=token)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "side" in df.columns
    assert set(df["side"].unique()).issubset({"bids", "asks"})


def test_get_orderbooks(client: PolymarketPandas, active_token_ids: pd.DataFrame) -> None:
    df = client.get_orderbooks(data=active_token_ids)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "side" in df.columns


def test_get_market_price(client: PolymarketPandas, token: str) -> None:
    price = client.get_market_price(token_id=token, side="BUY")
    assert isinstance(price, float)
    assert 0.0 <= price <= 1.0


def test_get_bid_ask_spreads(client: PolymarketPandas, markets: pd.DataFrame) -> None:
    data = markets[["clobTokenIds"]].rename(columns={"clobTokenIds": "token_id"}).head(20)
    result = client.get_bid_ask_spreads(data=data)
    assert isinstance(result, dict)
    assert len(result) > 0
    for v in result.values():
        assert isinstance(v, float)


def test_get_midpoint_price(client: PolymarketPandas, token: str) -> None:
    mid = client.get_midpoint_price(token_id=token)
    assert isinstance(mid, float)
    assert 0.0 <= mid <= 1.0


def test_get_multiple_market_prices_by_request(
    client: PolymarketPandas, markets: pd.DataFrame
) -> None:
    data = markets[["clobTokenIds"]].rename(columns={"clobTokenIds": "token_id"}).head(20)
    df = client.get_multiple_market_prices_by_request(data=data)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "tokenId" in df.columns
    assert "side" in df.columns
    assert "price" in df.columns


# ---------------------------------------------------------------------------
# Data API tests
# ---------------------------------------------------------------------------


def test_get_trades(client: PolymarketPandas) -> None:
    df = client.get_trades(limit=10)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
