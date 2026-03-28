"""Series explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Series", layout="wide")
st.title("Series")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Filters")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=100, key="series_limit")
    closed = st.selectbox(
        "Status",
        [None, False, True],
        format_func=lambda x: {None: "All", False: "Open", True: "Closed"}[x],
        key="series_closed",
    )
    expand_events = st.checkbox("Expand events", value=False, key="series_expand_events")

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching series..."):
    try:
        df = client.get_series(
            limit=limit,
            closed=closed,
            expand_events=expand_events,
        )
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Rows returned", len(df))

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, use_container_width=True, height=400)

# ── Visualization ────────────────────────────────────────────────────────────

if not df.empty and expand_events:
    st.subheader("Series → Events Hierarchy")
    title_col = "title" if "title" in df.columns else "slug"
    event_col = None
    for candidate in ["eventsTitle", "eventsSlug"]:
        if candidate in df.columns:
            event_col = candidate
            break
    if title_col in df.columns and event_col:
        import plotly.express as px

        counts = df.groupby(title_col, as_index=False)[event_col].nunique()
        counts = counts.rename(columns={event_col: "eventCount"})
        top = counts.nlargest(20, "eventCount")
        fig = px.bar(
            top,
            x="eventCount",
            y=title_col,
            orientation="h",
            title="Top 20 Series by Number of Events",
            labels={"eventCount": "Events", title_col: "Series"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_series(
    limit={limit},
    closed={closed},
    expand_events={expand_events},
)
print(df)
""",
        language="python",
    )
