"""
Post-Only Buy — Place a resting 1¢ buy order with post_only=True

Loads the "Will Bitcoin reach $80,000 by December 31, 2026?" market and
places a post-only BUY order on the Yes token at $0.01. Post-only means
the matching engine will reject the order if it would cross the book and
fill immediately — guaranteeing it rests as a maker.

Requires environment variables (or a .env file):
    POLYMARKET_ADDRESS
    POLYMARKET_PRIVATE_KEY
    POLYMARKET_API_KEY
    POLYMARKET_API_SECRET
    POLYMARKET_API_PASSPHRASE

Usage:
    python examples/post_only_buy.py
"""

from __future__ import annotations

import sys

import pandas as pd
from dotenv import load_dotenv

from polymarket_pandas import PolymarketPandas

load_dotenv()
pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)

MARKET_SLUG = "will-bitcoin-reach-80000-by-december-31-2026-195-842-488-785"


def main() -> None:
    client = PolymarketPandas()
    print(f"Connected as {client.address}")

    # ── 1. Load the market ────────────────────────────────────────────
    markets = client.get_markets(
        slug=MARKET_SLUG,
        expand_clob_token_ids=True,
    )
    if markets.empty:
        print(f"No market found for slug {MARKET_SLUG!r}")
        sys.exit(1)

    # expand_clob_token_ids explodes tokens but leaves `outcomes` as a list
    # aligned by position: row 0 = Yes token, row 1 = No token.
    yes_row = markets.iloc[0]
    assert yes_row["outcomes"][0] == "Yes", f"Unexpected outcomes: {yes_row['outcomes']}"

    token_id = yes_row["clobTokenIds"]
    tick_size = yes_row["orderPriceMinTickSize"]
    min_size = yes_row["orderMinSize"]
    neg_risk = yes_row["negRisk"]

    print(f"Market:     {yes_row['question']}")
    print(f"Yes token:  {token_id}")
    print(f"Tick size:  {tick_size}")
    print(f"Min size:   {min_size}")
    print(f"Neg-risk:   {neg_risk}")

    # ── 2. Place a post-only BUY at 1¢ ────────────────────────────────
    price = 0.01
    # Respect the market's min order size; 1¢ * min_size must also clear
    # the notional minimum (Polymarket requires ~$1 notional for buys, so
    # size at 1¢ needs to be at least 100 shares).
    size = max(min_size, 100)

    print(f"\nPlacing post-only BUY {size} @ ${price:.2f} ...")
    resp = client.submit_order(
        token_id=token_id,
        price=0.8,
        size=size,
        side="BUY",
        order_type="GTC",
        post_only=True,
    )
    print(f"Response: {resp}")

    client.close()


if __name__ == "__main__":
    main()
