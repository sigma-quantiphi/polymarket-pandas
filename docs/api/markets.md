# Markets & Events

Discovery endpoints powered by the Gamma API (`gamma-api.polymarket.com`). All methods are available on `PolymarketPandas` and `AsyncPolymarketPandas`.

---

## Markets

### `get_markets(**kwargs) -> pd.DataFrame`

List markets with rich filtering. Returns a preprocessed DataFrame with automatic type coercion.

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

### `get_markets_all(**kwargs) -> pd.DataFrame`

Auto-paginate through all matching markets. Uses offset-based pagination internally.

```python
all_markets = client.get_markets_all(closed=False)

# Limit the number of pages fetched
first_5 = client.get_markets_all(max_pages=5)
```

### `get_markets_keyset(limit=300, after_cursor=None, **filters) -> MarketsKeysetPage`

Fetch markets using **keyset (cursor) pagination**. Recommended for large scans — stable ordering, up to 1000 rows per page. The endpoint (`GET /markets/keyset`) does not accept `offset`; use `after_cursor` from the previous response instead.

Returns `{"data": DataFrame[MarketSchema], "next_cursor": str | None}`. The server omits `next_cursor` on the final page.

```python
page = client.get_markets_keyset(limit=500, closed=False)
df   = page["data"]

# Manual pagination
cursor = page.get("next_cursor")
while cursor:
    page = client.get_markets_keyset(limit=500, closed=False, after_cursor=cursor)
    # ... process page["data"] ...
    cursor = page.get("next_cursor")
```

See: <https://docs.polymarket.com/api-reference/markets/list-markets-keyset-pagination>

### `get_markets_keyset_all(**kwargs) -> pd.DataFrame`

Auto-paginate through all matching markets via keyset. Prefer this over `get_markets_all` for bulk scans.

```python
all_markets = client.get_markets_keyset_all(closed=False, limit=1000)

# Cap pages
first_3 = client.get_markets_keyset_all(max_pages=3, limit=1000)
```

### `get_market_by_id(id, include_tag=None) -> dict`

Fetch a single market by its numeric Gamma ID.

```python
market = client.get_market_by_id(12345)
```

### `get_market_by_slug(slug, include_tag=None) -> dict`

Fetch a single market by its URL slug.

```python
market = client.get_market_by_slug("will-trump-win-2024")
```

### `get_market_tags(id) -> pd.DataFrame`

Get tags associated with a specific market.

```python
tags = client.get_market_tags(12345)
```

---

## Sampling / Simplified Markets

These three endpoints are served by the CLOB server and use **cursor-based pagination**. Each method returns a `dict` with keys `data` (DataFrame), `next_cursor`, `count`, `limit`. The corresponding `_all()` variants auto-paginate and return a single concatenated DataFrame.

### `get_sampling_markets(next_cursor=None) -> dict`

Markets currently eligible for liquidity-provider rewards. Full market objects including `tokens`, `rewards`, `minimum_tick_size`, etc.

```python
page = client.get_sampling_markets()
df   = page["data"]
# fetch next page
page2 = client.get_sampling_markets(next_cursor=page["next_cursor"])
```

### `get_sampling_markets_all(**kwargs) -> pd.DataFrame`

Auto-paginate all sampling markets.

```python
all_sampling = client.get_sampling_markets_all()
```

### `get_simplified_markets(next_cursor=None) -> dict`

Lightweight snapshot of all CLOB markets: `condition_id`, `tokens` (price/outcome), `rewards`, `active`, `closed`, `archived`, `accepting_orders`.

```python
page = client.get_simplified_markets()
# auto-page all
all_simplified = client.get_simplified_markets_all()
```

### `get_simplified_markets_all(**kwargs) -> pd.DataFrame`

Auto-paginate all simplified markets.

### `get_sampling_simplified_markets(next_cursor=None) -> dict`

Intersection of sampling and simplified -- lightest payload for reward-eligible markets.

```python
all_sampling = client.get_sampling_simplified_markets_all()
```

### `get_sampling_simplified_markets_all(**kwargs) -> pd.DataFrame`

Auto-paginate all sampling simplified markets.

---

## Events

### `get_events(**kwargs) -> pd.DataFrame`

List events with filtering and optional market/tag expansion.

```python
events = client.get_events(
    closed=False,
    tag_id=1337,
    limit=300,
    expand_markets=True,            # inline market columns (default True)
    expand_clob_token_ids=True,     # explode token rows (default True)
)
```

