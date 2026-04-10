# Rewards

CLOB rewards API endpoints (`clob.polymarket.com/rewards/...`) for querying reward configurations, earnings, and percentages.

Cursor-paginated methods return a `CursorPage` dict with keys `data` (DataFrame), `next_cursor` (str), `count` (int), `limit` (int). Pass `next_cursor` from the previous response to fetch the next page. The sentinel value `"LTE="` indicates the last page. All cursor-paginated methods have corresponding `_all()` variants that auto-paginate.

---

## Public Endpoints

### `get_rewards_markets_current(sponsored=None, next_cursor=None, expand_rewards_config=False) -> CurrentRewardsCursorPage`

Get all currently active reward configurations, organized by market. Cursor-paginated.

```python
page = client.get_rewards_markets_current()
df = page["data"]        # DataFrame[CurrentRewardSchema]
cursor = page["next_cursor"]

# Auto-paginate all:
all_rewards = client.get_rewards_markets_current_all()

# Expand nested rewards_config into flat columns:
page = client.get_rewards_markets_current(expand_rewards_config=True)
```

| Parameter | Type | Description |
|---|---|---|
| `sponsored` | bool | If True, returns sponsored reward configurations |
| `next_cursor` | str | Opaque cursor from a previous response |
| `expand_rewards_config` | bool | Flatten nested `rewards_config` list into prefixed columns |

### `get_rewards_markets_multi(**kwargs) -> RewardsMarketMultiCursorPage`

Get active markets with their reward configurations. Supports text search, tag filtering, numeric filters, and sorting. Cursor-paginated.

```python
page = client.get_rewards_markets_multi(
    tag_slug="crypto",
    order_by="rate_per_day",
    position="DESC",
    expand_tokens=True,
)
```

| Parameter | Type | Description |
|---|---|---|
| `q` | str | Text search on market question/description |
| `tag_slug` | str | Filter by tag slug |
| `event_id` | str | Filter by event ID |
| `event_title` | str | Case-insensitive event title search |
| `order_by` | str | Sort field (e.g. `"rate_per_day"`, `"volume_24hr"`, `"spread"`, `"competitiveness"`) |
| `position` | str | Sort direction: `"ASC"` or `"DESC"` |
| `min_volume_24hr` / `max_volume_24hr` | float | 24h volume filter range |
| `min_spread` / `max_spread` | float | Spread filter range |
| `min_price` / `max_price` | float | First-token price filter range |
| `page_size` | int | Items per page (max 500, default 100) |
| `next_cursor` | str | Opaque cursor from a previous response |
| `expand_rewards_config` | bool | Flatten nested `rewards_config` list |
| `expand_tokens` | bool | Flatten nested `tokens` list |

### `get_rewards_market(condition_id, sponsored=None, next_cursor=None, expand_rewards_config=False, expand_tokens=False) -> RewardsMarketCursorPage`

Get reward configurations for a specific market. Cursor-paginated.

```python
page = client.get_rewards_market(
    condition_id="0xConditionId...",
    expand_rewards_config=True,
    expand_tokens=True,
)
```

---

## Private Endpoints (L2 Auth Required)

### `get_rewards_earnings(date, **kwargs) -> UserEarningsCursorPage`

Get per-market user earnings for a specific day. Cursor-paginated.

```python
page = client.get_rewards_earnings(date="2026-03-30")
df = page["data"]  # DataFrame[UserEarningSchema]

# Auto-paginate all:
all_earnings = client.get_rewards_earnings_all(date="2026-03-30")
```

| Parameter | Type | Description |
|---|---|---|
| `date` | str | Target date in `YYYY-MM-DD` format |
| `signature_type` | int | Address derivation type (0=EOA, 1=POLY_PROXY, 2=POLY_GNOSIS_SAFE) |
| `maker_address` | str | Ethereum address to query |
| `sponsored` | bool | If True, filter to sponsored earnings only |
| `next_cursor` | str | Opaque cursor from a previous response |

### `get_rewards_earnings_total(date, **kwargs) -> pd.DataFrame`

Get total earnings for a user on a given day, grouped by asset. Not cursor-paginated.

```python
totals = client.get_rewards_earnings_total(date="2026-03-30")
# columns: date, assetAddress, makerAddress, earnings, assetRate
```

### `get_rewards_percentages(signature_type=None, maker_address=None) -> dict`

Get real-time reward percentages per market for a user. Returns a dict mapping `condition_id` to percentage (float).

```python
pcts = client.get_rewards_percentages()
# {"0xConditionId1": 0.15, "0xConditionId2": 0.08, ...}
```

### `get_rewards_user_markets(**kwargs) -> UserRewardsMarketsCursorPage`

Get user earnings combined with full market configurations. Supports search, filtering, and sorting. Cursor-paginated.

```python
page = client.get_rewards_user_markets(
    date="2026-03-30",
    order_by="earnings",
    position="DESC",
    expand_tokens=True,
    expand_rewards_config=True,
    expand_earnings=True,
)
```

| Parameter | Type | Description |
|---|---|---|
| `date` | str | Target date in `YYYY-MM-DD` format (defaults to today) |
| `q` | str | Text search on market question/description |
| `tag_slug` | str | Filter by tag slug |
| `favorite_markets` | bool | Filter to user-favorited markets only |
| `no_competition` | bool | Filter for markets with no competition |
| `only_mergeable` | bool | Filter for mergeable markets |
| `only_open_orders` | bool | Filter for markets with user's open orders |
| `only_open_positions` | bool | Filter for markets with user's open positions |
| `order_by` | str | Sort field (e.g. `"earnings"`, `"rate_per_day"`, `"earning_percentage"`) |
| `position` | str | Sort direction: `"ASC"` or `"DESC"` |
| `page_size` | int | Items per page (max 500, default 100) |
| `next_cursor` | str | Opaque cursor from a previous response |
| `expand_rewards_config` | bool | Flatten nested `rewards_config` list |
| `expand_tokens` | bool | Flatten nested `tokens` list |
| `expand_earnings` | bool | Flatten nested `earnings` list |
