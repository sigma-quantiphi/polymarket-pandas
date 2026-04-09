"""Polymarket Pandas Explorer — home page and shared client setup."""

from __future__ import annotations

import streamlit as st

from polymarket_pandas import PolymarketPandas

st.set_page_config(
    page_title="Polymarket Explorer",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

# ── Sidebar: client configuration ────────────────────────────────────────────

st.sidebar.title("Configuration")

with st.sidebar.expander("API Credentials (optional)", expanded=False):
    st.caption(
        "Leave blank for public endpoints. Set for private endpoints (positions, orders, trades)."
    )
    _addr = st.text_input("Wallet address", key="cfg_address", type="default")
    _api_key = st.text_input("API key", key="cfg_api_key", type="password")
    _api_secret = st.text_input("API secret", key="cfg_api_secret", type="password")
    _api_passphrase = st.text_input(
        "API passphrase", key="cfg_api_passphrase", type="password"
    )


def get_client() -> PolymarketPandas:
    """Return a shared ``PolymarketPandas`` client, cached in session state."""
    # Build a cache key from credentials so the client refreshes when they change
    cache_key = (_addr, _api_key, _api_secret, _api_passphrase)
    if (
        "client" not in st.session_state
        or st.session_state.get("_client_key") != cache_key
    ):
        kwargs: dict = {}
        if _addr:
            kwargs["address"] = _addr
        if _api_key:
            kwargs["api_key"] = _api_key
        if _api_secret:
            kwargs["api_secret"] = _api_secret
        if _api_passphrase:
            kwargs["api_passphrase"] = _api_passphrase
        st.session_state["client"] = PolymarketPandas(**kwargs)
        st.session_state["_client_key"] = cache_key
    return st.session_state["client"]


# Make get_client available to all pages via session state
st.session_state["get_client"] = get_client

# ── Home page content ────────────────────────────────────────────────────────

st.title("Polymarket Pandas Explorer")

st.markdown("""
Interactive dashboard for exploring the [Polymarket](https://polymarket.com) API
via the **polymarket-pandas** SDK.

### Entity Hierarchy

```
Series  (recurring collections)
  └── Events  (e.g. "2024 US Election")
        └── Markets  (e.g. "Will Trump win?")
              ├── conditionId   (1:1 — the on-chain condition)
              └── clobTokenIds  (1:N — one per outcome)
                    ├── Orderbooks   (bid/ask ladder)
                    ├── Positions    (user holdings)
                    ├── Trades       (fill history)
                    └── Orders       (open limit orders)
```

### Pages

| Page | Endpoints | Auth Required |
|------|-----------|---------------|
| **Markets** | `get_markets`, `get_markets_all` | No |
| **Events** | `get_events`, `get_events_all` | No |
| **Series** | `get_series`, `get_series_all` | No |
| **Tags** | `get_tags` | No |
| **Orderbook** | `get_orderbook` | No |
| **Prices** | `get_price_history`, `get_midpoint_price`, `get_spread` | No |
| **Positions** | `get_positions`, `get_closed_positions` | No (needs wallet address) |
| **Trades** | `get_trades`, `get_user_trades` | Partial (user trades need L2) |
| **Leaderboard** | `get_leaderboard`, `get_builder_leaderboard` | No |
| **Rewards** | `get_current_rewards`, `get_user_earnings` | No |
| **Bridge** | `get_deposit_addresses`, `get_supported_assets` | No |

Use the sidebar to navigate between pages. Each page shows:
- **Data table** — the raw DataFrame from the SDK
- **Visualization** — interactive Plotly chart
- **Code snippet** — the equivalent Python code to reproduce
""")

# Show client status
client = get_client()
st.sidebar.success("Client initialized")
st.sidebar.caption(f"CLOB: {client.clob_url}")
st.sidebar.caption(f"Gamma: {client.gamma_url}")
