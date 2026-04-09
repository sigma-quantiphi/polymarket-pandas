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
    offset = st.number_input("Offset", min_value=0, value=0, step=10, key="positions_offset")

    if tab == "Open":
        sort_by = st.selectbox("Sort by", ["TOKENS", "VALUE"], key="positions_sort_open")
        sort_dir = st.selectbox("Sort direction", ["DESC", "ASC"], key="positions_dir_open")
        size_threshold = st.number_input(
            "Size threshold",
            min_value=0.0,
            value=1.0,
            step=0.1,
            key="positions_size_thresh",
            help="Min position size to include",
        )
        redeemable = st.checkbox("Redeemable only", value=False, key="positions_redeemable")
        mergeable = st.checkbox("Mergeable only", value=False, key="positions_mergeable")
    else:
        sort_by = st.selectbox(
            "Sort by",
            ["REALIZEDPNL", "TOTAL_PNL", "TOKENS"],
            key="positions_sort_closed",
        )
        sort_dir = st.selectbox("Sort direction", ["DESC", "ASC"], key="positions_dir_closed")

    with st.expander("Filter by Market/Event"):
        market_ids = st.text_input("Market token IDs (comma-separated)", key="pos_market_ids")
        event_ids = st.text_input("Event IDs (comma-separated)", key="pos_event_ids")
        title = st.text_input("Title search", key="pos_title")

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching positions..."):
    try:
        market_list = [s.strip() for s in market_ids.split(",") if s.strip()] or None
        event_list = [int(s.strip()) for s in event_ids.split(",") if s.strip()] or None

        if tab == "Open":
            df = client.get_positions(
                user=user_addr,
                limit=limit,
                offset=offset if offset > 0 else 0,
                sortBy=sort_by,
                sortDirection=sort_dir,
                sizeThreshold=size_threshold,
                redeemable=redeemable or None,
                mergeable=mergeable or None,
                market=market_list,
                eventId=event_list,
                title=title or None,
            )
        else:
            df = client.get_closed_positions(
                user=user_addr,
                limit=limit,
                offset=offset if offset > 0 else 0,
                sortBy=sort_by,
                sortDirection=sort_dir,
                market=market_list,
                eventId=event_list,
                title=title or None,
            )
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Positions", len(df))

if df.empty:
    st.warning("No positions found for this address.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="stretch", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

import plotly.express as px  # noqa: E402

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
    sortDirection="{sort_dir}",
)
print(df)
""",
        language="python",
    )
