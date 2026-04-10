# Trading

CLOB API endpoints (`clob.polymarket.com`) for market data, order management, and trade execution.

---

## Market Data (Public)

These endpoints require no authentication.

### `get_server_time() -> int`

Get the CLOB server's current Unix timestamp.

### `get_tick_size(token_id) -> float`

Get the minimum tick size for a token. Cached with a 300-second TTL (tick sizes can change mid-market).

### `get_neg_risk(token_id) -> bool`

Check whether a token belongs to a neg-risk (multi-outcome) market. Permanently cached per token.

### `get_fee_rate(token_id=None) -> int`

Returns the base fee in basis points. Permanently cached per token.

### `get_orderbook(token_id) -> pd.DataFrame`

Get the full order book for a token.

```python
book = client.get_orderbook("15871154585880...")
# columns: price, size, side (bids/asks), asset_id, hash, market, ...
```

### `get_orderbooks(data) -> pd.DataFrame`

POST endpoint -- `data` is a DataFrame with `token_id` and `side` columns. Fetches multiple order books in one call.

### `get_market_price(token_id, side) -> float`

Get the best available price for a token on a given side.

```python
price = client.get_market_price("15871...", side="BUY")
```

### `get_market_prices(token_sides) -> pd.DataFrame`

Get prices for multiple token/side pairs.

```python
prices = client.get_market_prices([
    {"token_id": "15871...", "side": "BUY"},
    {"token_id": "15871...", "side": "SELL"},
])
```

### `get_midpoint_price(token_id) -> float`

Get the midpoint price (average of best bid and ask) for a token.

### `get_midpoints(token_ids) -> pd.DataFrame`

Get midpoint prices for multiple tokens.

```python
mids = client.get_midpoints(["15871...", "99182..."])
```

### `get_spread(token_id) -> float`

Get the bid-ask spread for a token.

### `get_last_trade_price(token_id) -> LastTradePrice`

Get the last trade price and side for a token. Returns a `LastTradePrice` TypedDict with `price` and `side` keys.

### `get_last_trade_prices(data) -> pd.DataFrame`

Get last trade prices for multiple tokens via POST.

### `get_price_history(market, **kwargs) -> pd.DataFrame`

Get historical price data for a market.

```python
history = client.get_price_history(
    market="15871...",
    interval="1w",   # "1m", "1w", "1d", "6h", "1h", "max"
    fidelity=60,     # resolution in minutes
)
```

---

## Private Endpoints (L2 Auth Required)

All private endpoints use HMAC-SHA256 authentication (`_api_key`, `_api_secret`, `_api_passphrase`).

### `get_balance_allowance(asset_type, token_id=None) -> BalanceAllowance`

Get balance and allowance for a user's asset.

```python
# asset_type 0 = USDC collateral, 1 = conditional token
balance = client.get_balance_allowance(asset_type=0)
# balance["balance"], balance["allowances"]
```

### `get_user_trades(**kwargs) -> CursorPage`

Cursor-paginated. Returns `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}`.

```python
page = client.get_user_trades(market="0xConditionId...")
trades = page["data"]
# Auto-paginate all:
all_trades = client.get_user_trades_all(market="0xConditionId...")
```

### `get_order(order_id) -> dict`

Fetch a single order by its ID.

### `get_active_orders(**kwargs) -> CursorPage`

Cursor-paginated. Returns `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}`.

```python
page = client.get_active_orders(market="0xConditionId...")
orders = page["data"]
# Auto-paginate all:
all_orders = client.get_active_orders_all(market="0xConditionId...")
```

### `get_order_scoring(order_id) -> bool`

Check whether an order is being scored for rewards.

### `send_heartbeat() -> dict`

Must be called at least every 10 seconds while orders are open to prevent automatic cancellation.

---

## Order Building & Submission

