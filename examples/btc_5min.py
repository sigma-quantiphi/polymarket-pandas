"""
BTC 5-Minute Up/Down — Orderbook + Live Trades

Finds the active BTC 5-minute binary market on Polymarket, pulls the
current orderbook snapshot for both outcomes (Up / Down), then opens a
WebSocket stream for real-time book updates and trade prints.

Requirements:
    pip install polymarket-pandas python-dotenv

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

# ── 1. Find the BTC 5-min market ────────────────────────────────────────────

client = PolymarketPandas()

results = client.search_markets_events_profiles(
    q="Bitcoin 5-minute",
    events_status="active",
    limit_per_type=5,
)

events = results.get("events", [])
if not events:
    print("No active BTC 5-min events found.")
    sys.exit(1)

# Pick the first active event — usually the current 5-min window
event = events[0]
print(f"Event: {event['title']}")
print(f"  slug:  {event['slug']}")
print(f"  end:   {event.get('endDate', 'N/A')}")

# Each event has binary markets (Up / Down)
markets = event.get("markets", [])
if not markets:
    print("No markets found in event.")
    sys.exit(1)

# Collect token IDs and labels
tokens: list[dict] = []
for m in markets:
    token_ids = m.get("clobTokenIds", "[]")
    if isinstance(token_ids, str):
        import json

        token_ids = json.loads(token_ids)
    outcomes = m.get("outcomes", "[]")
    if isinstance(outcomes, str):
        import json

        outcomes = json.loads(outcomes)
    # token_ids[0] = Yes, token_ids[1] = No for each outcome
    for tid, label in zip(token_ids, outcomes):
        tokens.append(
            {
                "outcome": m.get("groupItemTitle", m.get("question", "")),
                "label": label,
                "token_id": tid,
                "condition_id": m.get("conditionId", ""),
            }
        )

token_df = pd.DataFrame(tokens)
print(f"\n{'='*60}")
print("Markets / Token IDs:")
print(token_df.to_string(index=False))

# We only want the "Yes" tokens — one per outcome (Up / Down)
yes_tokens = token_df[token_df["label"] == "Yes"]
asset_ids = yes_tokens["token_id"].tolist()

# ── 2. REST snapshot: orderbook + recent trades ─────────────────────────────

print(f"\n{'='*60}")
print("Orderbook Snapshot")
print("=" * 60)

for _, row in yes_tokens.iterrows():
    tid = row["token_id"]
    outcome = row["outcome"]
    print(f"\n--- {outcome} (Yes) ---")
    book = client.get_orderbook(tid)
    if book.empty:
        print("  (empty book)")
    else:
        bids = book[book["side"] == "bids"].sort_values("price", ascending=False).head(5)
        asks = book[book["side"] == "asks"].sort_values("price", ascending=True).head(5)
        print(f"  Top Bids:\n{bids[['price', 'size']].to_string(index=False)}")
        print(f"  Top Asks:\n{asks[['price', 'size']].to_string(index=False)}")

    spread = client.get_spread(tid)
    mid = client.get_midpoint_price(tid)
    print(f"  Midpoint: {mid:.4f}  Spread: {spread:.4f}")

print(f"\n{'='*60}")
print("Recent Trades")
print("=" * 60)

trades = client.get_trades(market=asset_ids, limit=20)
if not trades.empty:
    cols = [c for c in ["timestamp", "side", "price", "size", "market"] if c in trades.columns]
    print(trades[cols].to_string(index=False))
else:
    print("(no recent trades)")

# ── 3. WebSocket: live book + trade stream ──────────────────────────────────

print(f"\n{'='*60}")
print("Streaming live updates (Ctrl+C to quit) ...")
print("=" * 60)

ws = PolymarketWebSocket.from_client(client)


def on_book(df: pd.DataFrame) -> None:
    bids = df[df["side"] == "bids"]
    asks = df[df["side"] == "asks"]
    best_bid = bids["price"].max() if not bids.empty else None
    best_ask = asks["price"].min() if not asks.empty else None
    asset = df["assetId"].iloc[0] if "assetId" in df.columns else "?"
    label = yes_tokens.loc[yes_tokens["token_id"] == asset, "outcome"]
    label = label.iloc[0] if not label.empty else asset[:12]
    print(f"  [BOOK]  {label:<12}  bid={best_bid}  ask={best_ask}  levels={len(df)}")


def on_price_change(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        asset = row.get("assetId", "?")
        label = yes_tokens.loc[yes_tokens["token_id"] == asset, "outcome"]
        label = label.iloc[0] if not label.empty else str(asset)[:12]
        print(f"  [PRICE] {label:<12}  price={row.get('price', '?')}")


def on_last_trade_price(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        asset = row.get("assetId", "?")
        label = yes_tokens.loc[yes_tokens["token_id"] == asset, "outcome"]
        label = label.iloc[0] if not label.empty else str(asset)[:12]
        print(f"  [TRADE] {label:<12}  last={row.get('price', '?')}")


session = ws.market_channel(
    asset_ids=asset_ids,
    on_book=on_book,
    on_price_change=on_price_change,
    on_last_trade_price=on_last_trade_price,
)


def _shutdown(sig, frame):
    print("\nShutting down ...")
    session.close()
    client.close()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)

session.run_forever()
