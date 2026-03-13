"""Polymarket-specific exception hierarchy."""
from __future__ import annotations


class PolymarketError(Exception):
    """Base exception for all polymarket-pandas errors."""


class PolymarketAPIError(PolymarketError):
    """Raised when the Polymarket API returns a non-2xx response."""

    def __init__(self, status_code: int, url: str, detail: object) -> None:
        self.status_code = status_code
        self.url = url
        self.detail = detail
        super().__init__(f"HTTP {status_code} from {url}: {detail}")


class PolymarketAuthError(PolymarketAPIError):
    """Raised on 401/403 responses, or when required credentials are missing."""

    def __init__(
        self,
        status_code: int = 0,
        url: str = "",
        detail: object = "",
    ) -> None:
        super().__init__(status_code, url, detail)


class PolymarketRateLimitError(PolymarketAPIError):
    """Raised on 429 Too Many Requests."""
