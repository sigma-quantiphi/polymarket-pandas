"""
BTC 5-Minute Up/Down — Submit Orders, Cancel, Buy + Merge

End-to-end trading flow on a BTC 1d binary market:
  1. Find the current active BTC 1d Up/Down market
  2. Submit limit orders for both sides at min price via submit_orders (DataFrame)
  3. Sleep 30s, then cancel the limit orders
  4. Buy minimum "Up" at market price via submit_order
  5. Buy minimum "Down" at market price via submit_order
  6. Read back recent user trades
  7. Merge the Yes + No tokens back into USDC.e

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
import time

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
    current["outcomePrices"] = pd.to_numeric(current["outcomePrices"])

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
    print(f"Up  token:    {up_row['clobTokenIds']}  price={up_row['outcomePrices']:.3f}")
    print(f"Down token:   {down_row['clobTokenIds']}  price={down_row['outcomePrices']:.3f}")

    # ── 2. Submit limit orders at min price via DataFrame ──────────────
    #   Place cheap limit orders (unlikely to fill) to demo submit_orders.

    up_limit = tick_size  # lowest possible price
    down_limit = tick_size

    orders_df = pd.DataFrame(
        {
            "token_id": [up_row["clobTokenIds"], down_row["clobTokenIds"]],
            "price": [up_limit, down_limit],
            "size": [min_size, min_size],
            "side": ["BUY", "BUY"],
        }
    )
    print("\n── Submitting limit orders via submit_orders(DataFrame) ──")
    print(orders_df.to_string(index=False))
    limit_resp = client.submit_orders(orders_df)
    print(f"Responses:\n{limit_resp}")

    # ── 3. Sleep 30s, then cancel all orders on this market ──────────

    print("\nSleeping 30s before cancelling ...")
    time.sleep(30)
    print("Cancelling all orders on Up + Down tokens ...")
    resp = client.cancel_orders_from_market(market=condition_id)
    print(resp)

    # ── 4. Buy "Up" (Yes) at market price ──────────────────────────────

    up_price = up_row["outcomePrices"] + tick_size
    print(f"\nBuying {min_size} Up @ ${up_price:.3f} ...")
    up_resp = client.submit_order(
        token_id=up_row["clobTokenIds"],
        price=up_price,
        size=min_size,
        side="BUY",
        order_type="GTC",
    )
    print(f"Up buy response: {up_resp}")

    # ── 5. Buy "Down" (No) at market price ─────────────────────────────

    down_price = down_row["outcomePrices"] + tick_size
    print(f"\nBuying {min_size} Down @ ${down_price:.3f} ...")
    down_resp = client.submit_order(
        token_id=down_row["clobTokenIds"],
        price=down_price,
        size=min_size,
        side="BUY",
        order_type="GTC",
    )
    print(f"Down buy response: {down_resp}")

    # ── 6. Read user trades ────────────────────────────────────────────

    print("\nRecent user trades:")
    result = client.get_user_trades()
    trades = result["data"]
    if not trades.empty:
        print(trades)
    else:
        print("(no trades yet)")

    # ── 7. Merge Yes + No tokens back into USDC.e ─────────────────────
    #   Can only merge the minimum of the two positions (need equal amounts).

    merge_shares = min_size
    merge_amount = int(merge_shares * 1e6)

    spender = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
    print(f"\nApproving USDC.e for {spender[:10]}... (if needed)")
    client.approve_collateral(spender=spender)

    print(f"Merging {merge_shares} shares ({merge_amount} base units) ...")
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
