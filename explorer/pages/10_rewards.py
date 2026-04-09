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
        next_cursor = st.text_input(
            "Next cursor",
            key="rewards_cursor",
            help="Paste cursor from previous page to continue",
        )

    with st.spinner("Fetching current rewards..."):
        try:
            result = client.get_rewards_markets_current(
                sponsored=sponsored,
                next_cursor=next_cursor or None,
            )
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Reward configs", len(df))
    st.caption(f"Next cursor: `{result.get('next_cursor', 'N/A')}`")

    if not df.empty:
        st.dataframe(df, width="stretch", height=400)

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
result = client.get_rewards_markets_current(
    sponsored={sponsored},
    next_cursor={f'"{next_cursor}"' if next_cursor else None},
)
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
        position = st.selectbox("Sort direction", [None, "ASC", "DESC"], key="rewards_position")
        page_size = st.number_input(
            "Page size", min_value=1, max_value=500, value=100, key="rewards_page_size"
        )
        next_cursor = st.text_input("Next cursor", key="rewards_multi_cursor")

        with st.expander("Tag / Event Filter"):
            tag_slug = st.text_input("Tag slug", key="rewards_tag_slug")
            event_id = st.text_input("Event ID", key="rewards_event_id")
            event_title = st.text_input("Event title", key="rewards_event_title")

        with st.expander("Numeric Filters"):
            min_volume_24hr = st.number_input(
                "Min 24h volume",
                min_value=0.0,
                value=0.0,
                step=100.0,
                key="rewards_min_vol",
            )
            max_volume_24hr = st.number_input(
                "Max 24h volume",
                min_value=0.0,
                value=0.0,
                step=100.0,
                key="rewards_max_vol",
                help="0 = no limit",
            )
            min_spread = st.number_input(
                "Min spread",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="rewards_min_spread",
            )
            max_spread = st.number_input(
                "Max spread",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="rewards_max_spread",
                help="0 = no limit",
            )
            min_price = st.number_input(
                "Min price",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="rewards_min_price",
            )
            max_price = st.number_input(
                "Max price",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="rewards_max_price",
                help="0 = no limit",
            )

    kwargs: dict = {
        "q": q or None,
        "order_by": order_by,
        "position": position,
        "page_size": page_size if page_size != 100 else None,
        "next_cursor": next_cursor or None,
        "tag_slug": tag_slug or None,
        "event_id": event_id or None,
        "event_title": event_title or None,
        "min_volume_24hr": min_volume_24hr if min_volume_24hr > 0 else None,
        "max_volume_24hr": max_volume_24hr if max_volume_24hr > 0 else None,
        "min_spread": min_spread if min_spread > 0 else None,
        "max_spread": max_spread if max_spread > 0 else None,
        "min_price": min_price if min_price > 0 else None,
        "max_price": max_price if max_price > 0 else None,
    }
    active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    with st.spinner("Fetching markets with rewards..."):
        try:
            result = client.get_rewards_markets_multi(**active_kwargs)
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Markets", len(df))
    st.caption(f"Next cursor: `{result.get('next_cursor', 'N/A')}`")

    if not df.empty:
        st.dataframe(df, width="stretch", height=400)

    with st.expander("View Code"):
        args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
result = client.get_rewards_markets_multi(
    {args_str},
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

    with st.sidebar:
        st.subheader("Filters")
        sponsored = st.selectbox(
            "Sponsored",
            [None, True, False],
            format_func=lambda x: {None: "All", True: "Sponsored", False: "Standard"}[x],
            key="rewards_mkt_sponsored",
        )
        next_cursor = st.text_input("Next cursor", key="rewards_mkt_cursor")

    with st.spinner("Fetching market rewards..."):
        try:
            result = client.get_rewards_market(
                condition_id=condition_id,
                sponsored=sponsored,
                next_cursor=next_cursor or None,
            )
            df = result["data"]
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

    st.metric("Reward configs", len(df))
    st.caption(f"Next cursor: `{result.get('next_cursor', 'N/A')}`")

    if not df.empty:
        st.dataframe(df, width="stretch", height=400)

    with st.expander("View Code"):
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
result = client.get_rewards_market(
    condition_id="{condition_id}",
    sponsored={sponsored},
    next_cursor={f'"{next_cursor}"' if next_cursor else None},
)
df = result["data"]
print(df)
""",
            language="python",
        )
