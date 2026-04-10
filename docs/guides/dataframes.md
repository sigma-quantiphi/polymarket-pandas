# DataFrames & Type Coercion

Every method that returns a list of objects returns a preprocessed `pd.DataFrame` with
automatic type coercion applied. Raw `dict` returns are used only where a single object
is expected (e.g. `get_market_by_id`).

## Type Coercion Pipeline

All DataFrames pass through `preprocess_dataframe` which applies:

| Source type | Target type | Example columns |
|---|---|---|
| Numeric strings | `float64` | `volume`, `liquidity`, `price`, `size`, `umaBond` |
| ISO-8601 datetime strings | `datetime64[ns, UTC]` | `endDate`, `startDate`, `createdAt` |
| Unix-second timestamps (numeric strings >1e9) | `datetime64[ns, UTC]` | `matchTime`, `createdAt` (CLOB) |
| Unix-millisecond integers | `datetime64[ns, UTC]` | `createdTimeMs`, `estCheckoutTimeMs` |
| Boolean-ish strings (`"true"`, `"false"`) | `BooleanDtype` (nullable) | `active`, `closed`, `negRisk`, `live` |
| JSON-encoded strings | Python objects | `clobTokenIds`, `outcomes`, `outcomePrices` |

!!! note
    Boolean columns use pandas nullable `BooleanDtype` so that `NaN` is preserved as `pd.NA`
    rather than being silently converted to `True`.

Additional preprocessing steps:

- Column names are converted from `snake_case` to `camelCase`
- `icon` and `image` columns are dropped by default (configurable via `drop_columns`)

## Typed Returns

### TypedDicts for dict endpoints

All dict-returning endpoints use **TypedDicts** for IDE autocomplete and type safety:

```python
from polymarket_pandas import (
    SamplingMarketsCursorPage, OrdersCursorPage,
    SignedOrder, SendOrderResponse, TransactionReceipt,
)

# Every cursor-paginated endpoint has a specific type with typed data
page = client.get_sampling_markets()   # SamplingMarketsCursorPage
page["data"]         # DataFrame[SamplingMarketSchema] -- IDE knows columns
page["next_cursor"]  # str

orders = client.get_active_orders()    # OrdersCursorPage
orders["data"]       # DataFrame[ActiveOrderSchema]

order: SignedOrder = client.build_order(token_id, 0.55, 10, "BUY")
order["makerAmount"]  # str -- IDE knows all 13 fields
```

### Pandera schemas for DataFrame endpoints

All DataFrame-returning endpoints use **pandera DataFrameModels** for column documentation
and optional runtime validation:

```python
from polymarket_pandas import MarketSchema, PositionSchema, OrderbookSchema

# Annotation-only -- no runtime validation overhead
markets = client.get_markets()  # DataFrame[MarketSchema]

# Users who want validation:
MarketSchema.validate(markets)
```

All schemas use `strict=False` (extra columns allowed) so API changes don't break validation.
Field names are verified against the official Polymarket OpenAPI specs. All 11 cursor-paginated
endpoints have specific CursorPage types (e.g. `OrdersCursorPage`, `UserTradesCursorPage`)
that inherit from a `CursorPage` base and specify `data: DataFrame[Schema]`.

## Nested Expansion

Several `get_*` methods support `expand_*` flags that flatten nested JSON fields into
prefixed columns using `expand_dataframe`:

| Flag | Available on | Adds columns prefixed with |
|---|---|---|
| `expand_events` | `get_markets`, `get_series` | `events` (e.g. `eventsEndDate`, `eventsVolume`) |
| `expand_series` | `get_markets` | `series` (e.g. `seriesTitle`) |
| `expand_markets` | `get_events` | `markets` (e.g. `marketsSlug`, `marketsVolume`) |
| `expand_clob_token_ids` | `get_markets`, `get_events` | Explodes multi-outcome markets into one row per token |
| `expand_outcomes` | `get_markets`, `get_events` | Explodes `outcomes`, `outcomePrices`, `clobTokenIds` into one row per outcome |
| `expand_user` | `get_xtracker_trackings`, `get_xtracker_user_trackings` | `user` (e.g. `userHandle`, `userPlatform`) |
| `expand_trackings` | `get_xtracker_users` | `trackings` (e.g. `trackingsStartDate`) |
| `expand_count` | `get_xtracker_users` | Flattens `_count` dict (e.g. `countPosts`) |

!!! tip
    Expansion flags default to `True` on most methods. Set them to `False` if you want
    the raw nested structure or need faster processing.

After expansion, the type coercion pipeline still applies to all prefixed columns --
`eventsEndDate` is parsed as `datetime64` just like `endDate`. This is handled by
`expand_column_lists` which generates prefixed variants of all known column names.

### Rewards expansion

Rewards endpoints support additional expansion flags:

| Flag | Available on | Effect |
|---|---|---|
| `expand_rewards_config` | `get_rewards_markets_current`, `get_rewards_markets_multi`, `get_rewards_market`, `get_rewards_user_markets` | Flattens nested `rewards_config` list |
| `expand_tokens` | `get_rewards_markets_multi`, `get_rewards_market`, `get_rewards_user_markets` | Flattens nested `tokens` list |
| `expand_earnings` | `get_rewards_user_markets` | Flattens nested `earnings` list |
