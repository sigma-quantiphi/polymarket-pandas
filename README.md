# polymarket-pandas

[![PyPI](https://img.shields.io/pypi/v/polymarket-pandas)](https://pypi.org/project/polymarket-pandas/)
[![Python](https://img.shields.io/pypi/pyversions/polymarket-pandas)](https://pypi.org/project/polymarket-pandas/)
[![Downloads](https://img.shields.io/pypi/dm/polymarket-pandas)](https://pypistats.org/packages/polymarket-pandas)
[![License](https://img.shields.io/pypi/l/polymarket-pandas)](https://github.com/sigma-quantiphi/polymarket-pandas/blob/main/LICENSE)
[![CI](https://github.com/sigma-quantiphi/polymarket-pandas/actions/workflows/ci.yml/badge.svg)](https://github.com/sigma-quantiphi/polymarket-pandas/actions/workflows/ci.yml)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://sigma-quantiphi.github.io/polymarket-pandas/)

Pandas-native Python client for the full [Polymarket](https://polymarket.com) API surface — REST, WebSocket, Relayer, and Bridge — with automatic type coercion and DataFrame output.

**[Documentation](https://sigma-quantiphi.github.io/polymarket-pandas/)** | **[Getting Started](https://sigma-quantiphi.github.io/polymarket-pandas/getting-started/)** | **[API Reference](https://sigma-quantiphi.github.io/polymarket-pandas/api/markets/)** | **[Changelog](https://sigma-quantiphi.github.io/polymarket-pandas/changelog/)**

---

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

---

## Installation

```bash
pip install polymarket-pandas
```

Optional extras:

```bash
pip install "polymarket-pandas[ctf]"       # on-chain merge/split/redeem (web3)
pip install "polymarket-pandas[explorer]"   # Streamlit dashboard (11 pages)
pip install "polymarket-pandas[mcp]"        # MCP server (74 tools)
```

---

## Quick Start

```python
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()

# Get active markets sorted by volume
markets = client.get_markets(closed=False, order="volume24hr", ascending=False, limit=20)
print(markets[["slug", "question", "volume24hr", "endDate"]])

# Orderbook for a token
token_id = markets["clobTokenIds"].iloc[0]
book = client.get_orderbook(token_id)

# Price history
prices = client.get_price_history(market=token_id, interval="1d", fidelity=60)
```

See the [Getting Started](https://sigma-quantiphi.github.io/polymarket-pandas/getting-started/) guide for a complete walkthrough.

---

## MCP Server

Query Polymarket data from any MCP client with 74 tools covering the full API surface.

```bash
polymarket-mcp           # stdio transport
polymarket-mcp --sse     # SSE transport
```

Add to Claude Code / Claude Desktop (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "polymarket": {
      "command": "polymarket-mcp"
    }
  }
}
```

See the [MCP Server guide](https://sigma-quantiphi.github.io/polymarket-pandas/guides/mcp-server/) for the full list of 74 tools and environment variables.

---

## Interactive Explorer

```bash
pip install "polymarket-pandas[explorer]"
polymarket-explore
```

11 pages covering Markets, Events, Series, Tags, Orderbook, Prices, Positions, Trades, Leaderboard, Rewards, and Bridge. Each page shows the raw DataFrame, an interactive Plotly chart, and the equivalent Python code.

---

## Configuration

All credentials are read from environment variables (or a `.env` file). No auth needed for public endpoints.

```bash
export POLYMARKET_ADDRESS=0xYourProxyWallet
export POLYMARKET_API_KEY=your-api-key
export POLYMARKET_API_SECRET=your-secret
export POLYMARKET_API_PASSPHRASE=your-passphrase
```

Or derive API keys from your private key:

```python
client = PolymarketPandas(private_key="0xYourKey")
creds = client.derive_api_key()  # auto-sets L2 credentials
```

See the [Configuration guide](https://sigma-quantiphi.github.io/polymarket-pandas/guides/configuration/) for all environment variables and authentication layers.

---

## Examples

| Script | Description |
|--------|-------------|
| [`btc_5min.py`](examples/btc_5min.py) | Find BTC 5-min market, fetch orderbook and prices |
| [`btc_5min_trade_merge.py`](examples/btc_5min_trade_merge.py) | Full trading flow: `submit_orders`, cancel, merge |
| [`rewards_overview.py`](examples/rewards_overview.py) | All 7 CLOB rewards endpoints |
| [`xtracker_overview.py`](examples/xtracker_overview.py) | All 7 XTracker endpoints |
| [`market_structures.py`](examples/market_structures.py) | Event structures + title parsers demo |
| [`post_only_buy.py`](examples/post_only_buy.py) | Post-only order example |
| [`rtds_ws.py`](examples/rtds_ws.py) | Real-Time Data Streams via WebSocket |
| [`user_ws.py`](examples/user_ws.py) | Private user channel — live order and trade events |

---

## License

Apache-2.0
