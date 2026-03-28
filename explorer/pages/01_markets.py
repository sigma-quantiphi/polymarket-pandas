"""Markets explorer page."""

from __future__ import annotations

import streamlit as st

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
    volume_min = st.number_input("Min volume", min_value=0.0, value=0.0, step=1000.0)
    closed = st.selectbox("Status", [None, False, True], format_func=lambda x: {None: "All", False: "Open", True: "Closed"}[x])
    expand_events = st.checkbox("Expand events", value=True)
    expand_series = st.checkbox("Expand series", value=True)
    expand_tokens = st.checkbox("Expand CLOB token IDs", value=True)

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching markets..."):
    try:
        df = client.get_markets(
            limit=limit,
            volume_num_min=volume_min if volume_min > 0 else None,
            closed=closed,
            expand_events=expand_events,
            expand_series=expand_series,
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
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_markets(
    limit={limit},
    volume_num_min={volume_min if volume_min > 0 else None},
    closed={closed},
    expand_events={expand_events},
    expand_series={expand_series},
    expand_clob_token_ids={expand_tokens},
)
print(df)
""",
        language="python",
    )
