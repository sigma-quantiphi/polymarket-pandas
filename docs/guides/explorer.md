# Interactive Explorer

polymarket-pandas includes a built-in Streamlit dashboard for exploring all public
Polymarket endpoints visually.

## Installation

```bash
pip install "polymarket-pandas[explorer]"
```

## Launch

```bash
# CLI entry point
polymarket-explore

# Or run directly with Streamlit
streamlit run explorer/home.py
```

## Pages

The explorer includes 11 pages covering the full public API surface:

| Page | Endpoint | Visualization |
|---|---|---|
| **Markets** | `get_markets` | Volume bar chart, filters sidebar |
| **Events** | `get_events` | Volume chart, expand markets toggle |
| **Series** | `get_series` | Hierarchy chart, expand events toggle |
| **Tags** | `get_tags` | Tag listing with all parameters |
| **Orderbook** | `get_orderbook` | Depth chart (bids/asks) |
| **Prices** | `get_price_history`, `get_midpoint_price`, `get_spread`, `get_last_trade_price` | Price history line chart, spot values |
| **Positions** | `get_positions`, `get_closed_positions` | Portfolio pie chart |
| **Trades** | `get_trades` | Price scatter plot |
| **Leaderboard** | `get_leaderboard`, `get_builder_leaderboard` | Rankings table |
| **Rewards** | `get_rewards_markets_current` | Reward configs |
| **Bridge** | `get_bridge_supported_assets`, `get_bridge_transaction_status` | Supported assets listing |

## Features

Each page provides:

- **Raw DataFrame** -- the full API response as a searchable, sortable table
- **Plotly chart** -- an interactive visualization appropriate for the data
- **Python code snippet** -- collapsible block showing the equivalent Python code to reproduce the query

All endpoint parameters are exposed as interactive sidebar controls, so you can
explore the API without writing any code.
