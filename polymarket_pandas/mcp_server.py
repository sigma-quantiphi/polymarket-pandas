"""Polymarket Pandas MCP server — exposes read-only SDK endpoints as MCP tools.

Usage:
    polymarket-mcp              # stdio transport (default)
    polymarket-mcp --sse        # SSE transport on port 8000

Install:
    pip install polymarket-pandas[mcp]
"""

from __future__ import annotations

import json
import os

import pandas as pd
from fastmcp import FastMCP

from polymarket_pandas import PolymarketPandas

mcp = FastMCP(
    "Polymarket",
    instructions=(
        "Query live Polymarket prediction market data. "
        "Use search_markets to find markets by keyword, then drill into "
        "orderbooks, prices, positions, and trades using token/condition IDs. "
        "All table-returning tools accept max_rows to control output size."
    ),
)


def _client() -> PolymarketPandas:
    """Build a client from environment variables (cached in module)."""
    global _cached_client
    if _cached_client is None:
        kwargs: dict = {}
        if addr := os.environ.get("POLYMARKET_ADDRESS"):
            kwargs["address"] = addr
        if key := os.environ.get("POLYMARKET_API_KEY"):
            kwargs["api_key"] = key
        if secret := os.environ.get("POLYMARKET_API_SECRET"):
            kwargs["api_secret"] = secret
        if passphrase := os.environ.get("POLYMARKET_API_PASSPHRASE"):
            kwargs["api_passphrase"] = passphrase
        _cached_client = PolymarketPandas(**kwargs)
    return _cached_client


_cached_client: PolymarketPandas | None = None

_DEFAULT_MAX_ROWS = int(os.environ.get("POLYMARKET_MCP_MAX_ROWS", "200"))


