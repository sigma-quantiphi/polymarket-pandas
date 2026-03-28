"""Orderbook explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Orderbook", layout="wide")
st.title("Orderbook")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Input ────────────────────────────────────────────────────────────────────

token_id = st.text_input(
    "CLOB Token ID",
    placeholder="e.g. 12345678901234567890...",
    help="Paste a clobTokenId from the Markets page",
)

if not token_id:
    st.info("Enter a CLOB token ID to view its orderbook.")
    st.stop()

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching orderbook..."):
    try:
        df = client.get_orderbook(token_id)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

if df.empty:
    st.warning("Orderbook is empty for this token.")
    st.stop()

# ── Summary metrics ──────────────────────────────────────────────────────────

bids = df[df["side"] == "bids"]
asks = df[df["side"] == "asks"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bid levels", len(bids))
col2.metric("Ask levels", len(asks))
if not bids.empty:
    col3.metric("Best bid", f"{bids['price'].max():.4f}")
if not asks.empty:
    col4.metric("Best ask", f"{asks['price'].min():.4f}")

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
tab_bids, tab_asks, tab_all = st.tabs(["Bids", "Asks", "All"])
with tab_bids:
    st.dataframe(bids.sort_values("price", ascending=False), use_container_width=True)
with tab_asks:
    st.dataframe(asks.sort_values("price", ascending=True), use_container_width=True)
with tab_all:
    st.dataframe(df, use_container_width=True)

# ── Depth chart ──────────────────────────────────────────────────────────────

import plotly.graph_objects as go

st.subheader("Depth Chart")

bid_sorted = bids.sort_values("price", ascending=False).copy()
ask_sorted = asks.sort_values("price", ascending=True).copy()
bid_sorted["cumSize"] = bid_sorted["size"].cumsum()
ask_sorted["cumSize"] = ask_sorted["size"].cumsum()

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=bid_sorted["price"],
        y=bid_sorted["cumSize"],
        fill="tozeroy",
        name="Bids",
        line={"color": "green"},
        fillcolor="rgba(0, 128, 0, 0.2)",
    )
)
fig.add_trace(
    go.Scatter(
        x=ask_sorted["price"],
        y=ask_sorted["cumSize"],
        fill="tozeroy",
        name="Asks",
        line={"color": "red"},
        fillcolor="rgba(255, 0, 0, 0.2)",
    )
)
fig.update_layout(
    title="Orderbook Depth",
    xaxis_title="Price",
    yaxis_title="Cumulative Size",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_orderbook("{token_id}")

bids = df[df["side"] == "bids"]
asks = df[df["side"] == "asks"]
print(f"Best bid: {{bids['price'].max():.4f}}")
print(f"Best ask: {{asks['price'].min():.4f}}")
""",
        language="python",
    )