Build, sign (EIP-712), and place orders. Market parameters (`neg_risk`, `tick_size`, `fee_rate_bps`) are auto-fetched from the CLOB API and cached per `token_id` -- you only need to provide `token_id`, `price`, `size`, and `side`.

### `build_order(token_id, price, size, side, **kwargs) -> SignedOrder`

Build and EIP-712-sign a CLOB order. Returns a `SignedOrder` TypedDict ready for `place_order()`.

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

# Expiration accepts int (Unix seconds), pd.Timestamp, or ISO-8601 string:
gtd_order = client.build_order(
    token_id="15871...", price=0.55, size=10, side="BUY",
    expiration=pd.Timestamp("2025-12-31T23:59:59Z"),  # auto-converted to int
)
```

### `submit_order(token_id, price, size, side, order_type="GTC", **kwargs) -> SendOrderResponse`

Build, sign, and place a single order in one call.

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

### `submit_orders(orders: pd.DataFrame) -> pd.DataFrame`

Build, sign, and batch-submit orders from a DataFrame. Orders are sent in groups of 15 (the CLOB batch limit) via the `/orders` endpoint.

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

### `place_order(order, owner, orderType) -> SendOrderResponse`

Place a pre-signed order.

```python
result = client.place_order(
    order=signed_order_dict,
    owner="your-api-key",
    orderType="GTC",   # "GTC", "GTD", "FOK", "FAK"
)
```

### `place_orders(orders) -> pd.DataFrame`

Batch place up to 15 pre-signed orders. `orders` is a DataFrame with order fields plus `owner` and `orderType` columns.

### `cancel_order(order_id) -> CancelOrdersResponse`

Cancel a single order by ID.

### `cancel_orders(order_ids) -> CancelOrdersResponse`

Cancel multiple orders by their IDs.

```python
result = client.cancel_orders(["order-id-1", "order-id-2"])
# result["canceled"], result["not_canceled"]
```

### `cancel_all_orders() -> CancelOrdersResponse`

Cancel all open orders for the authenticated user.

### `cancel_orders_from_market(market=None, asset_id=None) -> CancelOrdersResponse`

Cancel all orders in a specific market or for a specific asset.

---

## Builder Trades (Builder Auth Required)

Requires `_builder_api_key`, `_builder_api_secret`, `_builder_api_passphrase`.

### `get_builder_trades(**kwargs) -> dict`

Returns a cursor-paginated dict (`data` DataFrame + `next_cursor`).

```python
page = client.get_builder_trades(
    builder="0199bfa0-f4c1-7a98-9c2b-b29cc6d39e10",
    market="0xConditionId...",
    after="1700000000",
)
df = page["data"]
# columns: id, tradeType, takerOrderHash, builder, market, assetId,
#          side, size, sizeUsdc, price, status, outcome, fee, matchTime, ...
```

---

## Rebates (Public)

### `get_rebates(date, maker_address) -> pd.DataFrame`

Get rebate information for a maker address on a specific date.

```python
rebates = client.get_rebates(
    date="2026-02-27",
    maker_address="0xYourMakerAddress",
)
# columns: date, condition_id, asset_address, maker_address, rebated_fees_usdc
```

---

## API Key Management (L1 Auth)

Requires `private_key` (EIP-712 signing).

### `create_api_key(nonce=0) -> ApiCredentials`

Create a new CLOB API key. Auto-sets credentials on the client instance.

### `derive_api_key(nonce=0) -> ApiCredentials`

Derive a deterministic CLOB API key from the wallet's private key. Auto-sets credentials on the client instance.

```python
# Step 1 -- derive CLOB API credentials from your wallet key
creds = client.derive_api_key()   # uses private_key from env

# Step 2 -- credentials are auto-set, but you can also set manually:
client._api_key = creds["apiKey"]
client._api_secret = creds["secret"]
client._api_passphrase = creds["passphrase"]
```

### `get_api_keys() -> pd.DataFrame`

List all API keys for the authenticated user.

### `delete_api_key() -> dict`

Delete the current API key.
