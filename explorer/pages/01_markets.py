"""Markets explorer page."""

from __future__ import annotations

import streamlit as st


def _tri(x):
    return {None: "Default", True: "Yes", False: "No"}[x]


st.set_page_config(page_title="Markets", layout="wide")
st.title("Markets")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Filters")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=100)
    offset = st.number_input("Offset", min_value=0, value=0, step=10)
    closed = st.selectbox(
        "Status",
        [None, False, True],
        format_func=lambda x: {None: "All", False: "Open", True: "Closed"}[x],
    )

    st.subheader("Expansion")
    expand_events = st.checkbox("Expand events", value=True)
    expand_series = st.checkbox("Expand series", value=True)
    expand_tokens = st.checkbox("Expand CLOB token IDs", value=True)

    with st.expander("Volume / Liquidity"):
        volume_min = st.number_input(
            "Min volume", min_value=0.0, value=0.0, step=1000.0
        )
        volume_max = st.number_input(
            "Max volume", min_value=0.0, value=0.0, step=1000.0, help="0 = no limit"
        )
        liquidity_min = st.number_input(
            "Min liquidity", min_value=0.0, value=0.0, step=1000.0
        )
        liquidity_max = st.number_input(
            "Max liquidity", min_value=0.0, value=0.0, step=1000.0, help="0 = no limit"
        )
        rewards_min_size = st.number_input(
            "Min rewards size",
            min_value=0.0,
            value=0.0,
            step=100.0,
            help="0 = no filter",
        )

    with st.expander("Date Range"):
        start_date_min = st.date_input("Start date min", value=None, key="mkt_sd_min")
        start_date_max = st.date_input("Start date max", value=None, key="mkt_sd_max")
        end_date_min = st.date_input("End date min", value=None, key="mkt_ed_min")
        end_date_max = st.date_input("End date max", value=None, key="mkt_ed_max")

    with st.expander("Sorting"):
        order = st.text_input(
            "Order by (comma-separated fields)",
            key="mkt_order",
            help="e.g. volume,startDate",
        )
        ascending = st.selectbox(
            "Ascending", [None, True, False], format_func=_tri, key="mkt_asc"
        )

    with st.expander("Lookup by ID"):
        slug_input = st.text_input("Slugs (comma-separated)", key="mkt_slugs")
        condition_ids_input = st.text_input(
            "Condition IDs (comma-separated)", key="mkt_cids"
        )
        clob_token_ids_input = st.text_input(
            "CLOB token IDs (comma-separated)", key="mkt_tids"
        )
        tag_id = st.number_input(
            "Tag ID",
            min_value=0,
            value=0,
            step=1,
            key="mkt_tag_id",
            help="0 = no filter",
        )

    with st.expander("Advanced"):
        related_tags = st.selectbox(
            "Related tags",
            [None, True, False],
            format_func=_tri,
            key="mkt_related_tags",
        )
        include_tag = st.selectbox(
            "Include tag", [None, True, False], format_func=_tri, key="mkt_include_tag"
        )
        cyom = st.selectbox(
            "CYOM", [None, True, False], format_func=_tri, key="mkt_cyom"
        )
        uma_resolution_status = st.selectbox(
            "UMA resolution status",
            [None, "proposed", "disputed", "resolved"],
            key="mkt_uma",
        )
        game_id = st.text_input("Game ID", key="mkt_game_id")
        sports_market_types_input = st.text_input(
            "Sports market types (comma-separated)", key="mkt_smt"
        )

# ── Build kwargs ─────────────────────────────────────────────────────────────

kwargs: dict = {
    "limit": limit,
    "offset": offset if offset > 0 else None,
    "closed": closed,
    "expand_events": expand_events,
    "expand_series": expand_series,
    "expand_clob_token_ids": expand_tokens,
    "volume_num_min": volume_min if volume_min > 0 else None,
    "volume_num_max": volume_max if volume_max > 0 else None,
    "liquidity_num_min": liquidity_min if liquidity_min > 0 else None,
    "liquidity_num_max": liquidity_max if liquidity_max > 0 else None,
    "rewards_min_size": rewards_min_size if rewards_min_size > 0 else None,
    "start_date_min": str(start_date_min) if start_date_min else None,
    "start_date_max": str(start_date_max) if start_date_max else None,
    "end_date_min": str(end_date_min) if end_date_min else None,
    "end_date_max": str(end_date_max) if end_date_max else None,
    "order": [s.strip() for s in order.split(",") if s.strip()] or None,
    "ascending": ascending,
    "slug": [s.strip() for s in slug_input.split(",") if s.strip()] or None,
    "condition_ids": [s.strip() for s in condition_ids_input.split(",") if s.strip()]
    or None,
    "clob_token_ids": [s.strip() for s in clob_token_ids_input.split(",") if s.strip()]
    or None,
    "tag_id": tag_id if tag_id > 0 else None,
    "related_tags": related_tags,
    "include_tag": include_tag,
    "cyom": cyom,
    "uma_resolution_status": uma_resolution_status,
    "game_id": game_id or None,
    "sports_market_types": [
        s.strip() for s in sports_market_types_input.split(",") if s.strip()
    ]
    or None,
}

# Remove None values for clean code snippet
active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching markets..."):
    try:
        df = client.get_markets(**active_kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Rows returned", len(df))

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="stretch", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

if not df.empty and "volumeNum" in df.columns:
    import plotly.express as px

    st.subheader("Volume Distribution")
    chart_df = df.dropna(subset=["volumeNum"]).copy()
    if not chart_df.empty:
        display_col = "question" if "question" in chart_df.columns else "slug"
        if display_col in chart_df.columns:
            top = chart_df.nlargest(20, "volumeNum")
            fig = px.bar(
                top,
                x="volumeNum",
                y=display_col,
                orientation="h",
                title="Top 20 Markets by Volume",
                labels={"volumeNum": "Volume (USD)", display_col: "Market"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
            st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_markets(
    {args_str},
)
print(df)
""",
        language="python",
    )
