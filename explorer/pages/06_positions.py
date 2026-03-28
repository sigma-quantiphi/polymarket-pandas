"""Positions explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Positions", layout="wide")
st.title("Positions")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Input ────────────────────────────────────────────────────────────────────

user_addr = st.text_input(
    "Wallet address",
    placeholder="0x...",
    help="User or proxy wallet address",
)

if not user_addr:
    st.info("Enter a wallet address to view positions. No API key required.")
    st.stop()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Position Filters")
    tab = st.radio("View", ["Open", "Closed"], key="positions_tab")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=100, key="positions_limit")
    sort_by = st.selectbox(
        "Sort by",
        ["TOKENS", "TOTAL_PNL", "REALIZEDPNL"] if tab == "Closed" else ["TOKENS", "VALUE"],
        key="positions_sort",
    )

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching positions..."):
    try:
        if tab == "Open":
            df = client.get_positions(user=user_addr, limit=limit, sortBy=sort_by)
        else:
            df = client.get_closed_positions(user=user_addr, limit=limit, sortBy=sort_by)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Positions", len(df))

if df.empty:
    st.warning("No positions found for this address.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, use_container_width=True, height=400)

# ── Visualization ────────────────────────────────────────────────────────────

import plotly.express as px

size_col = None
for candidate in ["currentValue", "size", "initialValue"]:
    if candidate in df.columns:
        size_col = candidate
        break

label_col = "title" if "title" in df.columns else "slug" if "slug" in df.columns else None

if size_col and label_col:
    st.subheader("Portfolio Breakdown")
    chart_df = df.dropna(subset=[size_col]).copy()
    chart_df[size_col] = chart_df[size_col].astype(float).abs()
    chart_df = chart_df[chart_df[size_col] > 0]
    if not chart_df.empty:
        fig = px.pie(
            chart_df,
            values=size_col,
            names=label_col,
            title=f"Positions by {size_col}",
            hole=0.3,
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    method = "get_positions" if tab == "Open" else "get_closed_positions"
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.{method}(
    user="{user_addr}",
    limit={limit},
    sortBy="{sort_by}",
)
print(df)
""",
        language="python",
    )
