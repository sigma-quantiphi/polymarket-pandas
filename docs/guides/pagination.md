# Pagination

polymarket-pandas provides automatic pagination helpers for both offset-based and
cursor-based API endpoints. Every paginated endpoint has a corresponding `_all()` method
that fetches all pages and concatenates the results.

## Offset-Based Pagination

Offset-based endpoints use `_autopage`, which auto-increments `offset` by the number of
records returned per page and stops when a short page is received. Works correctly with
`expand_*` flags (pagination uses the pre-expansion record count).

### Available `_all()` methods

**Discovery (Gamma API):**

```python
all_markets  = client.get_markets_all(closed=False, expand_events=True)
all_events   = client.get_events_all(closed=False, tag_id=1337)
all_series   = client.get_series_all(expand_events=True)
all_tags     = client.get_tags_all()
all_teams    = client.get_teams_all(league=["NFL"])
all_comments = client.get_comments_all(parent_entity_type="event")
```

**Data API:**

```python
all_positions = client.get_positions_all(user="0x...")
all_closed    = client.get_closed_positions_all(user="0x...")
all_mkt_pos   = client.get_market_positions_all(market="0xTokenId...")
all_trades    = client.get_trades_all(market=["0xTokenId..."])
all_activity  = client.get_user_activity_all(user="0x...")
all_lb        = client.get_leaderboard_all(timePeriod="WEEK")
all_builder   = client.get_builder_leaderboard_all()
```

### Limiting pages

Use the `max_pages` parameter to cap the number of pages fetched:

```python
first_5 = client.get_markets_all(max_pages=5)
```

!!! note
    All `_all` methods have explicit parameter signatures matching their base methods
    (minus `offset`) for full IDE autocomplete and type checking.

## Cursor-Based Pagination

Cursor-based endpoints use `_autopage_cursor`, which follows `next_cursor` values until
the sentinel value `"LTE="` is reached or the cursor is empty.

### Single-page methods

Single-page cursor methods return a `CursorPage` dict instead of a bare DataFrame:

```python
page = client.get_sampling_markets()
page["data"]         # pd.DataFrame
page["next_cursor"]  # str -- pass to next call
page["count"]        # int
page["limit"]        # int

# Fetch the next page manually
page2 = client.get_sampling_markets(next_cursor=page["next_cursor"])
```

Each endpoint has a specific CursorPage type (e.g. `SamplingMarketsCursorPage`,
`OrdersCursorPage`, `UserTradesCursorPage`) with `data: DataFrame[Schema]` for
full IDE autocomplete.

### Available `_all()` methods

**CLOB public (cursor-paginated):**

```python
all_sampling    = client.get_sampling_markets_all()
all_simplified  = client.get_simplified_markets_all()
all_samp_simple = client.get_sampling_simplified_markets_all()
```

**CLOB private (cursor-paginated):**

```python
all_trades = client.get_user_trades_all(market="0xConditionId...")
all_orders = client.get_active_orders_all(market="0xConditionId...")
```

**Rewards (cursor-paginated):**

```python
all_rewards  = client.get_rewards_markets_current_all()
all_earnings = client.get_rewards_earnings_all(date="2026-03-30")
```

### Limiting pages

```python
first_3 = client.get_simplified_markets_all(max_pages=3)
```

!!! warning
    Cursor-paginated endpoints like `get_user_trades` and `get_active_orders` require
    L2 HMAC authentication. Make sure your API credentials are configured before calling
    these methods.
