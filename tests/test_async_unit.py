"""Async unit tests — no live API calls, all HTTP interactions mocked via pytest-httpx."""

import pandas as pd
import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock

from polymarket_pandas import (
    AsyncPolymarketPandas,
    AsyncPolymarketWebSocket,
    AsyncPolymarketWebSocketSession,
    PolymarketAuthError,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """Unauthenticated async client for public-endpoint tests."""
    async with AsyncPolymarketPandas(use_tqdm=False) as c:
        yield c


@pytest_asyncio.fixture
async def authed_client():
    """Async client with stub L2 credentials for private-endpoint tests."""
    import base64

    secret = base64.urlsafe_b64encode(b"test-secret-key-pad-to-32-bytes!").decode()
    async with AsyncPolymarketPandas(
        use_tqdm=False,
        address="0xDEADBEEFdeadbeefDEADBEEFdeadbeef00000000",
        _api_key="test-api-key",
        _api_secret=secret,
        _api_passphrase="test-passphrase",
    ) as c:
        yield c


# ── Test async client basics ────────────────────────────────────────────


async def test_async_client_repr(client: AsyncPolymarketPandas):
    """repr shows Async prefix."""
    assert repr(client).startswith("AsyncPolymarketPandas")


async def test_async_client_has_methods(client: AsyncPolymarketPandas):
    """Async client has all key methods."""
    assert hasattr(client, "get_markets")
    assert hasattr(client, "get_orderbook")
    assert hasattr(client, "submit_order")
    assert hasattr(client, "build_order")


async def test_async_client_properties(authed_client: AsyncPolymarketPandas):
    """Properties delegate to sync client."""
    assert authed_client.address == "0xDEADBEEFdeadbeefDEADBEEFdeadbeef00000000"


# ── Test async HTTP calls ───────────────────────────────────────────────


async def test_async_get_server_time(client: AsyncPolymarketPandas, httpx_mock: HTTPXMock):
    """Async get_server_time returns int."""
    httpx_mock.add_response(json=1700000000)
    result = await client.get_server_time()
    assert result == 1700000000


async def test_async_get_markets(client: AsyncPolymarketPandas, httpx_mock: HTTPXMock):
    """Async get_markets returns DataFrame."""
    httpx_mock.add_response(
        json=[
            {
                "id": 1,
                "slug": "test-market",
                "volume": "1000.5",
                "active": "true",
                "clobTokenIds": '["token1"]',
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.5","0.5"]',
            }
        ],
    )
    df = await client.get_markets(
        limit=1, expand_clob_token_ids=False, expand_events=False, expand_series=False
    )
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "slug" in df.columns


async def test_async_get_orderbook(client: AsyncPolymarketPandas, httpx_mock: HTTPXMock):
    """Async get_orderbook returns DataFrame."""
    httpx_mock.add_response(
        json={
            "market": "0xabc",
            "asset_id": "12345",
            "hash": "0x",
            "timestamp": "1700000000",
            "min_order_size": "1",
            "tick_size": "0.01",
            "neg_risk": False,
            "bids": [{"price": "0.50", "size": "100"}],
            "asks": [{"price": "0.55", "size": "50"}],
        },
    )
    df = await client.get_orderbook("12345")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2


async def test_async_private_requires_auth(client: AsyncPolymarketPandas):
    """Private endpoints raise PolymarketAuthError without credentials."""
    with pytest.raises(PolymarketAuthError):
        await client.get_user_trades()


async def test_async_get_user_trades(authed_client: AsyncPolymarketPandas, httpx_mock: HTTPXMock):
    """Async private endpoint works with credentials."""
    httpx_mock.add_response(
        json={
            "data": [{"id": "trade-1", "side": "BUY", "size": "10", "price": "0.5"}],
            "next_cursor": "LTE=",
            "count": 1,
            "limit": 100,
        },
    )
    result = await authed_client.get_user_trades()
    assert isinstance(result, dict)
    assert isinstance(result["data"], pd.DataFrame)
    assert not result["data"].empty


# ── Test CTF amount_usdc ────────────────────────────────────────────────


def test_ctf_resolve_amount_usdc():
    """_resolve_amount converts USDC float to base units."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    assert CTFMixin._resolve_amount(None, 1.0) == 1_000_000
    assert CTFMixin._resolve_amount(None, 0.5) == 500_000
    assert CTFMixin._resolve_amount(None, 10.0) == 10_000_000


def test_ctf_resolve_amount_base_units():
    """_resolve_amount passes through base units."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    assert CTFMixin._resolve_amount(1_000_000, None) == 1_000_000


def test_ctf_resolve_amount_both_raises():
    """_resolve_amount raises if both amount and amount_usdc given."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    with pytest.raises(ValueError, match="not both"):
        CTFMixin._resolve_amount(1_000_000, 1.0)


def test_ctf_resolve_amount_neither_raises():
    """_resolve_amount raises if neither amount nor amount_usdc given."""
    from polymarket_pandas.mixins._ctf import CTFMixin

    with pytest.raises(ValueError, match="either"):
        CTFMixin._resolve_amount(None, None)


# ── Test async WebSocket ────────────────────────────────────────────────


def test_async_ws_from_client():
    """AsyncPolymarketWebSocket.from_client shares config."""
    from polymarket_pandas import PolymarketPandas

    sync = PolymarketPandas(
        use_tqdm=False,
        _api_key="key",
        _api_secret="secret",
        _api_passphrase="pass",
    )
    ws = AsyncPolymarketWebSocket.from_client(sync)
    assert ws.api_key == "key"
    assert ws.api_secret == "secret"


def test_async_ws_from_async_client():
    """AsyncPolymarketWebSocket.from_client works with async client."""
    async_client = AsyncPolymarketPandas(
        use_tqdm=False,
        _api_key="key",
        _api_secret="secret",
        _api_passphrase="pass",
    )
    ws = AsyncPolymarketWebSocket.from_client(async_client)
    assert ws.api_key == "key"


def test_async_ws_market_channel_returns_session():
    """market_channel returns AsyncPolymarketWebSocketSession."""
    ws = AsyncPolymarketWebSocket()
    session = ws.market_channel(asset_ids=["12345"])
    assert isinstance(session, AsyncPolymarketWebSocketSession)


def test_async_ws_user_channel_requires_creds():
    """user_channel raises without credentials."""
    ws = AsyncPolymarketWebSocket(api_key=None, api_secret=None, api_passphrase=None)
    with pytest.raises(ValueError, match="requires"):
        ws.user_channel(markets=["0xabc"])