def _df_to_str(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """Convert a DataFrame to a readable markdown table, truncated."""
    if max_rows is None:
        max_rows = _DEFAULT_MAX_ROWS
    if df.empty:
        return "No data returned."
    total = len(df)
    if total > max_rows:
        df = df.head(max_rows)
        suffix = f"\n\n... truncated to {max_rows} of {total} rows"
    else:
        suffix = ""
    return df.to_markdown(index=False) + suffix


def _cursor_to_str(result: dict, max_rows: int | None = None) -> str:
    """Convert a CursorPage result to readable output."""
    df = result["data"]
    cursor = result.get("next_cursor", "")
    count = result.get("count", len(df))
    out = _df_to_str(df, max_rows)
    if cursor and cursor != "LTE=":
        out += f"\n\nnext_cursor: {cursor} (pass to get next page)"
    out += f"\ncount: {count}"
    return out


# ── Discovery ────────────────────────────────────────────────────────────────


@mcp.tool()
def search_markets(
    query: str,
    limit_per_type: int = 10,
) -> str:
    """Search Polymarket for markets, events, and profiles by keyword.

    Returns matching markets, events, and profiles. This is the best
    starting point for finding markets to query.
    """
    result = _client().search_markets_events_profiles(
        q=query,
        limit_per_type=limit_per_type,
    )
    parts = []
    for key in ("markets", "events", "profiles"):
        items = result.get(key, [])
        if items:
            df = pd.DataFrame(items)
            cols = [c for c in ["slug", "question", "title", "name"] if c in df.columns]
            id_cols = [c for c in ["id", "conditionId", "clobTokenIds"] if c in df.columns]
            show = cols + id_cols
            if show:
                df = df[[c for c in show if c in df.columns]]
            parts.append(f"### {key.title()}\n{df.to_markdown(index=False)}")
    return "\n\n".join(parts) if parts else "No results found."


@mcp.tool()
def get_markets(
    limit: int = 20,
    closed: bool | None = None,
    volume_num_min: float | None = None,
    tag_id: int | None = None,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket markets with optional filters.

    Args:
        limit: Number of markets to fetch from the API (1-500).
        closed: None=all, True=closed, False=open.
        volume_num_min: Minimum volume filter.
        tag_id: Filter by tag ID.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_markets(
        limit=limit,
        closed=closed,
        volume_num_min=volume_num_min,
        tag_id=tag_id if tag_id else None,
    )
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_market_by_slug(slug: str) -> str:
    """Get detailed info for a single market by its URL slug."""
    data = _client().get_market_by_slug(slug)
    return json.dumps(data, default=str, indent=2)


@mcp.tool()
def get_events(
    limit: int = 20,
    closed: bool | None = None,
    featured: bool | None = None,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket events (groups of related markets).

    Args:
        limit: Number of events to fetch from the API (1-500).
        closed: None=all, True=closed, False=open.
        featured: None=all, True=featured only.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_events(
        limit=limit,
        closed=closed,
        featured=featured,
    )
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_event_by_slug(slug: str) -> str:
    """Get detailed info for a single event by its URL slug."""
    data = _client().get_event_by_slug(slug)
    return json.dumps(data, default=str, indent=2)


@mcp.tool()
def get_tags(limit: int = 100, max_rows: int | None = None) -> str:
    """Get all available tags (categories) on Polymarket.

    Args:
        limit: Number of tags to fetch from the API.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_tags(limit=limit)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_series(
    limit: int = 20,
    closed: bool | None = None,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket series (recurring event collections).

    Args:
        limit: Number of series to fetch from the API.
        closed: None=all, True=closed, False=open.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_series(limit=limit, closed=closed)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


# ── Pricing ──────────────────────────────────────────────────────────────────


@mcp.tool()
def get_orderbook(token_id: str, max_rows: int | None = None) -> str:
    """Get the full orderbook (bids and asks) for a CLOB token.

    Args:
        token_id: The clobTokenId (from market data).
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_orderbook(token_id)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_midpoint_price(token_id: str) -> str:
    """Get the midpoint price for a token (average of best bid and ask)."""
    price = _client().get_midpoint_price(token_id)
    return f"{price:.6f}"


@mcp.tool()
def get_spread(token_id: str) -> str:
    """Get the bid-ask spread for a token."""
    spread = _client().get_spread(token_id)
    return f"{spread:.6f}"


@mcp.tool()
def get_last_trade_price(token_id: str) -> str:
    """Get the last trade price for a token."""
    result = _client().get_last_trade_price(token_id)
    return json.dumps(result, default=str)


@mcp.tool()
def get_price_history(
    token_id: str,
    interval: str = "max",
    fidelity: int | None = None,
    max_rows: int | None = None,
) -> str:
    """Get historical price data for a token.

    Args:
        token_id: The clobTokenId.
        interval: Time range — "max", "1m", "1w", "1d", "6h", "1h".
        fidelity: Candle size in minutes (1, 5, 15, 60, 360, 1440).
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_price_history(
        market=token_id,
        interval=interval,
        fidelity=fidelity,
    )
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


# ── Positions & Trades ───────────────────────────────────────────────────────


@mcp.tool()
def get_positions(
    user: str,
    limit: int = 50,
    sort_by: str = "TOKENS",
    max_rows: int | None = None,
) -> str:
    """Get open positions for a wallet address.

    Args:
        user: Wallet address (0x...).
        limit: Max positions to fetch from the API.
        sort_by: Sort field — "TOKENS" or "VALUE".
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_positions(user=user, limit=limit, sortBy=sort_by)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_closed_positions(
    user: str,
    limit: int = 20,
    sort_by: str = "REALIZEDPNL",
    max_rows: int | None = None,
) -> str:
    """Get closed positions for a wallet address.

    Args:
        user: Wallet address (0x...).
        limit: Max positions to fetch from the API.
        sort_by: "REALIZEDPNL" or "TOTAL_PNL".
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_closed_positions(user=user, limit=limit, sortBy=sort_by)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_trades(
    limit: int = 50,
    user: str | None = None,
    side: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get recent trades, optionally filtered by user or side.

    Args:
        limit: Max trades to fetch from the API (1-500).
        user: Filter by wallet address.
        side: "BUY" or "SELL".
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_trades(limit=limit, user=user or None, side=side)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_top_holders(
    market: str,
    limit: int = 50,
    max_rows: int | None = None,
) -> str:
    """Get the top token holders for a market.

    Args:
        market: Token ID(s) — single clobTokenId string.
        limit: Max holders to fetch from the API.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_top_holders(market=[market], limit=limit)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


# ── Leaderboard ──────────────────────────────────────────────────────────────


@mcp.tool()
def get_leaderboard(
    time_period: str = "DAY",
    order_by: str = "PNL",
    limit: int = 25,
    max_rows: int | None = None,
) -> str:
    """Get the Polymarket trader leaderboard.

    Args:
        time_period: "DAY", "WEEK", "MONTH", or "ALL".
        order_by: "PNL" or "VOLUME".
        limit: Max entries to fetch from the API (1-100).
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_leaderboard(
        timePeriod=time_period,
        orderBy=order_by,
        limit=limit,
    )
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


@mcp.tool()
def get_builder_leaderboard(
    time_period: str = "DAY",
    limit: int = 25,
    max_rows: int | None = None,
) -> str:
    """Get the Polymarket builder (API trader) leaderboard.

    Args:
        time_period: "DAY", "WEEK", "MONTH", or "ALL".
        limit: Max entries to fetch from the API.
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_builder_leaderboard(timePeriod=time_period, limit=limit)
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


# ── Rewards ──────────────────────────────────────────────────────────────────


@mcp.tool()
def get_rewards_markets(
    query: str | None = None,
    order_by: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get markets with active liquidity rewards.

    Args:
        query: Text search on market question.
        order_by: "rate_per_day", "volume_24hr", "spread", "competitiveness".
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    result = _client().get_rewards_markets_multi(q=query, order_by=order_by)
    return _cursor_to_str(dict(result), max_rows=max_rows if max_rows != 0 else 999999)


# ── Profile ──────────────────────────────────────────────────────────────────


@mcp.tool()
def get_profile(address: str) -> str:
    """Get a user's Polymarket profile by wallet address."""
    data = _client().get_profile(address)
    return json.dumps(data, default=str, indent=2)


# ── Sports ───────────────────────────────────────────────────────────────────


@mcp.tool()
def get_sports_metadata(max_rows: int | None = None) -> str:
    """Get metadata about available sports on Polymarket (leagues, teams, etc.).

    Args:
        max_rows: Max rows in the output table (default 200, 0=unlimited).
    """
    df = _client().get_sports_metadata()
    return _df_to_str(df, max_rows=max_rows if max_rows != 0 else 999999)


# ── Bridge ───────────────────────────────────────────────────────────────────


@mcp.tool()
def get_bridge_supported_assets() -> str:
    """Get supported assets for bridging to/from Polymarket."""
    assets = _client().get_bridge_supported_assets()
    return json.dumps(assets, default=str, indent=2)


# ── Server entry point ───────────────────────────────────────────────────────


def main():
    """Run the Polymarket MCP server."""
    import sys

    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
