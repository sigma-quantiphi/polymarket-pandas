"""
BTC 5-Minute Up/Down — Orderbook + Live Trades

Finds the current BTC 5-minute binary market on Polymarket, pulls the
orderbook snapshot for both outcomes (Up / Down), then opens a WebSocket
stream for real-time book updates and trade prints.

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

# Markets ending within the next 10 minutes — catches the current 5-min window
markets = client.get_markets(
    end_date_min=now.isoformat(),
    end_date_max=(now + pd.Timedelta(minutes=10)).isoformat(),
    expand_clob_token_ids=True,
    expand_events=False,
    expand_series=False,
)

btc = markets[markets["slug"].str.contains("btc-updown-5m", case=False, na=False)]
if btc.empty:
    print("No active BTC 5-min markets found. Market may be between windows.")
    sys.exit(1)

# Pick the soonest-ending market (current window)
soonest_end = btc["endDate"].min()
current = btc[btc["endDate"] == soonest_end].copy()

question = current["question"].iloc[0]
end_date = current["endDate"].iloc[0]
condition_id = current["conditionId"].iloc[0]

print(f"Market:  {question}")
print(f"  end:   {end_date}")
print(f"  cond:  {condition_id}")

# Each market has 2 exploded rows — outcomes list tells us [Up, Down]
# First token_id = Up, second = Down
outcomes = current["outcomes"].iloc[0]  # e.g. ["Up", "Down"]
token_ids = current["clobTokenIds"].tolist()

token_df = pd.DataFrame({
    "outcome": outcomes,
    "token_id": token_ids,
})
print(f"\n{'='*60}")
print("Token IDs:")
print(token_df.to_string(index=False))

asset_ids = token_df["token_id"].tolist()

# ── 2. REST snapshot: orderbook + recent trades ─────────────────────────────

print(f"\n{'='*60}")
print("Orderbook Snapshot")
print("=" * 60)

for _, row in token_df.iterrows():
    tid = row["token_id"]
    outcome = row["outcome"]
    print(f"\n--- {outcome} ---")
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
    cols = [c for c in ["timestamp", "side", "price", "size"] if c in trades.columns]
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
    label = token_df.loc[token_df["token_id"] == asset, "outcome"]
    label = label.iloc[0] if not label.empty else str(asset)[:12]
    print(f"  [BOOK]  {label:<6}  bid={best_bid}  ask={best_ask}  levels={len(df)}")


def on_price_change(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        asset = row.get("assetId", "?")
        label = token_df.loc[token_df["token_id"] == asset, "outcome"]
        label = label.iloc[0] if not label.empty else str(asset)[:12]
        print(f"  [PRICE] {label:<6}  price={row.get('price', '?')}")


def on_last_trade_price(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        asset = row.get("assetId", "?")
        label = token_df.loc[token_df["token_id"] == asset, "outcome"]
        label = label.iloc[0] if not label.empty else str(asset)[:12]
        print(f"  [TRADE] {label:<6}  last={row.get('price', '?')}")


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