### `get_events_all(**kwargs) -> pd.DataFrame`

Auto-paginate all matching events.

```python
all_events = client.get_events_all(closed=False, tag_id=1337)
```

### `get_event_by_id(id, include_chat=None, include_template=None) -> dict`

Fetch a single event by its numeric ID.

### `get_event_by_slug(slug, ...) -> dict`

Fetch a single event by its URL slug.

### `get_event_tags(id) -> pd.DataFrame`

Get tags associated with a specific event.

---

## Tags

### `get_tags(**kwargs) -> pd.DataFrame`

List all tags.

```python
tags = client.get_tags(limit=300)
```

### `get_tags_all(**kwargs) -> pd.DataFrame`

Auto-paginate all tags.

### `get_tag_by_id(id, include_template=None) -> dict`

Fetch a single tag by its numeric ID.

### `get_tag_by_slug(slug, include_template=None) -> dict`

Fetch a single tag by its URL slug.

### `get_related_tags_by_tag_id(id, omit_empty=None, status=None) -> pd.DataFrame`

Get tags related to a given tag (by numeric ID).

### `get_related_tags_by_tag_slug(slug, omit_empty=None, status=None) -> pd.DataFrame`

Get tags related to a given tag (by slug).

---

## Series

### `get_series(**kwargs) -> pd.DataFrame`

List series with optional event expansion.

```python
series = client.get_series(
    closed=False,
    expand_events=True,
    expand_event_tags=False,
)
```

### `get_series_all(**kwargs) -> pd.DataFrame`

Auto-paginate all matching series. Works with `expand_events=True`.

```python
all_series = client.get_series_all(expand_events=True)
```

### `get_series_by_id(id, include_chat=None) -> dict`

Fetch a single series by its numeric ID.

---

## Sports

### `get_sports_metadata(**kwargs) -> pd.DataFrame`

Get sports metadata (leagues, seasons, etc.).

```python
meta = client.get_sports_metadata(sport="NFL")
```

### `get_sports_market_types() -> dict`

Get the full list of valid sports market type names.

### `get_teams(**kwargs) -> pd.DataFrame`

List teams, optionally filtered by league.

```python
teams = client.get_teams(league=["NFL", "NBA"])
```

### `get_teams_all(**kwargs) -> pd.DataFrame`

Auto-paginate all teams.

```python
all_teams = client.get_teams_all(league=["NFL"])
```

### `fetch_sports_event(sports_market_type, **kwargs) -> pd.DataFrame`

Convenience method that bridges `get_markets(sports_market_types=[...])` and `get_events(slug=[...], expand_markets=True)`. Sports events are usually "More Markets" bundles mixing moneyline + spreads + totals + props at the same parent event id; this picks one event and slices it down to just the markets of the requested type using `conditionId` as the join key.

```python
spreads = client.fetch_sports_event("spreads")          # MLB / NBA spread lines
totals  = client.fetch_sports_event("totals")           # over/under lines
btts    = client.fetch_sports_event("both_teams_to_score")
ml      = client.fetch_sports_event("moneyline")
```

See `get_sports_market_types()` for the full list of valid type names. The discovery filters mirror `get_markets` (`closed`, `start_date_min/max`, `liquidity_num_min/max`, `tag_id`, `order`, `ascending`, `limit`, ...).

---

## Comments

### `get_comments(**kwargs) -> pd.DataFrame`

List comments with filtering.

```python
comments = client.get_comments(
    parent_entity_type="Event",
    parent_entity_id=12345,
    limit=100,
)
```

### `get_comments_all(**kwargs) -> pd.DataFrame`

Auto-paginate all matching comments.

```python
all_comments = client.get_comments_all(parent_entity_type="event")
```

### `get_comments_by_user_address(user_address, **kwargs) -> pd.DataFrame`

List comments by a specific user address.

### `get_comments_by_user_address_all(user_address, **kwargs) -> pd.DataFrame`

Auto-paginate all comments by a specific user address.

### `get_comment_by_id(id, get_positions=None) -> dict`

Fetch a single comment by its ID.

---

## Search

### `search_markets_events_profiles(q, **kwargs) -> dict`

Full-text search across markets, events, and profiles.

```python
results = client.search_markets_events_profiles("bitcoin", limit_per_type=10)
# results keys: "markets", "events", "profiles"
```

---

## Profiles

### `get_profile(address) -> dict`

Fetch a user profile by wallet address.

```python
profile = client.get_profile("0xYourAddress")
```
