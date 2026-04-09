"""
Rewards Overview — Query all seven CLOB rewards endpoints

Prints the result of every method on RewardsMixin:
  Public:
    1. get_rewards_markets_current     — all active reward configs
    2. get_rewards_markets_multi       — markets sorted by rate_per_day
    3. get_rewards_market              — reward config for a specific market
  Private (L2 auth):
    4. get_rewards_earnings            — per-market earnings on a date
    5. get_rewards_earnings_total      — daily total grouped by asset
    6. get_rewards_percentages         — live share of each market's pool
    7. get_rewards_user_markets        — earnings joined with market config

Requires environment variables (or a .env file):
    POLYMARKET_ADDRESS
    POLYMARKET_API_KEY
    POLYMARKET_API_SECRET
    POLYMARKET_API_PASSPHRASE

Usage:
    python examples/rewards_overview.py
    python examples/rewards_overview.py 2026-04-07   # query a specific date
"""

from __future__ import annotations

import sys

import pandas as pd
from dotenv import load_dotenv

from polymarket_pandas import PolymarketPandas

load_dotenv()
pd.set_option("display.max_columns", 12)
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 15)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    client = PolymarketPandas()
    date = (
        sys.argv[1]
        if len(sys.argv) > 1
        else pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    )
    print(f"Address: {client.address}")
    print(f"Date:    {date}")

    # ── 1. Current active reward configs ──────────────────────────────
    section("1. get_rewards_markets_current()")
    current = client.get_rewards_markets_current(expand_rewards_config=True)
    print(f"count={current['count']} next_cursor={current['next_cursor']}")
    print(current["data"])
    print(current["data"].dtypes.to_string())

    # ── 2. Markets sorted by daily reward rate ────────────────────────
    section("2. get_rewards_markets_multi(order_by='rate_per_day', position='DESC')")
    multi = client.get_rewards_markets_multi(
        order_by="rate_per_day",
        position="DESC",
        page_size=10,
        expand_rewards_config=True,
    )
    print(f"count={multi['count']} next_cursor={multi['next_cursor']}")
    print(multi["data"])
    print(multi["data"].dtypes.to_string())

    # Pick a condition_id to drill into for the single-market call.
    top = multi["data"]
    if top.empty:
        print("\nNo rewarded markets returned; skipping single-market call.")
        condition_id = None
    else:
        condition_id = top["conditionId"].iloc[0]

    # ── 3. Reward config for a specific market ────────────────────────
    section(f"3. get_rewards_market(condition_id={condition_id!r})")
    if condition_id:
        single = client.get_rewards_market(
            condition_id=condition_id,
            expand_rewards_config=True,
            expand_tokens=True,
        )
        print(f"count={single['count']} next_cursor={single['next_cursor']}")
        print(single["data"])
        print(single["data"].dtypes.to_string())
    else:
        print("(skipped — no condition_id available)")

    # Private endpoints require signature_type + maker_address to be
    # passed explicitly (the CLOB doesn't infer them from L2 auth).
    sig_type = 1  # POLY_PROXY
    maker = client.address

    # ── 4. Per-market earnings on the given date ──────────────────────
    section(f"4. get_rewards_earnings(date={date!r})")
    earnings = client.get_rewards_earnings(
        date=date, signature_type=sig_type, maker_address=maker
    )
    print(f"count={earnings['count']} next_cursor={earnings['next_cursor']}")
    print(earnings["data"])
    print(earnings["data"].dtypes.to_string())

    # ── 5. Daily total grouped by asset ───────────────────────────────
    section(f"5. get_rewards_earnings_total(date={date!r})")
    total = client.get_rewards_earnings_total(
        date=date, signature_type=sig_type, maker_address=maker
    )
    print(total)
    print(total.dtypes.to_string())

    # ── 6. Real-time reward percentages per market ────────────────────
    section("6. get_rewards_percentages()")
    pct = client.get_rewards_percentages(signature_type=sig_type, maker_address=maker)
    if pct:
        pct_df = pd.DataFrame(
            sorted(pct.items(), key=lambda kv: kv[1], reverse=True),
            columns=["conditionId", "percentage"],
        )
        print(pct_df)
        print(pct_df.dtypes.to_string())
    else:
        print("(no active maker positions in rewarded markets)")

    # ── 7. User earnings joined with market config ────────────────────
    section(f"7. get_rewards_user_markets(date={date!r}, order_by='earnings')")
    user_markets = client.get_rewards_user_markets(
        date=date,
        signature_type=sig_type,
        maker_address=maker,
        order_by="earnings",
        position="DESC",
        page_size=100,
        expand_earnings=True,
        expand_tokens=True,
        expand_rewards_config=True,
    )
    print(f"count={user_markets['count']} next_cursor={user_markets['next_cursor']}")
    print(user_markets["data"])
    print(user_markets["data"].dtypes.to_string())
    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
