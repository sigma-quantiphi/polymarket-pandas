# WebSocket

Real-time streaming via WebSocket connections. Two implementations are available: sync (`PolymarketWebSocket`) and async (`AsyncPolymarketWebSocket`).

---

## Sync WebSocket

Uses `websocket-client` for blocking WebSocket I/O.

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

## Async WebSocket

Uses the `websockets` library for native async I/O with `async for` iteration and automatic reconnection.

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

### Dynamic Subscription Management

```python
async with session:
    await session.subscribe(["99182..."])
    await session.unsubscribe(["15871..."])
```

### Available Channels

Both sync and async WebSocket clients support the same four channels:

| Channel | Description | Auth Required |
|---|---|---|
| `market_channel` | Order book, price, and trade updates | No |
| `user_channel` | Private order and trade events | Yes (API key) |
| `sports_channel` | Live sports resolution events | No |
| `rtds_channel` | Crypto prices and market comments | No |
