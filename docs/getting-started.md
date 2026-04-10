# Getting Started

This guide walks through the most common workflows in under 5 minutes. No API keys needed for the first four steps — all public endpoints work out of the box.

## Install

=== "pip"

    ```bash
    pip install polymarket-pandas
    ```

=== "uv"

    ```bash
    uv add polymarket-pandas
    ```

## Create a client

```python
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
```

No configuration needed for public endpoints. See [Configuration](guides/configuration.md) for setting up API keys.

## Search markets

```python
# Active markets sorted by 24h volume
markets = client.get_markets(closed=False, order="volume24hr", ascending=False, limit=20)
print(markets[["slug", "question", "volume24hr", "endDate"]])
```

Every method returns a `pd.DataFrame` with parsed datetimes, numeric columns, and camelCase column names.

```python
# Expand nested event and series data into prefixed columns
markets = client.get_markets(
    closed=False,
    expand_events=True,
    expand_series=True,
    limit=50,
)

# Autopaginate all results
all_politics = client.get_markets_all(closed=False, tag_id=15)
```

## Get an orderbook

Extract a token ID from the markets DataFrame and query its orderbook:

```python
token_id = markets["clobTokenIds"].iloc[0]

book = client.get_orderbook(token_id)
print(book[["price", "size", "side"]])

# Scalar helpers
spread = client.get_spread(token_id)       # float
mid = client.get_midpoint_price(token_id)  # float
```

## Price history

```python
prices = client.get_price_history(
    market=token_id,
    interval="1d",
    fidelity=60,  # resolution in minutes
)
# DataFrame with columns: timestamp (datetime), price (float)
prices.plot(x="timestamp", y="price", title="Price History")
```

## Explore positions (requires auth)

Private endpoints need L2 API credentials. Set them via environment variables:

```bash
export POLYMARKET_ADDRESS=0xYourProxyWallet
export POLYMARKET_API_KEY=your-api-key
export POLYMARKET_API_SECRET=your-secret
export POLYMARKET_API_PASSPHRASE=your-passphrase
```

Or derive them from your private key:

```python
client = PolymarketPandas(private_key="0xYourKey")
creds = client.derive_api_key()  # auto-sets L2 credentials
```

Then query your portfolio:

```python
positions = client.get_positions()
trades = client.get_user_trades_all()
```

## Next steps

- [API Reference](api/markets.md) — full method documentation for all 9 API mixins
- [Order Building](guides/order-building.md) — build, sign, and place orders
- [WebSocket Streaming](api/websocket.md) — real-time orderbook and price feeds
- [Interactive Explorer](guides/explorer.md) — Streamlit dashboard with 11 pages
- [Configuration](guides/configuration.md) — all environment variables and auth layers
