"""Prices explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Prices", layout="wide")
st.title("Prices")

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
    key="prices_token_id",
)

if not token_id:
    st.info("Enter a CLOB token ID to view price data.")
    st.stop()

# ── Spot prices ──────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

with st.spinner("Fetching spot prices..."):
    try:
        midpoint = client.get_midpoint_price(token_id)
        col1.metric("Midpoint", f"{midpoint:.4f}")
    except Exception as e:
        col1.error(f"Midpoint: {e}")

    try:
        spread = client.get_spread(token_id)
        col2.metric("Spread", f"{spread:.4f}")
    except Exception as e:
        col2.error(f"Spread: {e}")

    try:
        last = client.get_last_trade_price(token_id)
        price = last.get("price", "N/A")
        col3.metric("Last trade", f"{float(price):.4f}" if price != "N/A" else "N/A")
    except Exception as e:
        col3.error(f"Last trade: {e}")

# ── Price history ────────────────────────────────────────────────────────────

st.subheader("Price History")

with st.sidebar:
    st.subheader("Price History Params")
    interval = st.selectbox(
        "Interval", ["max", "1m", "1w", "1d", "6h", "1h"], index=0, key="ph_interval"
    )
    fidelity = st.selectbox(
        "Fidelity (minutes)", [None, 1, 5, 15, 60, 360, 1440], index=0, key="ph_fidelity"
    )

    with st.expander("Time Range"):
        st.caption("Unix timestamps (seconds). Leave 0 to omit.")
        start_ts = st.number_input(
            "Start timestamp", min_value=0, value=0, step=1, key="ph_start_ts"
        )
        end_ts = st.number_input("End timestamp", min_value=0, value=0, step=1, key="ph_end_ts")

ph_kwargs: dict = {
    "market": token_id,
    "interval": interval,
    "fidelity": fidelity,
    "startTs": start_ts if start_ts > 0 else None,
    "endTs": end_ts if end_ts > 0 else None,
}
active_ph_kwargs = {k: v for k, v in ph_kwargs.items() if v is not None}

with st.spinner("Fetching price history..."):
    try:
        df = client.get_price_history(**active_ph_kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

if df.empty:
    st.warning("No price history available for this token.")
    st.stop()

st.dataframe(df, width="full", height=300)

# ── Price chart ──────────────────────────────────────────────────────────────

import plotly.express as px  # noqa: E402

time_col = None
for candidate in ["t", "timestamp", "time"]:
    if candidate in df.columns:
        time_col = candidate
        break

price_col = None
for candidate in ["p", "price"]:
    if candidate in df.columns:
        price_col = candidate
        break

if time_col and price_col:
    fig = px.line(
        df,
        x=time_col,
        y=price_col,
        title="Price Over Time",
        labels={time_col: "Time", price_col: "Price"},
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, width="full")

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_ph_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()

# Spot prices
midpoint = client.get_midpoint_price("{token_id}")
spread = client.get_spread("{token_id}")
last = client.get_last_trade_price("{token_id}")

# Price history
df = client.get_price_history(
    {args_str},
)
print(df)
""",
        language="python",
    )
