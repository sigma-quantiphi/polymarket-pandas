"""Tags explorer page."""

from __future__ import annotations

import streamlit as st


def _tri(x):
    return {None: "Default", True: "Yes", False: "No"}[x]


st.set_page_config(page_title="Tags", layout="wide")
st.title("Tags")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Filters ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Filters")
    limit = st.number_input(
        "Limit", min_value=1, max_value=500, value=300, key="tags_limit"
    )
    offset = st.number_input("Offset", min_value=0, value=0, step=10, key="tags_offset")

    with st.expander("Sorting"):
        order = st.text_input("Order by (comma-separated fields)", key="tags_order")
        ascending = st.selectbox(
            "Ascending",
            [None, True, False],
            format_func=_tri,
            key="tags_asc",
        )

    with st.expander("Advanced"):
        include_template = st.selectbox(
            "Include template",
            [None, True, False],
            format_func=_tri,
            key="tags_template",
        )
        is_carousel = st.selectbox(
            "Is carousel",
            [None, True, False],
            format_func=_tri,
            key="tags_carousel",
        )

# ── Build kwargs ─────────────────────────────────────────────────────────────

kwargs: dict = {
    "limit": limit,
    "offset": offset if offset > 0 else None,
    "order": [s.strip() for s in order.split(",") if s.strip()] or None,
    "ascending": ascending,
    "include_template": include_template,
    "is_carousel": is_carousel,
}

active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching tags..."):
    try:
        df = client.get_tags(**active_kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()

st.metric("Tags returned", len(df))

if df.empty:
    st.warning("No tags found.")
    st.stop()

# ── Data table ───────────────────────────────────────────────────────────────

st.subheader("Data")
st.dataframe(df, width="stretch", height=400)

# ── Visualization ────────────────────────────────────────────────────────────

if not df.empty:
    import plotly.express as px

    # Show tag event counts if available
    count_col = None
    for candidate in ["eventCount", "eventsCount", "count", "numEvents"]:
        if candidate in df.columns:
            count_col = candidate
            break

    label_col = None
    for candidate in ["label", "slug", "name"]:
        if candidate in df.columns:
            label_col = candidate
            break

    if count_col and label_col:
        st.subheader("Tags by Event Count")
        chart_df = df.dropna(subset=[count_col]).copy()
        chart_df[count_col] = chart_df[count_col].astype(float)
        top = chart_df.nlargest(30, count_col)
        fig = px.bar(
            top,
            x=count_col,
            y=label_col,
            orientation="h",
            title="Top 30 Tags by Event Count",
            labels={count_col: "Events", label_col: "Tag"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=700)
        st.plotly_chart(fig, use_container_width=True)

# ── Code snippet ─────────────────────────────────────────────────────────────

with st.expander("View Code"):
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_tags(
    {args_str},
)
print(df)
""",
        language="python",
    )
