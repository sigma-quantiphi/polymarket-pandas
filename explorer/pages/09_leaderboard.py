"""Leaderboard explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Leaderboard", layout="wide")
st.title("Leaderboard")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Leaderboard Filters")
    board_type = st.radio("Type", ["Traders", "Builders"], key="lb_type")
    time_period = st.selectbox("Time period", ["DAY", "WEEK", "MONTH", "ALL"], key="lb_period")
    limit = st.number_input("Limit", min_value=1, max_value=100, value=25, key="lb_limit")
    offset = st.number_input("Offset", min_value=0, value=0, step=10, key="lb_offset")

    if board_type == "Traders":
        order_by = st.selectbox("Order by", ["PNL", "VOLUME"], key="lb_order")
        category = st.selectbox(
            "Category",
            ["OVERALL", "CRYPTO", "POLITICS", "SPORTS", "POP_CULTURE"],
            key="lb_category",
        )

        with st.expander("Lookup User"):
            lb_user = st.text_input("User address", key="lb_user", placeholder="0x...")
            lb_user_name = st.text_input("Username", key="lb_user_name")

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching leaderboard..."):
    try:
        if board_type == "Traders":
            df = client.get_leaderboard(
                category=category,
                timePeriod=time_period,
                orderBy=order_by,
                limit=limit,
                offset=offset if offset > 0 else 0,
                user=lb_user or None,
                userName=lb_user_name or None,
            )
        else:
            df = client.get_builder_leaderboard(
                timePeriod=time_period,
                limit=limit,
                offset=offset if offset > 0 else 0,
            )
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Entries", len(df))

if df.empty:
    st.warning("No leaderboard data.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="stretch", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

import plotly.express as px  # noqa: E402

name_col = None
for candidate in ["userName", "name", "address", "user"]:
    if candidate in df.columns:
        name_col = candidate
        break

value_col = None
for candidate in ["pnl", "volume", "totalVolume", "totalPnl"]:
    if candidate in df.columns:
        value_col = candidate
        break

if name_col and value_col:
    st.subheader(f"Top {board_type} by {value_col}")
    chart_df = df.dropna(subset=[value_col]).copy()
    chart_df[value_col] = chart_df[value_col].astype(float)
    top = chart_df.head(20)
    fig = px.bar(
        top,
        x=value_col,
        y=name_col,
        orientation="h",
        title=f"Top {len(top)} {board_type}",
        labels={value_col: value_col.upper(), name_col: ""},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
    st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    if board_type == "Traders":
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_leaderboard(
    category="{category}",
    timePeriod="{time_period}",
    orderBy="{order_by}",
    limit={limit},
    offset={offset},
)
print(df)
""",
            language="python",
        )
    else:
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_builder_leaderboard(
    timePeriod="{time_period}",
    limit={limit},
    offset={offset},
)
print(df)
""",
            language="python",
        )
