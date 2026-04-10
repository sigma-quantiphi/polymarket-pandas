# polymarket-pandas

[![PyPI](https://img.shields.io/pypi/v/polymarket-pandas)](https://pypi.org/project/polymarket-pandas/)
[![Python](https://img.shields.io/pypi/pyversions/polymarket-pandas)](https://pypi.org/project/polymarket-pandas/)
[![Downloads](https://img.shields.io/pypi/dm/polymarket-pandas)](https://pypistats.org/packages/polymarket-pandas)
[![License](https://img.shields.io/pypi/l/polymarket-pandas)](https://github.com/sigma-quantiphi/polymarket-pandas/blob/main/LICENSE)
[![CI](https://github.com/sigma-quantiphi/polymarket-pandas/actions/workflows/ci.yml/badge.svg)](https://github.com/sigma-quantiphi/polymarket-pandas/actions/workflows/ci.yml)

Pandas-native Python client for the full [Polymarket](https://polymarket.com) API surface — REST, WebSocket, Relayer, and Bridge — with automatic type coercion and DataFrame output.

## Features

- **102 public methods** across 9 API mixins (Gamma, CLOB, Data, Rewards, Bridge, Relayer, CTF, XTracker)
- **Every endpoint returns a `pd.DataFrame`** with automatic type coercion (datetimes, numerics, booleans)
- **Sync + Async** HTTP clients — `PolymarketPandas` and `AsyncPolymarketPandas`
- **WebSocket streaming** — real-time orderbook, prices, trades, sports, crypto feeds
- **pandera schemas** for column documentation and optional runtime validation
- **TypedDicts** for dict-returning endpoints with full IDE autocomplete
- **Order building & EIP-712 signing** — `build_order`, `place_order`, `submit_orders` (DataFrame batch)
- **On-chain CTF operations** — merge, split, redeem positions via web3
- **Title parsers** — extract bracket bounds, directional thresholds, and sports lines from market titles
- **Auto-pagination** — offset-based and cursor-based `_all()` methods
- **Interactive Streamlit explorer** with 11 pages and Plotly charts
- **MCP server** with 74 tools for Claude Code / Claude Desktop

## Installation

```bash
pip install polymarket-pandas
```

Optional extras:

```bash
pip install "polymarket-pandas[ctf]"       # on-chain merge/split/redeem
pip install "polymarket-pandas[explorer]"   # Streamlit dashboard
pip install "polymarket-pandas[mcp]"        # MCP server (74 tools)
```

## Quick Start

```python
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()

# Get active markets sorted by volume
markets = client.get_markets(closed=False, limit=100)
print(markets[["slug", "volume24hr", "endDate"]].head())

# Get the order book for a token
book = client.get_orderbook("15871154585880608648...")
print(book)
```

See the [Getting Started](getting-started.md) guide for a complete walkthrough.

## Links

- [GitHub Repository](https://github.com/sigma-quantiphi/polymarket-pandas)
- [PyPI Package](https://pypi.org/project/polymarket-pandas/)
- [Changelog](changelog.md)
