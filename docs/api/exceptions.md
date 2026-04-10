# Exceptions

All custom exceptions are importable from the top-level package.

```python
from polymarket_pandas import (
    PolymarketError,
    PolymarketAPIError,
    PolymarketAuthError,
    PolymarketRateLimitError,
)
```

---

## Hierarchy

```
PolymarketError
└── PolymarketAPIError(status_code, url, detail)
    ├── PolymarketAuthError     — 401/403 or missing credentials
    └── PolymarketRateLimitError — 429
```

---

## Exception Classes

### `PolymarketError`

Base exception for all polymarket-pandas errors.

### `PolymarketAPIError`

Raised when the Polymarket API returns a non-2xx response.

**Attributes:**

| Attribute | Type | Description |
|---|---|---|
| `status_code` | int | HTTP status code |
| `url` | str | The request URL |
| `detail` | object | Response body or error detail |

```python
try:
    client.get_orderbook("invalid-token-id")
except PolymarketAPIError as e:
    print(e.status_code)  # 400
    print(e.url)          # https://clob.polymarket.com/book?token_id=...
    print(e.detail)       # error detail from the API
```

### `PolymarketAuthError`

Subclass of `PolymarketAPIError`. Raised in two situations:

1. **HTTP 401/403 responses** -- the API rejected the credentials
2. **Missing credentials** -- `_require_l2_auth()` or `_require_builder_auth()` detected that required credentials are not configured, raising before any network call is made

```python
try:
    client.get_active_orders()
except PolymarketAuthError as e:
    print("Authentication failed:", e)
```

### `PolymarketRateLimitError`

Subclass of `PolymarketAPIError`. Raised on HTTP 429 (Too Many Requests) responses.

```python
try:
    # rapid-fire requests
    for _ in range(1000):
        client.get_midpoint_price(token_id)
except PolymarketRateLimitError:
    print("Rate limited -- back off and retry")
```

---

## Error Mapping

The internal `_handle_response` method maps HTTP status codes to exceptions:

| Status Code | Exception |
|---|---|
| 401, 403 | `PolymarketAuthError` |
| 429 | `PolymarketRateLimitError` |
| Other non-2xx | `PolymarketAPIError` |

The `_extract(data, key)` helper raises `PolymarketAPIError` with context when an expected key is missing from a response dict -- used by scalar-returning endpoints like `get_tick_size`, `get_midpoint_price`, etc.

The XTracker request helper (`_request_xtracker`) also raises `PolymarketAPIError` when the `{success, data, message}` envelope returns `success=false`.
