"""Events explorer page."""

from __future__ import annotations

import streamlit as st


def _tri(x):
    return {None: "Default", True: "Yes", False: "No"}[x]

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
    offset = st.number_input("Offset", min_value=0, value=0, step=10, key="events_offset")
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

    st.subheader("Expansion")
    expand_markets = st.checkbox("Expand markets", value=True, key="events_expand_markets")
    expand_tokens = st.checkbox("Expand CLOB token IDs", value=True, key="events_expand_tokens")

    with st.expander("Date Range"):
        start_date_min = st.date_input("Start date min", value=None, key="ev_sd_min")
        start_date_max = st.date_input("Start date max", value=None, key="ev_sd_max")
        end_date_min = st.date_input("End date min", value=None, key="ev_ed_min")
        end_date_max = st.date_input("End date max", value=None, key="ev_ed_max")

    with st.expander("Sorting"):
        order = st.text_input("Order by (comma-separated fields)", key="ev_order")
        ascending = st.selectbox("Ascending", [None, True, False],
                                 format_func=_tri,
                                 key="ev_asc")

    with st.expander("Lookup / Tags"):
        slug_input = st.text_input("Slugs (comma-separated)", key="ev_slugs")
        tag_id = st.number_input("Tag ID", min_value=0, value=0, step=1, key="ev_tag_id",
                                 help="0 = no filter")
        exclude_tag_ids = st.text_input("Exclude tag IDs (comma-separated)", key="ev_excl_tags")
        related_tags = st.selectbox("Related tags", [None, True, False],
                                    format_func=_tri,
                                    key="ev_related_tags")

    with st.expander("Advanced"):
        cyom = st.selectbox("CYOM", [None, True, False],
                            format_func=_tri,
                            key="ev_cyom")
        include_chat = st.selectbox("Include chat", [None, True, False],
                                    format_func=_tri,
                                    key="ev_chat")
        include_template = st.selectbox("Include template", [None, True, False],
                                        format_func=_tri,
                                        key="ev_template")
        recurrence = st.selectbox("Recurrence", [None, "daily", "weekly", "monthly"],
                                  key="ev_recurrence")

# ── Build kwargs ─────────────────────────────────────────────────────────────

kwargs: dict = {
    "limit": limit,
    "offset": offset if offset > 0 else None,
    "closed": closed,
    "featured": featured,
    "expand_markets": expand_markets,
    "expand_clob_token_ids": expand_tokens,
    "start_date_min": str(start_date_min) if start_date_min else None,
    "start_date_max": str(start_date_max) if start_date_max else None,
    "end_date_min": str(end_date_min) if end_date_min else None,
    "end_date_max": str(end_date_max) if end_date_max else None,
    "order": [s.strip() for s in order.split(",") if s.strip()] or None,
    "ascending": ascending,
    "slug": [s.strip() for s in slug_input.split(",") if s.strip()] or None,
    "tag_id": tag_id if tag_id > 0 else None,
    "exclude_tag_id": [int(s.strip()) for s in exclude_tag_ids.split(",") if s.strip()] or None,
    "related_tags": related_tags,
    "cyom": cyom,
    "include_chat": include_chat,
    "include_template": include_template,
    "recurrence": recurrence,
}

active_kwargs = {k: v for k, v in kwargs.items() if v is not None}

# ── Fetch data ───────────────────────────────────────────────────────────────

with st.spinner("Fetching events..."):
    try:
        df = client.get_events(**active_kwargs)
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
    args_str = ",\n    ".join(f"{k}={v!r}" for k, v in active_kwargs.items())
    st.code(
        f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_events(
    {args_str},
)
print(df)
""",
        language="python",
    )
