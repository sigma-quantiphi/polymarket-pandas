# Order Building

polymarket-pandas provides a complete order lifecycle: build and EIP-712-sign orders,
submit them individually or in batches, and manage post-only mode and expiration formats.

## `build_order` -- Build and Sign

Build and EIP-712-sign a CLOB order. Returns a `SignedOrder` TypedDict ready for
`place_order()`.

```python
order = client.build_order(
    token_id="15871154585880...",
    price=0.55,
    size=10.0,
    side="BUY",
    # All optional -- auto-fetched if omitted:
    # neg_risk=False,
    # tick_size="0.01",
    # fee_rate_bps=1000,
    # expiration=0,       # 0 = no expiry (GTC)
    # nonce=0,
)
```

## `submit_order` -- Build, Sign, and Place

Build, sign, and place a single order in one call:

```python
result = client.submit_order(
    token_id="15871154585880...",
    price=0.55,
    size=10.0,
    side="BUY",
    order_type="GTC",  # "GTC", "GTD", "FOK", "FAK"
)
# result: {"orderID": "0x...", "status": "matched", "takingAmount": "10", ...}
```

## `submit_orders` -- DataFrame Batch Submission

Build, sign, and batch-submit orders from a DataFrame. Orders are sent in groups
of 15 (the CLOB batch limit) via the `/orders` endpoint.

```python
import pandas as pd

orders_df = pd.DataFrame({
    "token_id": [up_token_id, down_token_id],
    "price": [0.55, 0.45],
    "size": [10, 10],
    "side": ["BUY", "BUY"],
})
responses = client.submit_orders(orders_df)
```

<details>
<summary>DataFrame columns</summary>

| Column | Required | Default | Description |
|--------|----------|---------|-------------|
| `token_id` | Yes | -- | CLOB token ID |
| `price` | Yes | -- | Limit price (0-1) |
| `size` | Yes | -- | Number of shares |
| `side` | Yes | -- | `"BUY"` or `"SELL"` |
| `order_type` | No | `"GTC"` | `"GTC"`, `"GTD"`, `"FOK"`, `"FAK"` |
| `neg_risk` | No | auto | Fetched from CLOB API |
| `tick_size` | No | auto | Fetched from CLOB API |
| `fee_rate_bps` | No | auto | Fetched from CLOB API |
| `expiration` | No | `0` | Unix timestamp, `pd.Timestamp`, or ISO string (0 = no expiry) |
| `nonce` | No | `0` | Order nonce |

</details>

## `place_order` / `place_orders` -- Pre-Signed Orders

For pre-signed orders (from `build_order`), use the lower-level placement methods:

```python
# Single order
result = client.place_order(
    order=signed_order_dict,
    owner="your-api-key",
    orderType="GTC",
)

# Batch (up to 15 orders) -- orders is a DataFrame with order fields
result = client.place_orders(orders_df)
```

!!! warning
    `place_orders` enforces the CLOB API's 15-order-per-call limit. DataFrames with more
    than 15 rows will raise a `ValueError`.

## Post-Only Mode

Post-only orders are rejected if they would immediately fill, ensuring you always provide
liquidity (maker) rather than taking it (taker).

```python
# Single order
result = client.submit_order(
    token_id="15871...", price=0.55, size=10, side="BUY",
    post_only=True,
)

# Batch -- use the postOnly column (camelCase)
orders_df = pd.DataFrame({
    "token_id": [token_id],
    "price": [0.55],
    "size": [10],
    "side": ["BUY"],
    "postOnly": [True],
})
responses = client.submit_orders(orders_df)
```

!!! note
    Post-only mode is only valid with `GTC` or `GTD` order types. Using it with `FOK` or
    `FAK` raises a `ValueError`.

## Expiration Formats

The `expiration` parameter on `build_order` and `submit_order` accepts multiple formats:

| Format | Example | Notes |
|---|---|---|
| `int` | `1735689599` | Unix seconds |
| `pd.Timestamp` | `pd.Timestamp("2025-12-31T23:59:59Z")` | Auto-converted to Unix seconds |
| ISO-8601 `str` | `"2025-12-31T23:59:59Z"` | Auto-converted to Unix seconds |
| `0` | `0` | No expiry (GTC -- good til cancelled) |

```python
# GTD order expiring at a specific time
gtd_order = client.build_order(
    token_id="15871...", price=0.55, size=10, side="BUY",
    expiration=pd.Timestamp("2025-12-31T23:59:59Z"),
)
```

!!! tip
    Naive timestamps (without timezone info) are assumed to be UTC.

## Auto-Fetched Market Parameters

When `neg_risk`, `tick_size`, or `fee_rate_bps` are not provided, they are automatically
fetched from the CLOB API and cached per `token_id`:

| Parameter | Cache | Description |
|---|---|---|
| `tick_size` | 300-second TTL | Minimum price increment (tick sizes can change mid-market) |
| `neg_risk` | Permanent | Whether the market uses neg-risk (multi-outcome) contracts |
| `fee_rate_bps` | Permanent | Base fee in basis points |

This means you typically only need to provide `token_id`, `price`, `size`, and `side`.
