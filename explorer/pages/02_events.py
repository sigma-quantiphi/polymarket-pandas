"""Events explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Events", layout="wide")
st.title("Events")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Filters")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=100, key="events_limit")
    closed = st.selectbox(
        "Status",
        [None, False, True],
        format_func=lambda x: {None: "All", False: "Open", True: "Closed"}[x],
        key="events_closed",
    )
    featured = st.selectbox(
        "Featured",
        [None, True, False],
        format_func=lambda x: {None: "All", True: "Featured only", False: "Non-featured"}[x],
        key="events_featured",
    )
    expand_markets = st.checkbox("Expand markets", value=True, key="events_expand_markets")
    expand_tokens = st.checkbox("Expand CLOB token IDs", value=True, key="events_expand_tokens")

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching events..."):
    try:
        df = client.get_events(
            limit=limit,
            closed=closed,
            featured=featured,
            expand_markets=expand_markets,
            expand_clob_token_ids=expand_tokens,
        )
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Rows returned", len(df))

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, use_container_width=True, height=400)

# ── Visualization ────────────────────────────────────────────────────────────

if not df.empty:
    import plotly.express as px

    volume_col = None
    for candidate in ["marketsVolumeNum", "volume", "volumeNum"]:
        if candidate in df.columns:
            volume_col = candidate
            break

    if volume_col:
        st.subheader("Events by Volume")
        chart_df = df.dropna(subset=[volume_col]).copy()
        display_col = "title" if "title" in chart_df.columns else "slug"
        if not chart_df.empty and display_col in chart_df.columns:
            # Aggregate volume per event (may have multiple market rows)
            agg = chart_df.groupby(display_col, as_index=False)[volume_col].sum()
            top = agg.nlargest(20, volume_col)
            fig = px.bar(
                top,
                x=volume_col,
                y=display_col,
                orientation="h",
                title="Top 20 Events by Volume",
                labels={volume_col: "Volume (USD)", display_col: "Event"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
            st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_events(
    limit={limit},
    closed={closed},
    featured={featured},
    expand_markets={expand_markets},
    expand_clob_token_ids={expand_tokens},
)
print(df)
""",
        language="python",
    )
