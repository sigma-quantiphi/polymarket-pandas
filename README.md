# polymarket-pandas

Pandas-native Python client for the full [Polymarket](https://polymarket.com) API surface — REST, WebSocket, Relayer, and Bridge — with automatic type coercion and DataFrame output.

---

## Installation

```bash
pip install polymarket-pandas
# or
uv add polymarket-pandas
```

For on-chain CTF operations (merge, split, redeem positions):

```bash
pip install "polymarket-pandas[ctf]"
```

For the interactive Streamlit explorer dashboard:

```bash
pip install "polymarket-pandas[explorer]"
```

For the MCP server (Claude Code, Claude Desktop, etc.):

```bash
pip install "polymarket-pandas[mcp]"
```

---

## MCP Server

Query Polymarket data from any MCP client with 74 tools covering the full API surface.

```bash
# Run the server (stdio transport)
polymarket-mcp

# SSE transport
polymarket-mcp --sse
```

### Claude Code / Claude Desktop Setup

Add to your MCP settings (`~/.claude/settings.json` or Claude Desktop config):

```json
{
  "mcpServers": {
    "polymarket": {
      "command": "polymarket-mcp"
    }
  }
}
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `POLYMARKET_ADDRESS` | Wallet address for position/trade queries |
| `POLYMARKET_PRIVATE_KEY` | Private key for order signing |
| `POLYMARKET_API_KEY` | L2 API key for private endpoints |
| `POLYMARKET_API_SECRET` | L2 API secret |
| `POLYMARKET_API_PASSPHRASE` | L2 API passphrase |
| `POLYMARKET_MCP_MAX_ROWS` | Default max rows in table output (default 200) |

### Available Tools (74)

**Discovery:** search_markets, get_markets, get_market_by_slug/id, get_events, get_event_by_slug/id, get_tags, get_tag_by_slug/id, get_related_tags, get_market_tags, get_event_tags, get_series, get_series_by_id, get_teams, get_comments, get_comment_by_id, get_comments_by_user, get_profile, get_sports_metadata, get_sports_market_types

**Pricing:** get_orderbook, get_midpoint_price, get_spread, get_last_trade_price, get_tick_size, get_neg_risk, get_fee_rate, get_market_price, get_price_history, get_builder_trades, get_rebates, get_server_time

**Data:** get_positions, get_closed_positions, get_market_positions, get_top_holders, get_positions_value, get_trades, get_user_activity, get_leaderboard, get_builder_leaderboard, get_builder_volume, get_accounting_snapshot, get_open_interest, get_live_volume, get_traded_markets_count

**Rewards:** get_rewards_markets_current, get_rewards_markets_multi, get_rewards_market, get_rewards_earnings, get_rewards_earnings_total, get_rewards_percentages, get_rewards_user_markets

**Private:** get_balance_allowance, get_user_trades, get_active_orders, get_order, get_order_scoring, get_api_keys, send_heartbeat

**Write:** build_order, place_order, cancel_order, cancel_orders, cancel_all_orders, cancel_orders_from_market, create_api_key, derive_api_key, delete_api_key

**Bridge:** get_bridge_supported_assets, get_bridge_transaction_status, get_bridge_quote

---

## Interactive Explorer

Explore all public endpoints visually with the built-in Streamlit dashboard:

```bash
# Install with explorer support
pip install "polymarket-pandas[explorer]"

# Launch the dashboard
polymarket-explore
```

The explorer includes 10 pages covering Markets, Events, Series, Orderbook (depth chart), Prices (history + spot), Positions, Trades, Leaderboard, Rewards, and Bridge. Each page shows the raw DataFrame, an interactive Plotly chart, and the equivalent Python code to reproduce.

---

## Quick Start

```python
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()

# Get active markets
markets = client.get_markets(closed=False, limit=100)
print(markets[["slug", "volume24hr", "endDate"]].head())

# Get the order book for a token
book = client.get_orderbook("15871154585880608648...")
print(book)
```

---

## Configuration

All credentials are read from environment variables (or a `.env` file via `python-dotenv`).
You can also pass them directly as constructor arguments.

| Env var | Constructor kwarg | Purpose |
|---|---|---|
| `POLYMARKET_ADDRESS` | `address` | Your proxy wallet address |
| `POLYMARKET_PRIVATE_KEY` | `private_key` | Private key for EIP-712 (L1) signing |
| `POLYMARKET_FUNDER` | `private_funder_key` | Funder private key |
| `POLYMARKET_API_KEY` | `_api_key` | CLOB API key |
| `POLYMARKET_API_SECRET` | `_api_secret` | CLOB API secret (used for L2 HMAC) |
| `POLYMARKET_API_PASSPHRASE` | `_api_passphrase` | CLOB API passphrase |
| `POLYMARKET_BUILDER_API_KEY` | `_builder_api_key` | Builder API key |
| `POLYMARKET_BUILDER_API_SECRET` | `_builder_api_secret` | Builder API secret |
| `POLYMARKET_BUILDER_API_PASSPHRASE` | `_builder_api_passphrase` | Builder API passphrase |
| `POLYMARKET_RELAYER_API_KEY` | `_relayer_api_key` | Relayer API key |
| `POLYMARKET_RELAYER_API_KEY_ADDRESS` | `_relayer_api_key_address` | Address owning the relayer key |
| `POLYMARKET_RPC_URL` | `rpc_url` | Polygon RPC URL (default: `https://polygon-rpc.com`) |
| `HTTP_PROXY` | `proxy_url` | HTTP proxy URL |

```python
# Explicit credentials
client = PolymarketPandas(
    address="0xYourAddress",
    private_key="0xYourKey",
    _api_key="your-api-key",
    _api_secret="your-secret",
    _api_passphrase="your-passphrase",
)
```

### API Key setup

```python
# Step 1 — derive or create CLOB API credentials from your wallet key
creds = client.derive_api_key()   # uses private_key from env
# creds = client.create_api_key()  # creates a new key

# Step 2 — set credentials on the client
client._api_key = creds["apiKey"]
client._api_secret = creds["secret"]
client._api_passphrase = creds["passphrase"]
```

---

## DataFrames and type coercion

Every method that returns a list of objects returns a preprocessed `pd.DataFrame`:

- Numeric columns → `float64`
- ISO-8601 string timestamps → `datetime64[ns, UTC]`
- Unix-ms integer timestamps → `datetime64[ns, UTC]`
- Boolean-ish string columns → `bool`
- JSON-encoded string columns (`clobTokenIds`, `outcomes`, `outcomePrices`) → Python objects

Raw `dict` returns are used only where a single object is expected (e.g. `get_market_by_id`).

### Typed returns

All dict-returning endpoints use **TypedDicts** for IDE autocomplete and type safety:

```python
from polymarket_pandas import (
    SamplingMarketsCursorPage, OrdersCursorPage,
    SignedOrder, SendOrderResponse, TransactionReceipt,
)

# Every cursor-paginated endpoint has a specific type with typed data
page = client.get_sampling_markets()   # SamplingMarketsCursorPage
page["data"]         # DataFrame[SamplingMarketSchema] — IDE knows columns
page["next_cursor"]  # str

orders = client.get_active_orders()    # OrdersCursorPage
orders["data"]       # DataFrame[ActiveOrderSchema]

order: SignedOrder = client.build_order(token_id, 0.55, 10, "BUY")
order["makerAmount"]  # str — IDE knows all 13 fields
```

All DataFrame-returning endpoints use **pandera DataFrameModels** (22 schemas) for column documentation:

```python
from polymarket_pandas import MarketSchema, PositionSchema, OrderbookSchema

# Annotation-only — no runtime validation overhead
markets = client.get_markets()  # DataFrame[MarketSchema]
# Users who want validation: MarketSchema.validate(markets)
```

All schemas use `strict=False` (extra columns allowed) so API changes don't break validation.
Field names verified against the official Polymarket OpenAPI specs. All 11 cursor-paginated
endpoints have specific CursorPage types (e.g. `OrdersCursorPage`, `UserTradesCursorPage`)
that inherit from a `CursorPage` base and specify `data: DataFrame[Schema]`.

### Title parsers (`polymarket_pandas.parsers`)

Polymarket exposes bracket bounds, directional thresholds, and sports
spread/total lines only as free-text inside `marketsGroupItemTitle`
("280-299", "↑ 200,000", "Spread -1.5", "O/U 8.5"). The `parsers` module
ships vectorized regex extractors that turn those strings into structured
columns:

```python
from polymarket_pandas import (
    PolymarketPandas,
    classify_event_structure,
    parse_title_bounds,
    parse_title_sports,
    coalesce_end_date_from_title,
)

client = PolymarketPandas()
df = client.get_events(closed=False, limit=300, expand_markets=True)

df = pd.concat([df, parse_title_bounds(df), parse_title_sports(df)], axis=1)
df["structure"] = classify_event_structure(df)        # 5 event-shape labels
df["marketsEndDate"] = coalesce_end_date_from_title(df)  # fill NaT from title
```

| Function | Adds columns |
|---|---|
| `classify_event_structure` | one of `Single-Outcome`, `negRisk Multi-Outcome`, `Non-negRisk Multi-Outcome`, `Directional / Counter-Based`, `Bracketed` |
| `parse_title_bounds` | `boundLow`, `boundHigh`, `direction`, `threshold` |
| `parse_title_sports` | `spreadLine`, `totalLine`, `side` |
| `coalesce_end_date_from_title` | fills NaT in `marketsEndDate` by parsing "Month Day" titles, inferring the year from `marketsStartDate` (with Dec→Jan rollover) |

All parsers default to the `markets`-prefixed column names produced by
`get_events(expand_markets=True)`. Pass the unprefixed equivalents
(`title_col="groupItemTitle"`, etc.) to use them on raw `get_markets`
output. See `examples/market_structures.py` for an end-to-end demo
covering all 10 event shapes (5 core + BTC up/down + 4 sports market
types).

---

## REST API Reference

### Gamma API — Markets

#### `get_markets(**kwargs) → pd.DataFrame`

List markets with rich filtering.

```python
df = client.get_markets(
    limit=500,                  # rows per page (default 500)
    offset=0,
    closed=False,               # exclude resolved markets
    tag_id=1337,
    liquidity_num_min=1000,
    end_date_min="2025-01-01",
    expand_clob_token_ids=True, # explode multi-outcome markets (default True)
    expand_events=True,         # inline event columns (default True)
    expand_series=True,         # inline series columns (default True)
)
```

<details>
<summary>Full parameter list</summary>

| Parameter | Type | Description |
|---|---|---|
| `limit` | int | Rows per page (default 500) |
| `offset` | int | Pagination offset |
| `order` | list[str] | Fields to sort by |
| `ascending` | bool | Sort direction |
| `id` | list[int] | Filter by gamma market IDs |
| `slug` | list[str] | Filter by slugs |
| `clob_token_ids` | list[str] | Filter by CLOB token IDs |
| `condition_ids` | list[str] | Filter by condition IDs |
| `market_maker_address` | list[str] | Filter by market maker |
| `liquidity_num_min/max` | float | Liquidity range filter |
| `volume_num_min/max` | float | Volume range filter |
| `start_date_min/max` | str\|Timestamp | Start date range |
| `end_date_min/max` | str\|Timestamp | End date range |
| `tag_id` | int | Filter by tag |
| `related_tags` | bool | Include related tags |
| `cyom` | bool | CYOM markets only |
| `uma_resolution_status` | str | UMA resolution filter |
| `game_id` | str | Sports game ID |
| `sports_market_types` | list[str] | Sports market types |
| `rewards_min_size` | float | Minimum reward size |
| `question_ids` | list[str] | Filter by question IDs |
| `closed` | bool | Include/exclude closed markets |
| `expand_clob_token_ids` | bool | Explode multi-outcome rows (default True) |
| `expand_events` | bool | Inline event fields (default True) |
| `expand_series` | bool | Inline series fields (default True) |

</details>

#### `get_markets_all(**kwargs) → pd.DataFrame`

Auto-paginate through all matching markets.

```python
all_markets = client.get_markets_all(closed=False)
```

#### `get_market_by_id(id, include_tag=None) → dict`

```python
market = client.get_market_by_id(12345)
```

#### `get_market_by_slug(slug, include_tag=None) → dict`

```python
market = client.get_market_by_slug("will-trump-win-2024")
```

#### `get_market_tags(id) → pd.DataFrame`

```python
tags = client.get_market_tags(12345)
```

---

### Gamma API — Sampling / Simplified Markets (CLOB)

These three endpoints are served by the CLOB server and use **cursor-based pagination**.
Each method returns a `dict` with keys `data` (DataFrame), `next_cursor`, `count`, `limit`.
The corresponding `_all()` variants auto-paginate.

#### `get_sampling_markets(next_cursor=None) → dict`

Markets currently eligible for liquidity-provider rewards. Full market objects including
`tokens`, `rewards`, `minimum_tick_size`, etc.

```python
page = client.get_sampling_markets()
df   = page["data"]
# fetch next page
page2 = client.get_sampling_markets(next_cursor=page["next_cursor"])
```

#### `get_simplified_markets(next_cursor=None) → dict`

Lightweight snapshot of all CLOB markets: `condition_id`, `tokens` (price/outcome),
`rewards`, `active`, `closed`, `archived`, `accepting_orders`.

```python
page = client.get_simplified_markets()
# auto-page all
all_simplified = client.get_simplified_markets_all()
```

#### `get_sampling_simplified_markets(next_cursor=None) → dict`

Intersection of sampling and simplified — lightest payload for reward-eligible markets.

```python
all_sampling = client.get_sampling_simplified_markets_all()
```

---

### Gamma API — Events

#### `get_events(**kwargs) → pd.DataFrame`

```python
events = client.get_events(
    closed=False,
    tag_id=1337,
    limit=300,
    expand_markets=True,            # inline market columns (default True)
    expand_clob_token_ids=True,     # explode token rows (default True)
)
```

#### `get_events_all(**kwargs) → pd.DataFrame`

Auto-paginate all matching events.

#### `get_event_by_id(id, include_chat=None, include_template=None) → dict`

#### `get_event_by_slug(slug, ...) → dict`

#### `get_event_tags(id) → pd.DataFrame`

---

### Gamma API — Tags

#### `get_tags(**kwargs) → pd.DataFrame`

```python
tags = client.get_tags(limit=300)
```

#### `get_tags_all(**kwargs) → pd.DataFrame`

#### `get_tag_by_id(id, include_template=None) → dict`

#### `get_tag_by_slug(slug, include_template=None) → dict`

#### `get_related_tags_by_tag_id(id, omit_empty=None, status=None) → pd.DataFrame`

#### `get_related_tags_by_tag_slug(slug, omit_empty=None, status=None) → pd.DataFrame`

---

### Gamma API — Series

#### `get_series(**kwargs) → pd.DataFrame`

```python
series = client.get_series(
    closed=False,
    expand_events=True,
    expand_event_tags=False,
)
```

#### `get_series_all(**kwargs) → pd.DataFrame`

Auto-paginate all matching series. Works with `expand_events=True`.

#### `get_series_by_id(id, include_chat=None) → dict`

---

### Gamma API — Sports

#### `get_sports_metadata(**kwargs) → pd.DataFrame`

```python
meta = client.get_sports_metadata(sport="NFL")
```

#### `get_sports_market_types() → dict`

#### `get_teams(**kwargs) → pd.DataFrame`

```python
teams = client.get_teams(league=["NFL", "NBA"])
```

#### `get_teams_all(**kwargs) → pd.DataFrame`

#### `fetch_sports_event(sports_market_type, **kwargs) → pd.DataFrame`

Convenience method that bridges `get_markets(sports_market_types=[...])` and
`get_events(slug=[...], expand_markets=True)`. Sports events are usually
"More Markets" bundles mixing moneyline + spreads + totals + props at the
same parent event id; this picks one event and slices it down to just the
markets of the requested type using `conditionId` as the join key.

```python
spreads = client.fetch_sports_event("spreads")          # MLB / NBA spread lines
totals  = client.fetch_sports_event("totals")           # over/under lines
btts    = client.fetch_sports_event("both_teams_to_score")
ml      = client.fetch_sports_event("moneyline")
```

See `get_sports_market_types()` for the full list of valid type names.
The discovery filters mirror `get_markets` (`closed`, `start_date_min/max`,
`liquidity_num_min/max`, `tag_id`, `order`, `ascending`, `limit`, ...).

---

### Gamma API — Comments

#### `get_comments(**kwargs) → pd.DataFrame`

```python
comments = client.get_comments(
    parent_entity_type="Event",
    parent_entity_id=12345,
    limit=100,
)
```

#### `get_comments_all(**kwargs) → pd.DataFrame`

#### `get_comments_by_user_address(user_address, **kwargs) → pd.DataFrame`

#### `get_comments_by_user_address_all(user_address, **kwargs) → pd.DataFrame`

#### `get_comment_by_id(id, get_positions=None) → dict`

---

### Gamma API — Search

#### `search_markets_events_profiles(q, **kwargs) → dict`

```python
results = client.search_markets_events_profiles("bitcoin", limit_per_type=10)
# results keys: "markets", "events", "profiles"
```

---

### Gamma API — Profiles

#### `get_profile(address) → dict`

```python
profile = client.get_profile("0xYourAddress")
```

---

### Data API — Positions & Trades

#### `get_positions(user, **kwargs) → pd.DataFrame`

```python
positions = client.get_positions(
    user="0xYourAddress",
    sizeThreshold=1,
    redeemable=False,
    limit=100,
    sortBy="TOKENS",
    sortDirection="DESC",
)
```

#### `get_closed_positions(user, **kwargs) → pd.DataFrame`

```python
closed = client.get_closed_positions(
    user="0xYourAddress",
    sortBy="REALIZEDPNL",
    limit=50,
)
```

#### `get_market_positions(market, **kwargs) → pd.DataFrame`

All positions for a market, across traders.

```python
pos = client.get_market_positions(
    market="0xConditionId...",
    status="OPEN",
    sortBy="TOTAL_PNL",
    limit=50,
)
```

#### `get_positions_all(user, **kwargs) → pd.DataFrame`

#### `get_closed_positions_all(user, **kwargs) → pd.DataFrame`

#### `get_market_positions_all(market, **kwargs) → pd.DataFrame`

#### `get_top_holders(market, limit=100, minBalance=1) → pd.DataFrame`

```python
holders = client.get_top_holders(market=["0xConditionId..."])
```

#### `get_positions_value(user, market=None) → pd.DataFrame`

#### `get_leaderboard(**kwargs) → pd.DataFrame`

#### `get_leaderboard_all(**kwargs) → pd.DataFrame`

```python
lb = client.get_leaderboard(
    category="CRYPTO",
    timePeriod="WEEK",
    orderBy="PNL",
    limit=25,
)
```

#### `get_trades(**kwargs) → pd.DataFrame`

#### `get_trades_all(**kwargs) → pd.DataFrame`

```python
trades = client.get_trades(
    user="0xYourAddress",
    market=["0xConditionId..."],
    limit=100,
)
```

#### `get_user_activity(user, **kwargs) → pd.DataFrame`

#### `get_user_activity_all(user, **kwargs) → pd.DataFrame`

```python
activity = client.get_user_activity(
    user="0xYourAddress",
    type=["TRADE", "REDEEM"],
    limit=100,
)
```

---

### Data API — Misc

#### `get_accounting_snapshot(user) → dict[str, pd.DataFrame]`

Downloads and parses the ZIP accounting snapshot.

```python
snapshot = client.get_accounting_snapshot("0xYourAddress")
positions_df = snapshot["positions"]
equity_df    = snapshot["equity"]
```

#### `get_live_volume(id) → dict`

```python
vol = client.get_live_volume(id=12345)
```

#### `get_open_interest(market=None) → dict`

```python
oi = client.get_open_interest(market=["0xConditionId..."])
```

#### `get_traded_markets_count(user) → dict`

```python
count = client.get_traded_markets_count("0xYourAddress")
```

---

### Data API — Builders

#### `get_builder_leaderboard(timePeriod="DAY", limit=25, offset=0) → pd.DataFrame`

#### `get_builder_leaderboard_all(**kwargs) → pd.DataFrame`

```python
lb = client.get_builder_leaderboard(timePeriod="WEEK")
```

#### `get_builder_volume(timePeriod="DAY") → pd.DataFrame`

```python
vol = client.get_builder_volume(timePeriod="ALL")
```

---

### CLOB API — Market Data (public)

#### `get_server_time() → int`

#### `get_tick_size(token_id) → float`

#### `get_neg_risk(token_id) → bool`

#### `get_fee_rate(token_id=None) → int`

Returns the base fee in basis points.

#### `get_orderbook(token_id) → pd.DataFrame`

```python
book = client.get_orderbook("15871154585880...")
# columns: price, size, side (bids/asks), asset_id, hash, market, ...
```

#### `get_orderbooks(data) → pd.DataFrame`

POST endpoint — `data` is a DataFrame with `token_id` and `side` columns.

#### `get_market_price(token_id, side) → float`

```python
price = client.get_market_price("15871...", side="BUY")
```

#### `get_market_prices(token_sides) → pd.DataFrame`

```python
prices = client.get_market_prices([
    {"token_id": "15871...", "side": "BUY"},
    {"token_id": "15871...", "side": "SELL"},
])
```

#### `get_midpoint_price(token_id) → float`

#### `get_midpoints(token_ids) → pd.DataFrame`

```python
mids = client.get_midpoints(["15871...", "99182..."])
```

#### `get_spread(token_id) → float`

#### `get_last_trade_price(token_id) → LastTradePrice`

#### `get_last_trade_prices(data) → pd.DataFrame`

#### `get_price_history(market, **kwargs) → pd.DataFrame`

```python
history = client.get_price_history(
    market="15871...",
    interval="1w",   # "1m", "1w", "1d", "6h", "1h", "max"
    fidelity=60,     # resolution in minutes
)
```

---

### CLOB API — Private (L2 auth required)

All private endpoints use HMAC-SHA256 (`_api_key`, `_api_secret`, `_api_passphrase`).

#### `get_balance_allowance(asset_type, token_id=None) → BalanceAllowance`

```python
# asset_type 0 = USDC collateral, 1 = conditional token
balance = client.get_balance_allowance(asset_type=0)
# balance["balance"], balance["allowances"]
```

#### `get_user_trades(**kwargs) → CursorPage`

Cursor-paginated. Returns `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}`.

```python
page = client.get_user_trades(market="0xConditionId...")
trades = page["data"]
# Auto-paginate all:
all_trades = client.get_user_trades_all(market="0xConditionId...")
```

#### `get_order(order_id) → dict`

#### `get_active_orders(**kwargs) → CursorPage`

Cursor-paginated. Returns `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}`.

```python
page = client.get_active_orders(market="0xConditionId...")
orders = page["data"]
# Auto-paginate all:
all_orders = client.get_active_orders_all(market="0xConditionId...")
```

#### `get_order_scoring(order_id) → bool`

#### `place_order(order, owner, orderType) → SendOrderResponse`

```python
result = client.place_order(
    order=signed_order_dict,
    owner="your-api-key",
    orderType="GTC",   # "GTC", "GTD", "FOK", "FAK"
)
```

#### `place_orders(orders) → pd.DataFrame`

Batch place up to 15 orders. `orders` is a DataFrame with order fields plus
`owner` and `orderType` columns.

#### `cancel_order(order_id) → CancelOrdersResponse`

#### `cancel_orders(order_ids) → CancelOrdersResponse`

```python
result = client.cancel_orders(["order-id-1", "order-id-2"])
# result["canceled"], result["not_canceled"]
```

#### `cancel_all_orders() → CancelOrdersResponse`

#### `cancel_orders_from_market(market=None, asset_id=None) → CancelOrdersResponse`

#### `send_heartbeat() → dict`

Must be called at least every 10 seconds while orders are open to prevent
automatic cancellation.

---

### Order Building & Submission

Build, sign (EIP-712), and place orders. Market parameters (`neg_risk`, `tick_size`,
`fee_rate_bps`) are **auto-fetched** from the CLOB API and cached per `token_id` —
you only need to provide `token_id`, `price`, `size`, and `side`.

Caching: `get_tick_size` uses a 300-second TTL (tick sizes can change mid-market);
`get_neg_risk` and `get_fee_rate` are cached permanently.

#### `build_order(token_id, price, size, side, **kwargs) → SignedOrder`

Build and EIP-712-sign a CLOB order. Returns a typed dict ready for `place_order()`.

```python
order = client.build_order(
    token_id="15871154585880...",
    price=0.55,
    size=10.0,
    side="BUY",
    # All optional — auto-fetched if omitted:
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

#### `submit_order(token_id, price, size, side, order_type="GTC", **kwargs) → SendOrderResponse`

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

#### `submit_orders(orders: pd.DataFrame) → pd.DataFrame`

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
| `token_id` | Yes | — | CLOB token ID |
| `price` | Yes | — | Limit price (0–1) |
| `size` | Yes | — | Number of shares |
| `side` | Yes | — | `"BUY"` or `"SELL"` |
| `order_type` | No | `"GTC"` | `"GTC"`, `"GTD"`, `"FOK"`, `"FAK"` |
| `neg_risk` | No | auto | Fetched from CLOB API |
| `tick_size` | No | auto | Fetched from CLOB API |
| `fee_rate_bps` | No | auto | Fetched from CLOB API |
| `expiration` | No | `0` | Unix timestamp, `pd.Timestamp`, or ISO string (0 = no expiry) |
| `nonce` | No | `0` | Order nonce |

</details>

---

### CLOB API — Builder Trades (builder auth required)

Requires `_builder_api_key`, `_builder_api_secret`, `_builder_api_passphrase`.

#### `get_builder_trades(**kwargs) → dict`

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

### CLOB API — Rebates (public)

#### `get_rebates(date, maker_address) → pd.DataFrame`

```python
rebates = client.get_rebates(
    date="2026-02-27",
    maker_address="0xYourMakerAddress",
)
# columns: date, condition_id, asset_address, maker_address, rebated_fees_usdc
```

---

### CLOB API — API Key Management (L1 auth)

Requires `private_key` (EIP-712 signing).

#### `create_api_key(nonce=0) → ApiCredentials`

#### `derive_api_key(nonce=0) → ApiCredentials`

#### `get_api_keys() → pd.DataFrame`

#### `delete_api_key() → dict`

---

### Relayer API

Base URL: `https://relayer-v2.polymarket.com`

#### `check_safe_deployed(address) → bool`

```python
deployed = client.check_safe_deployed("0xProxyAddress")
```

#### `get_relayer_transaction(id) → list[dict]`

```python
txs = client.get_relayer_transaction("0190b317-a1d3-7bec-9b91-eeb6dcd3a620")
```

Each transaction has: `transactionID`, `transactionHash`, `from`, `to`,
`proxyAddress`, `data`, `nonce`, `value`, `signature`,
`state` (`STATE_NEW` | `STATE_EXECUTED` | `STATE_MINED` | `STATE_CONFIRMED` | `STATE_INVALID` | `STATE_FAILED`),
`type` (`SAFE` | `PROXY`), `owner`, `metadata`, `createdAt`, `updatedAt`.

#### `get_relayer_nonce(address, type) → str`

```python
nonce = client.get_relayer_nonce("0xSignerAddress", type="PROXY")
```

#### `get_relayer_transactions() → pd.DataFrame`

Requires relayer credentials. Returns recent transactions for the authenticated account.

#### `get_relay_payload(address, type) → RelayPayload`

Returns `{"address": "<relayer_address>", "nonce": "<nonce>"}` — needed to
construct a transaction before signing.

```python
payload = client.get_relay_payload("0xSignerAddress", type="PROXY")
```

#### `submit_transaction(...) → SubmitTransactionResponse`

```python
result = client.submit_transaction(
    from_="0xSignerAddress",
    to="0xContractAddress",
    proxy_wallet="0xProxyWallet",
    data="0xEncodedCalldata",
    nonce="31",
    signature="0xSignatureHex",
    type="PROXY",
    signature_params={
        "gasPrice": "100000000000",
        "operation": "0",
        "safeTxnGas": "0",
        "baseGas": "0",
        "gasToken": "0x0000000000000000000000000000000000000000",
        "refundReceiver": "0x0000000000000000000000000000000000000000",
    },
)
# result: {"transactionID": str, "transactionHash": str, "state": str}
```

---

### Relayer API Keys

Requires `_relayer_api_key` and `_relayer_api_key_address`.

#### `get_relayer_api_keys() → pd.DataFrame`

```python
keys = client.get_relayer_api_keys()
# columns: apiKey, address, createdAt, updatedAt
```

---

### Bridge API

Base URL: `https://bridge.polymarket.com`

#### `get_bridge_supported_assets() → list[dict]`

```python
assets = client.get_bridge_supported_assets()
# Each item: {chainId, chainName, token: {name, symbol, address, decimals}, minCheckoutUsd}
```

#### `get_bridge_quote(...) → dict`

Get a price estimate before bridging.

```python
quote = client.get_bridge_quote(
    from_amount_base_unit="1000000",        # 1 USDC (6 decimals)
    from_chain_id="1",                      # Ethereum
    from_token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    recipient_address="0xYourPolymarketWallet",
    to_chain_id="137",                      # Polygon
    to_token_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
)
# quote keys: quoteId, estCheckoutTimeMs, estInputUsd, estOutputUsd,
#             estToTokenBaseUnit, estFeeBreakdown (appFeeUsd, gasUsd, ...)
```

#### `create_deposit_address(address) → BridgeAddress`

Create multi-chain deposit addresses. Send funds to the returned address to
have USDC.e credited to your Polymarket wallet.

```python
result = client.create_deposit_address("0xYourPolymarketWallet")
# result: {"address": {"evm": "0x...", "svm": "...", "btc": "bc1q..."}, "note": "..."}
```

#### `create_withdrawal_address(address, to_chain_id, to_token_address, recipient_addr) → BridgeAddress`

Bridge funds out of Polymarket to another chain.

```python
result = client.create_withdrawal_address(
    address="0xYourPolymarketWallet",
    to_chain_id="1",                    # Ethereum mainnet
    to_token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    recipient_addr="0xRecipientOnEthereum",
)
```

#### `get_bridge_transaction_status(address) → pd.DataFrame`

Poll for transaction status using an address returned by deposit/withdraw.

```python
status = client.get_bridge_transaction_status("0xDepositAddress...")
# columns: fromChainId, fromTokenAddress, fromAmountBaseUnit,
#          toChainId, toTokenAddress, status, txHash, createdTimeMs
# status values: DEPOSIT_DETECTED | PROCESSING | ORIGIN_TX_CONFIRMED |
#                SUBMITTED | COMPLETED | FAILED
```

---

## CTF — On-Chain Operations

On-chain merge, split, and redeem via Polymarket's Conditional Token Framework
contracts on Polygon. Requires the `[ctf]` extra: `pip install "polymarket-pandas[ctf]"`.

All methods require `private_key` (for signing transactions) and a funded EOA
wallet (MATIC for gas). Amounts are in USDC.e base units (6 decimals):
`1_000_000` = 1.00 USDC.

#### `split_position(condition_id, amount, neg_risk=False, wait=True, timeout=120) → TransactionReceipt`

Split USDC.e collateral into Yes + No outcome tokens.

```python
result = client.split_position(
    condition_id="0x4aee6d11...",
    amount=1_000_000,       # 1.00 USDC
    neg_risk=False,         # True for neg-risk (multi-outcome) markets
)
# result: {"txHash": "0x...", "status": 1, "blockNumber": 12345, "gasUsed": 150000}
```

#### `merge_positions(condition_id, amount, neg_risk=False, wait=True, timeout=120) → TransactionReceipt`

Merge equal amounts of Yes + No tokens back into USDC.e.

```python
result = client.merge_positions(
    condition_id="0x4aee6d11...",
    amount=1_000_000,
)
```

#### `redeem_positions(condition_id, index_sets=None, wait=True, timeout=120) → TransactionReceipt`

Redeem winning outcome tokens for USDC.e after market resolution.

```python
result = client.redeem_positions(condition_id="0x4aee6d11...")
```

#### `approve_collateral(spender=None, amount=None, wait=True, timeout=120) → TransactionReceipt`

Approve a CTF contract to spend USDC.e. Required before `split_position` or
`merge_positions`. Defaults to unlimited approval for the ConditionalTokens contract.

```python
from polymarket_pandas.mixins._ctf import CONDITIONAL_TOKENS, NEG_RISK_ADAPTER

# For standard binary markets
client.approve_collateral(spender=CONDITIONAL_TOKENS)

# For neg-risk markets
client.approve_collateral(spender=NEG_RISK_ADAPTER)
```

---

## WebSocket API

```python
from polymarket_pandas import PolymarketWebSocket, PolymarketPandas

ws = PolymarketWebSocket()
# Or share config with an existing HTTP client:
# ws = PolymarketWebSocket.from_client(client)
```

### Market Channel

Real-time order book, price, and trade updates for one or more tokens.

```python
def on_book(df):
    print("Book update:", df[["price", "size", "side"]])

def on_price_change(df):
    print("Price change:", df[["price", "size"]])

def on_best_bid_ask(df):
    print("BBA:", df[["best_bid", "best_ask"]])

session = ws.market_channel(
    asset_ids=["15871154585880..."],
    on_book=on_book,
    on_price_change=on_price_change,
    on_best_bid_ask=on_best_bid_ask,
    # on_last_trade_price=...,
    # on_tick_size_change=...,
    # on_new_market=...,
    # on_market_resolved=...,
    # on_message=lambda event_type, payload: ...,  # catch-all
    ping_interval=10,
)
session.run_forever()
```

Subscribe / unsubscribe additional tokens after connection:

```python
session.subscribe(["99182..."])
session.unsubscribe(["15871..."])
```

### User Channel

Private order and trade events. Requires API key credentials.

```python
ws = PolymarketWebSocket(
    api_key="your-key",
    api_secret="your-secret",
    api_passphrase="your-passphrase",
)

def on_trade(df):
    print("Trade:", df)

def on_order(df):
    print("Order update:", df)

session = ws.user_channel(
    markets=["0xConditionId..."],
    on_trade=on_trade,
    on_order=on_order,
)
session.run_forever()
```

### Sports Channel

Live sports resolution events.

```python
def on_sport_result(df):
    print("Result:", df)

session = ws.sports_channel(on_sport_result=on_sport_result)
session.run_forever()
```

### RTDS Channel (Real-Time Data Streams)

Crypto prices (Binance and Chainlink) and market comments.

```python
def on_crypto_prices(df):
    print("Binance price:", df[["price"]])

def on_crypto_prices_chainlink(df):
    print("Chainlink price:", df[["price"]])

session = ws.rtds_channel(
    subscriptions=[{"type": "crypto_prices", "condition_id": "0x..."}],
    on_crypto_prices=on_crypto_prices,
    on_crypto_prices_chainlink=on_crypto_prices_chainlink,
    ping_interval=5,
)
session.run_forever()
```

---

## Async Client

`AsyncPolymarketPandas` wraps the sync client, running each method in a thread
pool for non-blocking behavior in asyncio contexts. All 100+ public methods are
available as `async def`.

```python
from polymarket_pandas import AsyncPolymarketPandas

async with AsyncPolymarketPandas() as client:
    markets = await client.get_markets(closed=False, limit=100)
    book = await client.get_orderbook(token_id)
    tick = await client.get_tick_size(token_id)

    # Order building and submission work the same way
    result = await client.submit_order(
        token_id=token_id, price=0.55, size=10, side="BUY"
    )
```

Accepts the same constructor arguments as `PolymarketPandas`, plus
`max_workers` (default 10) for the thread pool size.

---

## Async WebSocket

`AsyncPolymarketWebSocket` uses the `websockets` library for native async I/O
with `async for` iteration and automatic reconnection.

```python
from polymarket_pandas import AsyncPolymarketWebSocket

ws = AsyncPolymarketWebSocket.from_client(client)  # works with sync or async client

session = ws.market_channel(asset_ids=["15871..."])
async with session:
    async for event_type, payload in session:
        if event_type == "book":
            print(payload[["price", "size", "side"]])
        elif event_type == "price_change":
            print(payload)
```

### Features

- **`async for`** iteration over parsed messages
- **Auto-reconnection** with exponential backoff (configurable via `reconnect=True`)
- **Async subscribe/unsubscribe** on live connections
- **Async context manager** (`async with session:`)
- Channels: `market_channel`, `user_channel`, `sports_channel`, `rtds_channel`

```python
# Dynamic subscription management
async with session:
    await session.subscribe(["99182..."])
    await session.unsubscribe(["15871..."])
```

---

## Pagination Helpers

### Offset-based (`_autopage`)

Every offset-paginated endpoint has a corresponding `_all()` method that auto-increments
`offset` and concatenates pages. Works correctly with `expand_*` flags.

```python
# Discovery (Gamma API)
all_markets  = client.get_markets_all(closed=False, expand_events=True)
all_events   = client.get_events_all(closed=False, tag_id=1337)
all_series   = client.get_series_all(expand_events=True)
all_tags     = client.get_tags_all()
all_teams    = client.get_teams_all(league=["NFL"])
all_comments = client.get_comments_all(parent_entity_type="event")

# Data API
all_positions = client.get_positions_all(user="0x...")
all_closed    = client.get_closed_positions_all(user="0x...")
all_mkt_pos   = client.get_market_positions_all(market="0xTokenId...")
all_trades    = client.get_trades_all(market=["0xTokenId..."])
all_activity  = client.get_user_activity_all(user="0x...")
all_lb        = client.get_leaderboard_all(timePeriod="WEEK")
all_builder   = client.get_builder_leaderboard_all()

# Limit pages
first_5 = client.get_markets_all(max_pages=5)
```

### Cursor-based (`_autopage_cursor`)

```python
# Fetch ALL sampling/simplified markets
all_sampling    = client.get_sampling_markets_all()
all_simplified  = client.get_simplified_markets_all()
all_samp_simple = client.get_sampling_simplified_markets_all()

# User trades and active orders (CLOB private, cursor-paginated)
all_trades = client.get_user_trades_all(market="0xConditionId...")
all_orders = client.get_active_orders_all(market="0xConditionId...")

# Rewards
all_rewards = client.get_rewards_markets_current_all()
all_earnings = client.get_rewards_earnings_all(date="2026-03-30")

# Limit pages
first_3 = client.get_simplified_markets_all(max_pages=3)
```

---

## Utility Methods

#### `preprocess_dataframe(data) → pd.DataFrame`

Apply the full type-coercion pipeline to any raw DataFrame.

#### `response_to_dataframe(data) → pd.DataFrame`

`pd.DataFrame(data)` + `preprocess_dataframe`.

#### `orderbook_to_dataframe(data) → pd.DataFrame`

Parse a raw order book dict (with `bids` / `asks` arrays) into a flat DataFrame.

---

## Examples

See the [`examples/`](examples/) directory for runnable scripts:

| Script | Description |
|--------|-------------|
| [`btc_5min.py`](examples/btc_5min.py) | Find BTC 5-min market, fetch orderbook and prices |
| [`btc_5min_trade_merge.py`](examples/btc_5min_trade_merge.py) | Full trading flow: `submit_orders` (DataFrame), cancel, buy both sides, merge positions |
| [`rtds_ws.py`](examples/rtds_ws.py) | Real-Time Data Streams — live crypto prices via WebSocket |
| [`user_ws.py`](examples/user_ws.py) | Private user channel — live order and trade events |

---

## Environment Variables Reference

```dotenv
# Wallet / signing
POLYMARKET_ADDRESS=0xYourProxyWallet
POLYMARKET_PRIVATE_KEY=0xYourPrivateKey
POLYMARKET_FUNDER=0xFunderKey

# CLOB API (L2)
POLYMARKET_API_KEY=your-clob-api-key
POLYMARKET_API_SECRET=your-clob-api-secret
POLYMARKET_API_PASSPHRASE=your-clob-passphrase

# Builder API
POLYMARKET_BUILDER_API_KEY=your-builder-key
POLYMARKET_BUILDER_API_SECRET=your-builder-secret
POLYMARKET_BUILDER_API_PASSPHRASE=your-builder-passphrase

# Relayer API
POLYMARKET_RELAYER_API_KEY=your-relayer-key
POLYMARKET_RELAYER_API_KEY_ADDRESS=0xAddressThatOwnsRelayerKey

# Network
POLYMARKET_RPC_URL=https://polygon-bor-rpc.publicnode.com  # Polygon RPC for CTF ops
HTTP_PROXY=http://proxy:8080                                # HTTP proxy (optional)
```

---

## License

Apache-2.0
