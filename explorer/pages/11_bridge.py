"""Bridge explorer page."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Bridge", layout="wide")
st.title("Bridge")

get_client = st.session_state.get("get_client")
if not get_client:
    st.error("Navigate to the Home page first to initialize the client.")
    st.stop()

client = get_client()

# ── Supported Assets ─────────────────────────────────────────────────────────

st.subheader("Supported Assets")

with st.spinner("Fetching supported assets..."):
    try:
        assets = client.get_bridge_supported_assets()
    except Exception as e:
        st.error(f"API error: {e}")
        assets = []

if assets:
    import pandas as pd

    # Flatten the nested structure for display
    rows = []
    for asset in assets:
        if isinstance(asset, dict):
            rows.append(asset)
        else:
            rows.append({"asset": asset})
    df_assets = pd.DataFrame(rows)
    st.dataframe(df_assets, width="stretch", height=300)
else:
    st.warning("No supported assets returned.")

with st.expander("View Code"):
    st.code(
        """\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
assets = client.get_bridge_supported_assets()
print(assets)
""",
        language="python",
    )

# ── Transaction Status ───────────────────────────────────────────────────────

st.subheader("Transaction Status")

bridge_addr = st.text_input(
    "Bridge address",
    placeholder="Address returned by create_deposit_address or create_withdrawal_address",
    key="bridge_addr",
)

if bridge_addr:
    with st.spinner("Fetching transaction status..."):
        try:
            df_tx = client.get_bridge_transaction_status(bridge_addr)
        except Exception as e:
            st.error(f"API error: {e}")
            df_tx = None

    if df_tx is not None:
        st.metric("Transactions", len(df_tx))
        if not df_tx.empty:
            st.dataframe(df_tx, width="stretch", height=300)
        else:
            st.info("No transactions found for this address.")

    with st.expander("View Code"):
        st.code(
            f"""\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
df = client.get_bridge_transaction_status("{bridge_addr}")
print(df)
""",
            language="python",
        )

# ── Bridge Quote ─────────────────────────────────────────────────────────────

st.subheader("Bridge Quote")
st.caption("Get a price quote for bridging assets to/from Polymarket.")

with st.expander("View Code"):
    st.code(
        """\
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas()
quote = client.get_bridge_quote(
    from_amount_base_unit="1000000",  # 1 USDC (6 decimals)
    from_chain_id="1",                # Ethereum mainnet
    from_token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC
    recipient_address="0xYourAddress...",
    to_chain_id="137",                # Polygon
    to_token_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",    # USDC.e
)
print(quote)
""",
        language="python",
    )
