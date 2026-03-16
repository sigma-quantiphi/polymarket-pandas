"""
RTDS WebSocket — Live Crypto Prices

Connects to the Polymarket RTDS (Real-Time Data Service) WebSocket and prints
live crypto price updates from Binance and Chainlink feeds.

No credentials required.

Usage:
    python examples/rtds_ws.py
"""

from __future__ import annotations

import json
import signal
import sys

import pandas as pd

from polymarket_pandas import PolymarketPandas, PolymarketWebSocket

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)

# ── Connect ──────────────────────────────────────────────────────────────────

client = PolymarketPandas()
ws = PolymarketWebSocket.from_client(client)

# ── Callbacks ────────────────────────────────────────────────────────────────


def on_crypto_prices(df: pd.DataFrame) -> None:
    print(f"  [BINANCE]   {df}")


def on_crypto_prices_chainlink(df: pd.DataFrame) -> None:
    print(f"  [CHAINLINK] {df}")


def on_comment(comment: dict) -> None:
    print(f"  [COMMENT]   {comment}")


# ── Start ────────────────────────────────────────────────────────────────────

# Subscribe to crypto price feeds and comments
subscriptions = [
    # {
    #     "topic": "crypto_prices",
    #     "type": "update",
    #     "filters": ",".join(["solusdt", "btcusdt", "ethusdt"]),
    #     "filters": ["solusdt", "btcusdt", "ethusdt"],
    # },
    {
        "topic": "crypto_prices_chainlink",
        "type": "*",
        "filters": json.dumps({"symbol": "eth/usd"})
    },
    # {
    #     "topic": "comments",
    #     "type": "comment_created"
    # },
]

print("Listening for RTDS updates (Ctrl+C to quit) ...")
print("  Subscriptions:", [s["topic"] for s in subscriptions])

session = ws.rtds_channel(
    subscriptions=subscriptions,
    on_crypto_prices=on_crypto_prices,
    on_crypto_prices_chainlink=on_crypto_prices_chainlink,
    on_comment=on_comment,
)


def _shutdown(_sig, _frame):
    print("\nShutting down ...")
    session.close()
    client.close()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
session.run_forever()
