# Schemas & Types

`polymarket-pandas` provides pandera `DataFrameModel` schemas for all DataFrame-returning endpoints and `TypedDict` subclasses for all dict-returning endpoints. Both enable IDE autocomplete and type safety with zero runtime overhead.

---

## Pandera DataFrameModels

All schemas use `strict=False` (extra columns allowed) and `coerce=True`, so API changes do not break validation. Schemas are annotation-only by default -- no runtime validation unless you explicitly call `.validate()`.

```python
from polymarket_pandas import MarketSchema, PositionSchema, OrderbookSchema

# Annotation-only -- no runtime validation overhead
markets = client.get_markets()  # DataFrame[MarketSchema]

# Users who want validation:
MarketSchema.validate(markets)
```

### Gamma API Schemas

| Schema | Endpoint(s) |
|---|---|
| `MarketSchema` | `get_markets`, `get_markets_all` |
| `EventSchema` | `get_events`, `get_events_all` |
| `TagSchema` | `get_tags`, `get_market_tags`, `get_event_tags`, `get_related_tags_by_tag_id`, `get_related_tags_by_tag_slug` |
| `SeriesSchema` | `get_series`, `get_series_all` |
| `CommentSchema` | `get_comments`, `get_comments_by_user_address` |
| `SportsMetadataSchema` | `get_sports_metadata` |
| `TeamSchema` | `get_teams`, `get_teams_all` |

### CLOB API Schemas

| Schema | Endpoint(s) |
|---|---|
| `OrderbookSchema` | `get_orderbook`, `get_orderbooks` |
| `ClobTradeSchema` | `get_user_trades` |
| `ActiveOrderSchema` | `get_active_orders` |
| `PriceHistorySchema` | `get_price_history` |
| `MidpointSchema` | `get_midpoints` |
| `MarketPriceSchema` | `get_market_prices` |
| `LastTradePricesSchema` | `get_last_trade_prices` |
| `SendOrderResponseSchema` | `place_orders` (batch response) |
| `SamplingMarketSchema` | `get_sampling_markets` |
| `SimplifiedMarketSchema` | `get_simplified_markets`, `get_sampling_simplified_markets` |
| `BuilderTradeSchema` | `get_builder_trades` |

### Data API Schemas

| Schema | Endpoint(s) |
|---|---|
| `PositionSchema` | `get_positions` |
| `ClosedPositionSchema` | `get_closed_positions` |
| `DataTradeSchema` | `get_trades` |
| `ActivitySchema` | `get_user_activity` |
| `LeaderboardSchema` | `get_leaderboard` |
| `BuilderLeaderboardSchema` | `get_builder_leaderboard` |
| `BuilderVolumeSchema` | `get_builder_volume` |
| `PositionValueSchema` | `get_positions_value` |

### Rewards API Schemas

| Schema | Endpoint(s) |
|---|---|
| `CurrentRewardSchema` | `get_rewards_markets_current` |
| `RewardsMarketMultiSchema` | `get_rewards_markets_multi` |
| `RewardsMarketSchema` | `get_rewards_market` |
| `UserEarningSchema` | `get_rewards_earnings` |
| `UserRewardsMarketSchema` | `get_rewards_user_markets` |
| `RebateSchema` | `get_rebates` |

### Bridge API Schemas

| Schema | Endpoint(s) |
|---|---|
| `BridgeSupportedAssetSchema` | `get_bridge_supported_assets` |
| `BridgeTransactionSchema` | `get_bridge_transaction_status` |

### XTracker API Schemas

| Schema | Endpoint(s) |
|---|---|
| `XTrackerUserSchema` | `get_xtracker_users` |
| `XTrackerPostSchema` | `get_xtracker_user_posts` |
| `XTrackerTrackingSchema` | `get_xtracker_trackings`, `get_xtracker_user_trackings` |
| `XTrackerDailyStatSchema` | `get_xtracker_tracking` (daily stats inside `stats`) |
| `XTrackerMetricSchema` | `get_xtracker_metrics` |

---

## TypedDicts

Structural subtypes of `dict` for dict-returning endpoints. Existing code using `result["key"]` continues to work unchanged.

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

### Cursor-Paginated Pages

All inherit from `CursorPage` base with `next_cursor`, `count`, `limit` keys plus a typed `data` DataFrame.

| TypedDict | Endpoint | Data Schema |
|---|---|---|
| `OrdersCursorPage` | `get_active_orders` | `ActiveOrderSchema` |
| `UserTradesCursorPage` | `get_user_trades` | `ClobTradeSchema` |
| `SamplingMarketsCursorPage` | `get_sampling_markets` | `SamplingMarketSchema` |
| `SimplifiedMarketsCursorPage` | `get_simplified_markets` | `SimplifiedMarketSchema` |
| `BuilderTradesCursorPage` | `get_builder_trades` | `BuilderTradeSchema` |
| `CurrentRewardsCursorPage` | `get_rewards_markets_current` | `CurrentRewardSchema` |
| `RewardsMarketMultiCursorPage` | `get_rewards_markets_multi` | `RewardsMarketMultiSchema` |
| `RewardsMarketCursorPage` | `get_rewards_market` | `RewardsMarketSchema` |
| `UserEarningsCursorPage` | `get_rewards_earnings` | `UserEarningSchema` |
| `UserRewardsMarketsCursorPage` | `get_rewards_user_markets` | `UserRewardsMarketSchema` |

### Other TypedDicts

| TypedDict | Used by |
|---|---|
| `SignedOrder` | `build_order` |
| `SendOrderResponse` | `place_order`, `submit_order` |
| `CancelOrdersResponse` | `cancel_order`, `cancel_orders`, `cancel_all_orders`, `cancel_orders_from_market` |
| `ApiCredentials` | `create_api_key`, `derive_api_key` |
| `BalanceAllowance` | `get_balance_allowance` |
| `TransactionReceipt` | `split_position`, `merge_positions`, `redeem_positions`, `approve_collateral` |
| `LastTradePrice` | `get_last_trade_price` |
| `BridgeAddress` | `create_deposit_address`, `create_withdrawal_address` |
| `BridgeAddressInfo` | Nested in `BridgeAddress` (chain-specific addresses) |
| `RelayPayload` | `get_relay_payload` |
| `SubmitTransactionResponse` | `submit_transaction` |
| `XTrackerUser` | `get_xtracker_user` |
| `XTrackerTracking` | `get_xtracker_tracking` |

### Order Input Schemas

Two pandera `DataFrameModel` schemas for runtime input validation (validated automatically on submission):

| Schema | Used by | Description |
|---|---|---|
| `PlaceOrderSchema` | `place_orders` | Validates signed-order DataFrames (Ethereum address format, amounts, side, signatureType, orderType) |
| `SubmitOrderSchema` | `submit_orders` | Validates unsigned-intent DataFrames (tokenId, price, size, side + optional fields) |
| `OrderSchema` | -- | Backward-compat alias for `PlaceOrderSchema` |
