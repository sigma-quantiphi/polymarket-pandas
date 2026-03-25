"""Shared pytest fixtures for the unit test suite."""

import base64

import pytest

from polymarket_pandas import PolymarketPandas

# Base64-encoded secret for test fixtures (Polymarket API secrets are base64)
_TEST_SECRET = base64.urlsafe_b64encode(b"test-secret-key-pad-to-32-bytes!").decode()


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
        _api_secret=_TEST_SECRET,
        _api_passphrase="test-passphrase",
    )
