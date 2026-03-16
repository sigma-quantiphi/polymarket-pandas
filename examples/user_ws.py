"""
User WebSocket — Live Fills + Order Updates

Connects to the Polymarket user WebSocket channel and prints your trade
fills and order status updates in real time.

Requires L2 credentials set as environment variables:
    POLYMARKET_API_KEY
    POLYMARKET_API_SECRET
    POLYMARKET_API_PASSPHRASE

Usage:
    python examples/user_ws.py                           # all markets
    python examples/user_ws.py 0xcondition1 0xcondition2 # specific markets
"""

from __future__ import annotations

import signal
import sys

import pandas as pd

from polymarket_pandas import PolymarketPandas, PolymarketWebSocket

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)

# ── Connect ──────────────────────────────────────────────────────────────────

client = PolymarketPandas()
ws = PolymarketWebSocket.from_client(client)

if not ws.api_key:
    print("Missing credentials. Set POLYMARKET_API_KEY, POLYMARKET_API_SECRET,")
    print("and POLYMARKET_API_PASSPHRASE environment variables.")
    sys.exit(1)

# Optional: pass condition IDs as CLI args to filter specific markets
condition_ids = sys.argv[1:] if len(sys.argv) > 1 else []

# ── Callbacks ────────────────────────────────────────────────────────────────


def on_trade(df: pd.DataFrame) -> None:
    print(f"  [FILL]  {df.dropna(how='all', axis=1)}")


def on_order(df: pd.DataFrame) -> None:
    print(f"  [ORDER] {df.dropna(how='all', axis=1)}")


# ── Start ────────────────────────────────────────────────────────────────────

print("Listening for user updates (Ctrl+C to quit) ...")
if condition_ids:
    print(f"  Markets: {condition_ids}")
else:
    print("  All markets")

session = ws.user_channel(
    markets=condition_ids,
    on_trade=on_trade,
    on_order=on_order,
)


def _shutdown(_sig, _frame):
    print("\nShutting down ...")
    session.close()
    client.close()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)

session.run_forever()
