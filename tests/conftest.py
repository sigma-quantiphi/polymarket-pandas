"""Shared pytest fixtures for the unit test suite."""
import pytest
from polymarket_pandas import PolymarketPandas


@pytest.fixture
def client() -> PolymarketPandas:
    """Unauthenticated client for public-endpoint tests."""
    return PolymarketPandas(use_tqdm=False)


@pytest.fixture
def authed_client() -> PolymarketPandas:
    """Client with stub L2 credentials for private-endpoint tests."""
    return PolymarketPandas(
        use_tqdm=False,
        address="0xDEADBEEFdeadbeefDEADBEEFdeadbeef00000000",
        _api_key="test-api-key",
        _api_secret="test-secret-key-pad-to-32-bytes!!",
        _api_passphrase="test-passphrase",
    )
