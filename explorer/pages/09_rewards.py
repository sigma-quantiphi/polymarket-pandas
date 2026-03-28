"""Rewards explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Rewards", layout="wide")
st.title("Rewards")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Endpoint selection ───────────────────────────────────────────────────────

endpoint = st.selectbox(
    "Endpoint",
    [
        "Current Reward Configs",
        "Markets with Rewards",
        "Market Rewards (by condition ID)",
    ],
    key="rewards_endpoint",
)

# ── Current Reward Configs ───────────────────────────────────────────────────

if endpoint == "Current Reward Configs":
    with st.sidebar:
        st.subheader("Filters")
        sponsored = st.selectbox(
            "Sponsored",
            [None, True, False],
            format_func=lambda x: {None: "All", True: "Sponsored", False: "Standard"}[x],
            key="rewards_sponsored",
        )

    with st.spinner("Fetching current rewards..."):
        try:
            result = client.get_rewards_markets_current(sponsored=sponsored)
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Reward configs", len(df))
    st.caption(f"Next cursor: `{result.get('next_cursor', 'N/A')}`")

    if not df.empty:
        st.dataframe(df, use_container_width=True, height=400)

        import plotly.express as px

        rate_col = None
        for candidate in ["ratePerDay", "rewardRate", "dailyRate"]:
            if candidate in df.columns:
                rate_col = candidate
                break
        if rate_col:
            st.subheader("Reward Rate Distribution")
            chart_df = df.dropna(subset=[rate_col]).copy()
            chart_df[rate_col] = chart_df[rate_col].astype(float)
            fig = px.histogram(chart_df, x=rate_col, nbins=30, title="Distribution of Reward Rates")
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("View Code"):
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
result = client.get_rewards_markets_current(sponsored={sponsored})
df = result["data"]
print(f"Configs: {{len(df)}}, next_cursor: {{result['next_cursor']}}")
""",
            language="python",
        )

# ── Markets with Rewards ─────────────────────────────────────────────────────

elif endpoint == "Markets with Rewards":
    with st.sidebar:
        st.subheader("Filters")
        q = st.text_input("Search query", key="rewards_q")
        order_by = st.selectbox(
            "Order by",
            [None, "rate_per_day", "volume_24hr", "spread", "competitiveness"],
            key="rewards_order",
        )

    with st.spinner("Fetching markets with rewards..."):
        try:
            result = client.get_rewards_markets_multi(
                q=q or None,
                order_by=order_by,
            )
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Markets", len(df))
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=400)

    with st.expander("View Code"):
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
result = client.get_rewards_markets_multi(
    q={f'"{q}"' if q else None},
    order_by={f'"{order_by}"' if order_by else None},
)
df = result["data"]
print(df)
""",
            language="python",
        )

# ── Market Rewards (by condition ID) ─────────────────────────────────────────

else:
    condition_id = st.text_input(
        "Condition ID",
        placeholder="0x...",
        help="The conditionId of a market (from the Markets page)",
        key="rewards_condition_id",
    )
    if not condition_id:
        st.info("Enter a condition ID to view its reward configuration.")
        st.stop()

    with st.spinner("Fetching market rewards..."):
        try:
            result = client.get_rewards_market(condition_id=condition_id)
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Reward configs", len(df))
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=400)

    with st.expander("View Code"):
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
result = client.get_rewards_market(condition_id="{condition_id}")
df = result["data"]
print(df)
""",
            language="python",
        )
