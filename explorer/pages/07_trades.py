"""Trades explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Trades", layout="wide")
st.title("Trades")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Trade Filters")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=100, key="trades_limit")
    user = st.text_input("User address (optional)", key="trades_user", placeholder="0x...")
    side = st.selectbox("Side", [None, "BUY", "SELL"], format_func=lambda x: x or "All", key="trades_side")
    taker_only = st.checkbox("Taker only", value=True, key="trades_taker_only")

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching trades..."):
    try:
        df = client.get_trades(
            limit=limit,
            user=user or None,
            side=side,
            takerOnly=taker_only,
        )
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Trades returned", len(df))

if df.empty:
    st.warning("No trades found.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, use_container_width=True, height=400)

# ── Visualization ────────────────────────────────────────────────────────────

import plotly.express as px

time_col = None
for candidate in ["timestamp", "createdAt", "matchTime"]:
    if candidate in df.columns:
        time_col = candidate
        break

price_col = None
for candidate in ["price", "tradePrice"]:
    if candidate in df.columns:
        price_col = candidate
        break

if time_col and price_col:
    st.subheader("Trade Prices Over Time")
    chart_df = df.dropna(subset=[price_col]).copy()
    chart_df[price_col] = chart_df[price_col].astype(float)

    color_col = "side" if "side" in chart_df.columns else None
    fig = px.scatter(
        chart_df,
        x=time_col,
        y=price_col,
        color=color_col,
        title="Trade Price vs Time",
        labels={time_col: "Time", price_col: "Price"},
        color_discrete_map={"BUY": "green", "SELL": "red"} if color_col else None,
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_trades(
    limit={limit},
    user={f'"{user}"' if user else None},
    side={f'"{side}"' if side else None},
    takerOnly={taker_only},
)
print(df)
""",
        language="python",
    )
