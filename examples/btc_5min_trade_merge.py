"""
BTC 5-Minute Up/Down — Buy Both Sides + Merge

End-to-end trading flow on a BTC 1d binary market:
  1. Find the current active BTC 1d Up/Down market
  2. Buy minimum amount of "Up" (Yes) at market price (FOK)
  3. Buy minimum amount of "Down" (No) at market price (FOK)
  4. Read back recent user trades
  5. Merge the Yes + No tokens back into USDC.e

Requirements:
    pip install "polymarket-pandas[ctf]"

Create a .env file (see .env.example) with:
    POLYMARKET_ADDRESS          — Polymarket proxy wallet address
    POLYMARKET_PRIVATE_KEY      — EOA private key (signs orders + CTF txs)
    POLYMARKET_API_KEY          — CLOB L2 API key
    POLYMARKET_API_SECRET       — CLOB L2 secret
    POLYMARKET_API_PASSPHRASE   — CLOB L2 passphrase
    POLYMARKET_RPC_URL          — Polygon RPC (default: https://polygon-rpc.com)

Usage:
    python examples/btc_5min_trade_merge.py
"""

from __future__ import annotations

import sys

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from polymarket_pandas import PolymarketPandas
from polymarket_pandas.mixins._ctf import CONDITIONAL_TOKENS, NEG_RISK_ADAPTER

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)


def main() -> None:
    client = PolymarketPandas()
    print(f"Connected to {client}")

    # ── 1. Find the current BTC 1d market ─────────────────────────────

    print("Finding active BTC 1d market ...")
    now = pd.Timestamp.now(tz="UTC")
    series = client.get_series(
        slug="btc-up-or-down-daily",
        expand_events=True,
        closed=False,
    )
    series = series.loc[series["eventsEndDate"] >= now].sort_values(
        "eventsEndDate", ignore_index=True
    )
    if series.empty:
        print("No active BTC 1d events found.")
        sys.exit(1)

    event_slug = series["eventsSlug"].iloc[0]
    events = client.get_events(slug=[event_slug])
    markets = client.get_markets(
        slug=events["marketsSlug"].tolist(),
        expand_clob_token_ids=False,
        expand_events=False,
        expand_series=False,
    )
    if markets.empty:
        print("No active BTC 1d markets found. Between windows?")
        sys.exit(1)

    # Explode all three list columns together so token IDs align with outcomes
    current = (
        markets.sort_values("endDate")
        .explode(["clobTokenIds", "outcomes", "outcomePrices"])
        .drop_duplicates(subset=["clobTokenIds", "outcomes"])
        .reset_index(drop=True)
    )
    current['outcomePrices'] = pd.to_numeric(current['outcomePrices'])

    up_row = current.loc[current["outcomes"] == "Up"].iloc[0]
    down_row = current.loc[current["outcomes"] == "Down"].iloc[0]

    condition_id = up_row["conditionId"]
    min_size = up_row["orderMinSize"]
    tick_size = up_row["orderPriceMinTickSize"]
    neg_risk = up_row["negRisk"]

    print(f"Market:       {up_row['question']}")
    print(f"Condition ID: {condition_id}")
    print(f"Neg-risk:     {neg_risk}")
    print(f"Tick size:    {tick_size}")
    print(f"Up  token:    {up_row['clobTokenIds']}  bid/ask {up_row['bestBid']:.2f}/{up_row['bestAsk']:.2f}")
    print(f"Down token:   {down_row['clobTokenIds']}  bid/ask {down_row['bestBid']:.2f}/{down_row['bestAsk']:.2f}")

    # ── 4. Read user trades ──────────────────────────────────────────────
    print("\nRecent user trades:")
    trades = client.get_user_trades()
    if not trades.empty:
        print(trades)
    else:
        print("(no trades yet)")

    # ── 2. Buy "Up" (Yes) at market price (FOK) ─────────────────────────

    up_price = up_row["outcomePrices"] + tick_size
    print(f"\nBuying {min_size} Up @ ${up_price:.2f} (FOK) ...")
    up_resp = client.submit_order(
        token_id=up_row["clobTokenIds"],
        price=up_price,
        size=min_size,
        side="BUY",
        order_type="GTC",
        neg_risk=neg_risk,
        tick_size=str(tick_size),
    )
    print(f"Up buy response: {up_resp}")

    # ── 3. Buy "Down" (No) at market price (FOK) ────────────────────────
    down_price = down_row["outcomePrices"] - tick_size
    print(f"\nBuying {min_size} Down @ ${down_price:.2f} (FOK) ...")
    down_resp = client.submit_order(
        token_id=down_row["clobTokenIds"],
        price=down_price,
        size=min_size,
        side="BUY",
        order_type="GTC",
        neg_risk=neg_risk,
        tick_size=str(tick_size),
    )
    print(f"Down buy response: {down_resp}")

    # ── 5. Merge Yes + No tokens back into USDC.e ────────────────────────
    spender = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
    print(f"\nApproving USDC.e for {spender[:10]}... (if needed)")
    client.approve_collateral(spender=spender)

    merge_amount = int(min_size * 1e6)
    print(f"Merging {merge_amount} base units ...")
    merge_result = client.merge_positions(
        condition_id=condition_id,
        amount=merge_amount,
        neg_risk=neg_risk,
    )
    print(f"Merge tx: {merge_result}")

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
