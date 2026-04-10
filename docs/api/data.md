# Data & Positions

Data API endpoints (`data-api.polymarket.com`) for positions, trades, leaderboards, and aggregate metrics.

---

## Positions

### `get_positions(user, **kwargs) -> pd.DataFrame`

Get open positions for a user.

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

### `get_positions_all(user, **kwargs) -> pd.DataFrame`

Auto-paginate all open positions for a user.

```python
all_positions = client.get_positions_all(user="0x...")
```

### `get_closed_positions(user, **kwargs) -> pd.DataFrame`

Get closed (resolved or sold) positions for a user.

```python
closed = client.get_closed_positions(
    user="0xYourAddress",
    sortBy="REALIZEDPNL",
    limit=50,
)
```

### `get_closed_positions_all(user, **kwargs) -> pd.DataFrame`

Auto-paginate all closed positions for a user.

```python
all_closed = client.get_closed_positions_all(user="0x...")
```

### `get_market_positions(market, **kwargs) -> pd.DataFrame`

All positions for a market, across all traders.

```python
pos = client.get_market_positions(
    market="0xConditionId...",
    status="OPEN",
    sortBy="TOTAL_PNL",
    limit=50,
)
```

### `get_market_positions_all(market, **kwargs) -> pd.DataFrame`

Auto-paginate all positions for a market.

```python
all_mkt_pos = client.get_market_positions_all(market="0xTokenId...")
```

### `get_top_holders(market, limit=100, minBalance=1) -> pd.DataFrame`

Get top token holders for a market.

```python
holders = client.get_top_holders(market=["0xConditionId..."])
```

### `get_positions_value(user, market=None) -> pd.DataFrame`

Get the total value of a user's positions, optionally filtered by market.

---

## Leaderboard

### `get_leaderboard(**kwargs) -> pd.DataFrame`

Get the trading leaderboard.

```python
lb = client.get_leaderboard(
    category="CRYPTO",
    timePeriod="WEEK",
    orderBy="PNL",
    limit=25,
)
```

### `get_leaderboard_all(**kwargs) -> pd.DataFrame`

Auto-paginate the full leaderboard.

```python
all_lb = client.get_leaderboard_all(timePeriod="WEEK")
```

---

## Trades

### `get_trades(**kwargs) -> pd.DataFrame`

Get trades with optional user and market filters.

```python
trades = client.get_trades(
    user="0xYourAddress",
    market=["0xConditionId..."],
    limit=100,
)
```

### `get_trades_all(**kwargs) -> pd.DataFrame`

Auto-paginate all matching trades.

```python
all_trades = client.get_trades_all(market=["0xTokenId..."])
```

---

## User Activity

### `get_user_activity(user, **kwargs) -> pd.DataFrame`

Get a user's activity log (trades, redeems, etc.).

```python
activity = client.get_user_activity(
    user="0xYourAddress",
    type=["TRADE", "REDEEM"],
    limit=100,
)
```

### `get_user_activity_all(user, **kwargs) -> pd.DataFrame`

Auto-paginate all activity for a user.

```python
all_activity = client.get_user_activity_all(user="0x...")
```

---

## Accounting

### `get_accounting_snapshot(user) -> dict[str, pd.DataFrame]`

Downloads and parses the ZIP accounting snapshot. Returns a dict of DataFrames.

```python
snapshot = client.get_accounting_snapshot("0xYourAddress")
positions_df = snapshot["positions"]
equity_df    = snapshot["equity"]
```

---

## Aggregate Metrics

### `get_live_volume(id) -> dict`

Get live volume for an event.

```python
vol = client.get_live_volume(id=12345)
```

### `get_open_interest(market=None) -> dict`

Get open interest, optionally filtered by market.

```python
oi = client.get_open_interest(market=["0xConditionId..."])
```

### `get_traded_markets_count(user) -> dict`

Get the number of markets a user has traded.

```python
count = client.get_traded_markets_count("0xYourAddress")
```

---

## Builders

### `get_builder_leaderboard(timePeriod="DAY", limit=25, offset=0) -> pd.DataFrame`

Get the builder (API integrator) leaderboard.

```python
lb = client.get_builder_leaderboard(timePeriod="WEEK")
```

### `get_builder_leaderboard_all(**kwargs) -> pd.DataFrame`

Auto-paginate the full builder leaderboard.

```python
all_builder = client.get_builder_leaderboard_all()
```

### `get_builder_volume(timePeriod="DAY") -> pd.DataFrame`

Get builder volume breakdown.

```python
vol = client.get_builder_volume(timePeriod="ALL")
```
