# XTracker

XTracker API endpoints (`xtracker.polymarket.com/api/`) for querying the post-tracking service that powers "# tweets / # posts in window" counter markets (e.g. Elon, Trump, Zelenskyy). Covers X (Twitter) and Truth Social platforms.

No authentication required. The `{success, data, message}` envelope is automatically unwrapped; a `PolymarketAPIError` is raised when `success=false`.

---

## User Endpoints

### `get_xtracker_users(platform=None, stats=None, include_inactive=None, expand_trackings=False, expand_count=True) -> pd.DataFrame`

List tracked users on the xtracker service.

```python
users = client.get_xtracker_users(platform="X", stats=True)
```

| Parameter | Type | Description |
|---|---|---|
| `platform` | str | `"X"` or `"TRUTH_SOCIAL"` (None = all platforms) |
| `stats` | bool | When True, include per-user aggregate stats |
| `include_inactive` | bool | When True, include users no longer actively tracked |
| `expand_trackings` | bool | Flatten nested `trackings` list into prefixed columns |
| `expand_count` | bool | Flatten nested `_count` dict into prefixed columns (e.g. `countPosts`). Default True |

### `get_xtracker_user(handle, platform=None) -> XTrackerUser`

Fetch a single tracked user by handle. Returns a dict with `trackings` materialized as a DataFrame.

```python
user = client.get_xtracker_user("elonmusk")
user["trackings"]  # DataFrame of tracking periods
```

### `get_xtracker_user_posts(handle, platform=None, start_date=None, end_date=None, timezone="EST") -> pd.DataFrame`

Fetch tracked posts for a user within a date range.

```python
posts = client.get_xtracker_user_posts(
    "elonmusk",
    start_date="2026-04-01",
    end_date="2026-04-07",
    timezone="EST",
)
```

| Parameter | Type | Description |
|---|---|---|
| `handle` | str | Platform handle |
| `platform` | str | Required if the handle exists on multiple platforms |
| `start_date` | str \| Timestamp | ISO date string or `pd.Timestamp` |
| `end_date` | str \| Timestamp | Inclusive end of the window |
| `timezone` | str | Time-zone label for interpreting dates (default `"EST"`) |

### `get_xtracker_user_trackings(handle, platform=None, active_only=None, expand_user=False) -> pd.DataFrame`

List tracking periods configured for a single user.

```python
trackings = client.get_xtracker_user_trackings("elonmusk", active_only=True)
```

| Parameter | Type | Description |
|---|---|---|
| `handle` | str | Platform handle |
| `platform` | str | Required if the handle exists on multiple platforms |
| `active_only` | bool | When True, only return active trackings |
| `expand_user` | bool | Flatten nested `user` dict into prefixed columns (`userHandle`, `userPlatform`, etc.) |

---

## Tracking Endpoints

### `get_xtracker_trackings(active_only=None, expand_user=False) -> pd.DataFrame`

List all tracking periods across all users. Each row represents one Polymarket counter market -- the `title` field matches the parent event title and `marketLink` points at the polymarket.com page.

```python
trackings = client.get_xtracker_trackings(active_only=True, expand_user=True)
```

| Parameter | Type | Description |
|---|---|---|
| `active_only` | bool | When True, only return currently active trackings |
| `expand_user` | bool | Flatten nested `user` dict into prefixed columns |

### `get_xtracker_tracking(id, include_stats=False) -> XTrackerTracking`

Fetch a single tracking period by id. Returns a dict.

When `include_stats=True`, the `stats` field is materialized as a DataFrame of the daily counter (one row per bucket) with aggregate scalars (`total`, `cumulative`, `pace`, `percentComplete`, `daysElapsed`, `daysRemaining`, `daysTotal`, `isComplete`) accessible via `stats.attrs`.

```python
tracking = client.get_xtracker_tracking("some-uuid", include_stats=True)
daily_df = tracking["stats"]          # DataFrame with date, count, cumulative
total = tracking["stats"].attrs["total"]
pace = tracking["stats"].attrs["pace"]
```

---

## Metrics Endpoint

### `get_xtracker_metrics(user_id, type="daily", start_date=None, end_date=None) -> pd.DataFrame`

Fetch a user's per-bucket post metrics over a date range. The nested `data` object is flattened into prefixed columns (`dataCount`, `dataCumulative`, `dataTrackingId`).

```python
metrics = client.get_xtracker_metrics(
    user_id="some-uuid",  # xtracker internal user id, from get_xtracker_users()['id']
    start_date="2026-04-01",
    end_date="2026-04-07",
)
```

| Parameter | Type | Description |
|---|---|---|
| `user_id` | str | xtracker internal user id (UUID) |
| `type` | str | Bucket granularity (`"daily"` is the default and only documented value) |
| `start_date` | str \| Timestamp | ISO date string or `pd.Timestamp` |
| `end_date` | str \| Timestamp | ISO date string or `pd.Timestamp` |
