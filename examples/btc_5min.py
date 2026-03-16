"""
BTC 5-Minute Up/Down — Orderbook + Live Trades

Finds the current BTC 5-minute binary market on Polymarket via series lookup,
pulls the orderbook snapshot for both outcomes (Up / Down), then opens a
WebSocket stream for real-time book updates and trade prints.

Requirements:
    pip install polymarket-pandas

Usage:
    python examples/btc_5min.py
"""

from __future__ import annotations

import signal
import sys

import pandas as pd

from polymarket_pandas import PolymarketPandas, PolymarketWebSocket

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 160)

# ── 1. Find the current BTC 5-min market ────────────────────────────────────

client = PolymarketPandas()
now = pd.Timestamp.now(tz="UTC")

# Find the BTC 5-min series, get the soonest active event
series = client.get_series(
    slug="btc-up-or-down-5m",
    expand_events=True,
    closed=False,
)
series = series.loc[series["eventsEndDate"] >= now].sort_values(
    "eventsEndDate", ignore_index=True
)
if series.empty:
    print("No active BTC 5-min events found.")
    sys.exit(1)

event_slug = series["eventsSlug"].iloc[0]
print(f"Event: {event_slug}")

# Get event details with markets
events = client.get_events(slug=[event_slug])

# Get markets with exploded token IDs
markets = client.get_markets(
    slug=events["marketsSlug"].tolist(),
    expand_clob_token_ids=True,
    expand_events=False,
    expand_series=False,
)
if markets.empty:
    print("No active BTC 5-min markets found. Market may be between windows.")
    sys.exit(1)

# Sort by endDate, deduplicate token IDs, explode outcomes for display
current = (
    markets.sort_values("endDate")
    .drop_duplicates(subset=["clobTokenIds"])
    .explode(["outcomes", "outcomePrices"])
)

asset_ids = current["clobTokenIds"].unique().tolist()

print(f"\n{'='*60}")
print(current[["question", "endDate", "conditionId", "clobTokenIds", "outcomes", "outcomePrices"]].to_string(index=False))

# ── 2. REST snapshot: orderbook + recent trades ─────────────────────────────

print(f"\n{'='*60}")
print("Orderbook Snapshot")
print("=" * 60)

for tid in asset_ids:
    book = client.get_orderbook(token_id=tid)
    print(f"  Book:\n{book}")
    spread = client.get_spread(token_id=tid)
    mid = client.get_midpoint_price(tid)
    print(f"  Midpoint: {mid:.4f}  Spread: {spread:.4f}")

print(f"\n{'='*60}")
print("Recent Trades")
print("=" * 60)

event_id = events["id"].iloc[0]
trades = client.get_trades(eventId=[event_id], limit=20)
if not trades.empty:
    print(trades.reindex(columns=["timestamp", "side", "price", "size"]))
else:
    print("(no recent trades)")

# ── 3. WebSocket: live book + trade stream ──────────────────────────────────

print(f"\n{'='*60}")
print("Streaming live updates (Ctrl+C to quit) ...")
print("=" * 60)

ws = PolymarketWebSocket.from_client(client)


def on_book(df: pd.DataFrame) -> None:
    print(f"  [BOOK]  {df.dropna(how='all', axis=1)}")


def on_price_change(df: pd.DataFrame) -> None:
    print(f"  [PRICE] {df.dropna(how='all', axis=1)}")


def on_last_trade_price(df: pd.DataFrame) -> None:
    print(f"  [TRADE] {df.dropna(how='all', axis=1)}")


def on_best_bid_ask(df: pd.DataFrame) -> None:
    print(f"  [BBA]   {df.dropna(how='all', axis=1)}")


session = ws.market_channel(
    asset_ids=asset_ids,
    on_book=on_book,
    on_price_change=on_price_change,
    on_last_trade_price=on_last_trade_price,
    on_best_bid_ask=on_best_bid_ask,
    initial_dump=True,
    level=2,
    custom_feature_enabled=True,
)


def _shutdown(_sig, _frame):
    print("\nShutting down ...")
    session.close()
    client.close()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)

session.run_forever()
