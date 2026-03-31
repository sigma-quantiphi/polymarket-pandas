"""
Async Client — Fetch User Trades & Active Orders

Initializes AsyncPolymarketPandas, derives API keys from your private key,
and fetches your recent trades and active orders.

Requires environment variables (or a .env file):
    POLYMARKET_PRIVATE_KEY

Usage:
    python examples/async_trades_orders.py
"""

from __future__ import annotations

import asyncio

import pandas as pd
from dotenv import load_dotenv

from polymarket_pandas import AsyncPolymarketPandas

load_dotenv()
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


async def main():
    async with AsyncPolymarketPandas() as client:
        creds = await client.derive_api_key()
        print(f"API key derived: {creds['apiKey'][:8]}...\n")

        # Fetch user trades and active orders concurrently
        trades_result, orders_result = await asyncio.gather(
            client.get_user_trades(),
            client.get_active_orders(),
        )

        # User trades
        trades = trades_result["data"]
        print("=== USER TRADES ===")
        cols = ["side", "size", "price", "status", "outcome", "matchTime"]
        print(trades[cols].head(10).to_string())
        print(f"\n({len(trades)} rows)\n")

        # Active orders
        orders = orders_result["data"]
        print("=== ACTIVE ORDERS ===")
        if orders.empty:
            print("(none)")
        else:
            cols = ["side", "originalSize", "price", "status", "outcome", "createdAt"]
            print(orders[cols].to_string())
        print(f"\n({len(orders)} rows)")


if __name__ == "__main__":
    asyncio.run(main())
