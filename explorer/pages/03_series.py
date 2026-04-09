"""Series explorer page."""

from __future__ import annotations

import streamlit as st


def _tri(x):
    return {None: "Default", True: "Yes", False: "No"}[x]


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
    limit = st.number_input(
        "Limit", min_value=1, max_value=500, value=100, key="series_limit"
    )
    offset = st.number_input(
        "Offset", min_value=0, value=0, step=10, key="series_offset"
    )
    closed = st.selectbox(
        "Status",
        [None, False, True],
        format_func=lambda x: {None: "All", False: "Open", True: "Closed"}[x],
        key="series_closed",
    )

    st.subheader("Expansion")
    expand_events = st.checkbox(
        "Expand events", value=False, key="series_expand_events"
    )
    expand_event_tags = st.checkbox(
        "Expand event tags", value=False, key="series_expand_tags"
    )

    with st.expander("Sorting"):
        order = st.text_input("Order by (comma-separated fields)", key="ser_order")
        ascending = st.selectbox(
            "Ascending", [None, True, False], format_func=_tri, key="ser_asc"
        )

    with st.expander("Lookup / Categories"):
        slug_input = st.text_input("Slugs (comma-separated)", key="ser_slugs")
        categories_ids = st.text_input(
            "Category IDs (comma-separated)", key="ser_cat_ids"
        )
        categories_labels = st.text_input(
            "Category labels (comma-separated)", key="ser_cat_labels"
        )

    with st.expander("Advanced"):
        include_chat = st.selectbox(
            "Include chat", [None, True, False], format_func=_tri, key="ser_chat"
        )
        recurrence = st.selectbox(
            "Recurrence", [None, "daily", "weekly", "monthly"], key="ser_recurrence"
        )

# ── Build kwargs ─────────────────────────────────────────────────────────────

kwargs: dict = {
    "limit": limit,
    "offset": offset if offset > 0 else None,
    "closed": closed,
    "expand_events": expand_events,
    "expand_event_tags": expand_event_tags,
    "order": [s.strip() for s in order.split(",") if s.strip()] or None,
    "ascending": ascending,
    "slug": [s.strip() for s in slug_input.split(",") if s.strip()] or None,
    "categories_ids": [int(s.strip()) for s in categories_ids.split(",") if s.strip()]
    or None,
    "categories_labels": [s.strip() for s in categories_labels.split(",") if s.strip()]
    or None,
    "include_chat": include_chat,
    "recurrence": recurrence,
}

active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching series..."):
    try:
        df = client.get_series(**active_kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Rows returned", len(df))

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="stretch", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

if not df.empty and expand_events:
    st.subheader("Series -> Events Hierarchy")
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
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_series(
    {args_str},
)
print(df)
""",
        language="python",
    )
