# Title Parsers

The `polymarket_pandas.parsers` module provides vectorized regex extractors that turn free-text `marketsGroupItemTitle` strings into structured columns. Polymarket exposes bracket bounds, directional thresholds, and sports spread/total lines only as display text (e.g. "280-299", "up 200,000", "Spread -1.5", "O/U 8.5").

---

## Usage

```python
from polymarket_pandas import (
    PolymarketPandas,
    classify_event_structure,
    parse_title_bounds,
    parse_title_sports,
    coalesce_end_date_from_title,
)

client = PolymarketPandas()
df = client.get_events(closed=False, limit=300, expand_markets=True)

df = pd.concat([df, parse_title_bounds(df), parse_title_sports(df)], axis=1)
df["structure"] = classify_event_structure(df)        # 5 event-shape labels
df["marketsEndDate"] = coalesce_end_date_from_title(df)  # fill NaT from title
```

All parsers default to the `markets`-prefixed column names produced by `get_events(expand_markets=True)`. Pass the unprefixed equivalents (`title_col="groupItemTitle"`, etc.) to use them on raw `get_markets` output.

---

## Functions

### `classify_event_structure(data, ...) -> pd.Series`

Per-row label assigning each market to one of five event structures:

| Label | Description |
|---|---|
| `Single-Outcome` | Events with one binary market |
| `negRisk Multi-Outcome` | Mutually-exclusive outcomes (prices sum to $1) |
| `Non-negRisk Multi-Outcome` | Independent binary markets |
| `Directional / Counter-Based` | Thresholds on a counter (up/down titles) |
| `Bracketed` | Numeric value carved into ranges ("20-29", "<20", "580+") |

Parameters: `id_col`, `condition_id_col`, `neg_risk_col`, `title_col` (all default to `markets`-prefixed names).

### `parse_title_bounds(data, ...) -> pd.DataFrame`

Extract numeric bounds from bracket and directional titles.

**Adds columns:**

| Column | Description |
|---|---|
| `boundLow` | Lower bound of the bracket range (float) |
| `boundHigh` | Upper bound of the bracket range (float) |
| `direction` | Direction indicator (e.g. "up", "down") |
| `threshold` | Numeric threshold for directional titles (float) |

### `parse_title_sports(data, ...) -> pd.DataFrame`

Extract sports-specific fields from market titles.

**Adds columns:**

| Column | Description |
|---|---|
| `spreadLine` | Spread line value (float, e.g. -1.5) |
| `totalLine` | Over/under total line value (float, e.g. 8.5) |
| `side` | Side indicator (e.g. "Over", "Under", team name) |

### `coalesce_end_date_from_title(data, ...) -> pd.Series`

Fills `NaT` values in `marketsEndDate` by parsing "Month Day" patterns from market titles and inferring the year from `marketsStartDate` (with Dec-to-Jan rollover handling).

---

## Summary Table

| Function | Adds columns |
|---|---|
| `classify_event_structure` | One of 5 event-shape labels |
| `parse_title_bounds` | `boundLow`, `boundHigh`, `direction`, `threshold` |
| `parse_title_sports` | `spreadLine`, `totalLine`, `side` |
| `coalesce_end_date_from_title` | Fills NaT in `marketsEndDate` by parsing titles |

See `examples/market_structures.py` for an end-to-end demo covering all 10 event shapes (5 core + BTC up/down + 4 sports market types).
