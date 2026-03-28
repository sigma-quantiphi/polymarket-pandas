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
    offset = st.number_input("Offset", min_value=0, value=0, step=10, key="trades_offset")
    user = st.text_input("User address (optional)", key="trades_user", placeholder="0x...")
    side = st.selectbox(
        "Side", [None, "BUY", "SELL"], format_func=lambda x: x or "All", key="trades_side"
    )
    taker_only = st.checkbox("Taker only", value=True, key="trades_taker_only")

    with st.expander("Filter by Market/Event"):
        market_ids = st.text_input("Market token IDs (comma-separated)", key="trades_market_ids")
        event_ids = st.text_input("Event IDs (comma-separated)", key="trades_event_ids")

    with st.expander("Amount Filter"):
        filter_type = st.selectbox(
            "Filter type", [None, "ABOVE", "BELOW"], key="trades_filter_type"
        )
        filter_amount = st.number_input(
            "Filter amount",
            min_value=0.0,
            value=0.0,
            step=10.0,
            key="trades_filter_amount",
            help="Used with filter type",
        )

# ── Build kwargs ─────────────────────────────────────────────────────────────

kwargs: dict = {
    "limit": limit,
    "offset": offset if offset > 0 else 0,
    "user": user or None,
    "side": side,
    "takerOnly": taker_only,
    "market": [s.strip() for s in market_ids.split(",") if s.strip()] or None,
    "eventId": [int(s.strip()) for s in event_ids.split(",") if s.strip()] or None,
    "filterType": filter_type,
    "filterAmount": filter_amount if filter_amount > 0 and filter_type else None,
}

active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching trades..."):
    try:
        df = client.get_trades(**active_kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Trades returned", len(df))

if df.empty:
    st.warning("No trades found.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="full", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

import plotly.express as px  # noqa: E402

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
    st.plotly_chart(fig, width="full")

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_trades(
    {args_str},
)
print(df)
""",
        language="python",
    )
