# Async Client

`AsyncPolymarketPandas` wraps the sync `PolymarketPandas` client, running each method in a `ThreadPoolExecutor` for non-blocking behavior in asyncio contexts. All 100+ public methods are available as `async def`.

---

## Usage

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

---

## Constructor

Accepts the same constructor arguments as `PolymarketPandas`, plus `max_workers` (default 10) for the thread pool size.

```python
client = AsyncPolymarketPandas(
    address="0xYourAddress",
    private_key="0xYourKey",
    _api_key="your-api-key",
    _api_secret="your-secret",
    _api_passphrase="your-passphrase",
    max_workers=20,  # thread pool size
)
```

---

## How It Works

The async client uses composition rather than inheritance. It creates an internal sync `PolymarketPandas` instance and runs each method in a `ThreadPoolExecutor` via `loop.run_in_executor()`.

All public methods from `PolymarketPandas` are auto-generated as `async def` wrappers at class creation time via `_populate_async_methods()`. This includes all pagination helpers (`_all` methods), order building, WebSocket creation, and property access.

The composition approach avoids rewriting all 77+ mixin methods to be truly async while still providing non-blocking behavior in asyncio applications.

---

## Context Manager

The async client supports the `async with` context manager pattern, which ensures proper cleanup of the thread pool:

```python
async with AsyncPolymarketPandas() as client:
    # client is ready to use
    markets = await client.get_markets()
```

Without the context manager, call `await client.close()` when done to shut down the thread pool.
