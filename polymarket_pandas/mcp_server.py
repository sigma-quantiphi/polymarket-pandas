"""Polymarket Pandas MCP server — exposes SDK endpoints as MCP tools.

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
        "All table-returning tools accept max_rows to control output size. "
        "Write tools (place_order, cancel_order, etc.) require user approval."
    ),
)


def _client() -> PolymarketPandas:
    """Build a client from environment variables (cached in module)."""
    global _cached_client
    if _cached_client is None:
        kwargs: dict = {}
        if addr := os.environ.get("POLYMARKET_ADDRESS"):
            kwargs["address"] = addr
        if pk := os.environ.get("POLYMARKET_PRIVATE_KEY"):
            kwargs["private_key"] = pk
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


def _resolve_max_rows(max_rows: int | None) -> int:
    if max_rows is not None and max_rows == 0:
        return 999999
    return max_rows if max_rows is not None else _DEFAULT_MAX_ROWS


def _df_to_str(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """Convert a DataFrame to a readable markdown table, truncated."""
    limit = _resolve_max_rows(max_rows)
    if df.empty:
        return "No data returned."
    total = len(df)
    if total > limit:
        df = df.head(limit)
        suffix = f"\n\n... truncated to {limit} of {total} rows"
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


def _to_list(val: str | None) -> list[str] | None:
    """Split comma-separated string into list, or None."""
    if not val:
        return None
    return [s.strip() for s in val.split(",") if s.strip()] or None


def _to_int_list(val: str | None) -> list[int] | None:
    """Split comma-separated string into int list, or None."""
    if not val:
        return None
    return [int(s.strip()) for s in val.split(",") if s.strip()] or None


# ══════════════════════════════════════════════════════════════════════════════
# DISCOVERY (Gamma API)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def search_markets(
    query: str,
    limit_per_type: int = 10,
    events_status: str | None = None,
    events_tag: str | None = None,
    sort: str | None = None,
    ascending: bool | None = None,
) -> str:
    """Search Polymarket for markets, events, and profiles by keyword.

    Args:
        query: Search text.
        limit_per_type: Max results per type (markets, events, profiles).
        events_status: Filter events by status.
        events_tag: Comma-separated tag slugs to filter events.
        sort: Sort field.
        ascending: Sort direction.
    """
    result = _client().search_markets_events_profiles(
        q=query,
        limit_per_type=limit_per_type,
        events_status=events_status,
        events_tag=_to_list(events_tag),
        sort=sort,
        ascending=ascending,
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
    limit: int = 100,
    offset: int | None = None,
    order: str | None = None,
    ascending: bool | None = None,
    slug: str | None = None,
    clob_token_ids: str | None = None,
    condition_ids: str | None = None,
    liquidity_num_min: float | None = None,
    liquidity_num_max: float | None = None,
    volume_num_min: float | None = None,
    volume_num_max: float | None = None,
    start_date_min: str | None = None,
    start_date_max: str | None = None,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
    tag_id: int | None = None,
    closed: bool | None = None,
    expand_events: bool = True,
    expand_series: bool = True,
    expand_clob_token_ids: bool = True,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket markets with full filtering.

    Args:
        limit: Number of markets to fetch (1-500).
        offset: Pagination offset.
        order: Comma-separated sort fields (e.g. "volume,startDate").
        ascending: Sort direction.
        slug: Comma-separated slugs to look up.
        clob_token_ids: Comma-separated CLOB token IDs.
        condition_ids: Comma-separated condition IDs.
        liquidity_num_min: Min liquidity.
        liquidity_num_max: Max liquidity.
        volume_num_min: Min volume.
        volume_num_max: Max volume.
        start_date_min: Start date min (ISO-8601).
        start_date_max: Start date max (ISO-8601).
        end_date_min: End date min (ISO-8601).
        end_date_max: End date max (ISO-8601).
        tag_id: Filter by tag ID.
        closed: None=all, True=closed, False=open.
        expand_events: Inline event fields.
        expand_series: Inline series fields.
        expand_clob_token_ids: Inline CLOB token IDs.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_markets(
        limit=limit,
        offset=offset,
        order=_to_list(order),
        ascending=ascending,
        slug=_to_list(slug),
        clob_token_ids=_to_list(clob_token_ids),
        condition_ids=_to_list(condition_ids),
        liquidity_num_min=liquidity_num_min,
        liquidity_num_max=liquidity_num_max,
        volume_num_min=volume_num_min,
        volume_num_max=volume_num_max,
        start_date_min=start_date_min,
        start_date_max=start_date_max,
        end_date_min=end_date_min,
        end_date_max=end_date_max,
        tag_id=tag_id if tag_id else None,
        closed=closed,
        expand_events=expand_events,
        expand_series=expand_series,
        expand_clob_token_ids=expand_clob_token_ids,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_market_by_slug(slug: str) -> str:
    """Get detailed info for a single market by its URL slug."""
    return json.dumps(_client().get_market_by_slug(slug), default=str, indent=2)


@mcp.tool()
def get_market_by_id(id: int) -> str:
    """Get detailed info for a single market by its numeric ID."""
    return json.dumps(_client().get_market_by_id(id), default=str, indent=2)


@mcp.tool()
def get_events(
    limit: int = 100,
    offset: int | None = None,
    order: str | None = None,
    ascending: bool | None = None,
    slug: str | None = None,
    tag_id: int | None = None,
    featured: bool | None = None,
    closed: bool | None = None,
    start_date_min: str | None = None,
    start_date_max: str | None = None,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
    expand_markets: bool = True,
    expand_clob_token_ids: bool = True,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket events with full filtering.

    Args:
        limit: Number of events to fetch (1-500).
        offset: Pagination offset.
        order: Comma-separated sort fields.
        ascending: Sort direction.
        slug: Comma-separated slugs.
        tag_id: Filter by tag ID.
        featured: True=featured only, False=non-featured, None=all.
        closed: None=all, True=closed, False=open.
        start_date_min: Start date min (ISO-8601).
        start_date_max: Start date max (ISO-8601).
        end_date_min: End date min (ISO-8601).
        end_date_max: End date max (ISO-8601).
        expand_markets: Inline market fields.
        expand_clob_token_ids: Inline CLOB token IDs.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_events(
        limit=limit,
        offset=offset,
        order=_to_list(order),
        ascending=ascending,
        slug=_to_list(slug),
        tag_id=tag_id if tag_id else None,
        featured=featured,
        closed=closed,
        start_date_min=start_date_min,
        start_date_max=start_date_max,
        end_date_min=end_date_min,
        end_date_max=end_date_max,
        expand_markets=expand_markets,
        expand_clob_token_ids=expand_clob_token_ids,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_event_by_slug(slug: str) -> str:
    """Get detailed info for a single event by its URL slug."""
    return json.dumps(_client().get_event_by_slug(slug), default=str, indent=2)


@mcp.tool()
def get_tags(
    limit: int = 300,
    offset: int | None = None,
    order: str | None = None,
    ascending: bool | None = None,
    is_carousel: bool | None = None,
    max_rows: int | None = None,
) -> str:
    """Get all available tags (categories) on Polymarket.

    Args:
        limit: Number of tags to fetch.
        offset: Pagination offset.
        order: Comma-separated sort fields.
        ascending: Sort direction.
        is_carousel: Filter carousel tags.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_tags(
        limit=limit,
        offset=offset,
        order=_to_list(order),
        ascending=ascending,
        is_carousel=is_carousel,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_series(
    limit: int = 100,
    offset: int | None = None,
    order: str | None = None,
    ascending: bool | None = None,
    slug: str | None = None,
    closed: bool | None = None,
    expand_events: bool = False,
    max_rows: int | None = None,
) -> str:
    """Get Polymarket series (recurring event collections).

    Args:
        limit: Number of series to fetch.
        offset: Pagination offset.
        order: Comma-separated sort fields.
        ascending: Sort direction.
        slug: Comma-separated slugs.
        closed: None=all, True=closed, False=open.
        expand_events: Inline event fields.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_series(
        limit=limit,
        offset=offset,
        order=_to_list(order),
        ascending=ascending,
        slug=_to_list(slug),
        closed=closed,
        expand_events=expand_events,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_sports_metadata(
    sport: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get sports metadata (leagues, resolution sources, etc.).

    Args:
        sport: Filter by sport name.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_sports_metadata(sport=sport)
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_teams(
    limit: int = 100,
    league: str | None = None,
    name: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get sports teams.

    Args:
        limit: Number of teams to fetch.
        league: Comma-separated league filters.
        name: Comma-separated team name filters.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_teams(
        limit=limit,
        league=_to_list(league),
        name=_to_list(name),
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_comments(
    limit: int | None = None,
    offset: int | None = None,
    parent_entity_type: str | None = None,
    parent_entity_id: int | None = None,
    holders_only: bool | None = None,
    max_rows: int | None = None,
) -> str:
    """Get comments on markets/events.

    Args:
        limit: Number of comments to fetch.
        offset: Pagination offset.
        parent_entity_type: Entity type (e.g. "market", "event").
        parent_entity_id: Entity ID.
        holders_only: Only show comments from holders.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_comments(
        limit=limit,
        offset=offset,
        parent_entity_type=parent_entity_type,
        parent_entity_id=parent_entity_id,
        holders_only=holders_only,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_profile(address: str) -> str:
    """Get a user's Polymarket profile by wallet address."""
    return json.dumps(_client().get_profile(address), default=str, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# PRICING (CLOB Public API)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_orderbook(token_id: str, max_rows: int | None = None) -> str:
    """Get the full orderbook (bids and asks) for a CLOB token.

    Args:
        token_id: The clobTokenId.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_orderbook(token_id)
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_midpoint_price(token_id: str) -> str:
    """Get the midpoint price for a token (average of best bid and ask)."""
    return f"{_client().get_midpoint_price(token_id):.6f}"


@mcp.tool()
def get_spread(token_id: str) -> str:
    """Get the bid-ask spread for a token."""
    return f"{_client().get_spread(token_id):.6f}"


@mcp.tool()
def get_last_trade_price(token_id: str) -> str:
    """Get the last trade price for a token."""
    return json.dumps(_client().get_last_trade_price(token_id), default=str)


@mcp.tool()
def get_tick_size(token_id: str) -> str:
    """Get the tick size for a token (min price increment)."""
    return str(_client().get_tick_size(token_id))


@mcp.tool()
def get_neg_risk(token_id: str) -> str:
    """Check if a token uses the neg-risk exchange contract."""
    return str(_client().get_neg_risk(token_id))


@mcp.tool()
def get_price_history(
    token_id: str,
    interval: str = "max",
    fidelity: int | None = None,
    startTs: int | None = None,
    endTs: int | None = None,
    max_rows: int | None = None,
) -> str:
    """Get historical price data for a token.

    Args:
        token_id: The clobTokenId.
        interval: Time range — "max", "1m", "1w", "1d", "6h", "1h".
        fidelity: Candle size in minutes (1, 5, 15, 60, 360, 1440).
        startTs: Start Unix timestamp (seconds).
        endTs: End Unix timestamp (seconds).
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_price_history(
        market=token_id,
        interval=interval,
        fidelity=fidelity,
        startTs=startTs,
        endTs=endTs,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_builder_trades(
    builder: str | None = None,
    market: str | None = None,
    asset_id: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get builder (API) trades.

    Args:
        builder: Builder address filter.
        market: Condition ID filter.
        asset_id: Token ID filter.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_builder_trades(builder=builder, market=market, asset_id=asset_id)
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_rebates(date: str, maker_address: str, max_rows: int | None = None) -> str:
    """Get maker rebates for a given date and address.

    Args:
        date: Date string (YYYY-MM-DD).
        maker_address: Maker wallet address.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_rebates(date=date, maker_address=maker_address)
    return _df_to_str(df, max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# DATA API (Positions, Trades, Leaderboard)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_positions(
    user: str,
    market: str | None = None,
    event_id: str | None = None,
    size_threshold: float | None = 1,
    redeemable: bool | None = None,
    mergeable: bool | None = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "TOKENS",
    sort_direction: str = "DESC",
    title: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get open positions for a wallet address.

    Args:
        user: Wallet address (0x...).
        market: Comma-separated token IDs to filter.
        event_id: Comma-separated event IDs to filter.
        size_threshold: Min position size (default 1).
        redeemable: Filter redeemable positions.
        mergeable: Filter mergeable positions.
        limit: Max positions to fetch from API.
        offset: Pagination offset.
        sort_by: "TOKENS" or "VALUE".
        sort_direction: "DESC" or "ASC".
        title: Title search filter.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_positions(
        user=user,
        market=_to_list(market),
        eventId=_to_int_list(event_id),
        sizeThreshold=size_threshold,
        redeemable=redeemable,
        mergeable=mergeable,
        limit=limit,
        offset=offset,
        sortBy=sort_by,
        sortDirection=sort_direction,
        title=title,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_closed_positions(
    user: str,
    market: str | None = None,
    event_id: str | None = None,
    title: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "REALIZEDPNL",
    sort_direction: str = "DESC",
    max_rows: int | None = None,
) -> str:
    """Get closed positions for a wallet address.

    Args:
        user: Wallet address (0x...).
        market: Comma-separated token IDs to filter.
        event_id: Comma-separated event IDs to filter.
        title: Title search filter.
        limit: Max positions to fetch from API.
        offset: Pagination offset.
        sort_by: "REALIZEDPNL", "TOTAL_PNL", or "TOKENS".
        sort_direction: "DESC" or "ASC".
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_closed_positions(
        user=user,
        market=_to_list(market),
        eventId=_to_int_list(event_id),
        title=title,
        limit=limit,
        offset=offset,
        sortBy=sort_by,
        sortDirection=sort_direction,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_market_positions(
    market: str,
    user: str | None = None,
    status: str = "ALL",
    sort_by: str = "TOTAL_PNL",
    limit: int = 50,
    max_rows: int | None = None,
) -> str:
    """Get all positions for a specific market.

    Args:
        market: Token ID.
        user: Filter by user address.
        status: "ALL", "OPEN", or "CLOSED".
        sort_by: Sort field.
        limit: Max results.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_market_positions(
        market=market, user=user, status=status, sortBy=sort_by, limit=limit
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_top_holders(
    market: str,
    limit: int = 100,
    max_rows: int | None = None,
) -> str:
    """Get top token holders for a market.

    Args:
        market: clobTokenId.
        limit: Max holders.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_top_holders(market=[market], limit=limit)
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_trades(
    limit: int = 100,
    offset: int = 0,
    taker_only: bool = True,
    filter_type: str | None = None,
    filter_amount: float | None = None,
    market: str | None = None,
    event_id: str | None = None,
    user: str | None = None,
    side: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get recent trades with full filtering.

    Args:
        limit: Max trades to fetch (1-500).
        offset: Pagination offset.
        taker_only: Only taker fills.
        filter_type: "ABOVE" or "BELOW".
        filter_amount: Amount threshold (used with filter_type).
        market: Comma-separated token IDs.
        event_id: Comma-separated event IDs.
        user: Filter by wallet address.
        side: "BUY" or "SELL".
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_trades(
        limit=limit,
        offset=offset,
        takerOnly=taker_only,
        filterType=filter_type,
        filterAmount=filter_amount,
        market=_to_list(market),
        eventId=_to_int_list(event_id),
        user=user or None,
        side=side,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_user_activity(
    user: str,
    limit: int = 100,
    offset: int = 0,
    market: str | None = None,
    event_id: str | None = None,
    type: str | None = None,
    side: str | None = None,
    sort_by: str = "TIMESTAMP",
    sort_direction: str = "DESC",
    max_rows: int | None = None,
) -> str:
    """Get user activity (trades, transfers, redemptions, etc.).

    Args:
        user: Wallet address.
        limit: Max results.
        offset: Pagination offset.
        market: Comma-separated token IDs.
        event_id: Comma-separated event IDs.
        type: Comma-separated activity types.
        side: "BUY" or "SELL".
        sort_by: "TIMESTAMP" or "VALUE".
        sort_direction: "DESC" or "ASC".
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_user_activity(
        user=user,
        limit=limit,
        offset=offset,
        market=_to_list(market),
        eventId=_to_int_list(event_id),
        type=_to_list(type),
        side=side,
        sortBy=sort_by,
        sortDirection=sort_direction,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_leaderboard(
    category: str = "OVERALL",
    time_period: str = "DAY",
    order_by: str = "PNL",
    limit: int = 25,
    offset: int = 0,
    user: str | None = None,
    user_name: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get the Polymarket trader leaderboard.

    Args:
        category: "OVERALL", "CRYPTO", "POLITICS", "SPORTS", "POP_CULTURE".
        time_period: "DAY", "WEEK", "MONTH", or "ALL".
        order_by: "PNL" or "VOLUME".
        limit: Max entries (1-100).
        offset: Pagination offset.
        user: Look up specific user address.
        user_name: Look up specific username.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_leaderboard(
        category=category,
        timePeriod=time_period,
        orderBy=order_by,
        limit=limit,
        offset=offset,
        user=user or None,
        userName=user_name or None,
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_builder_leaderboard(
    time_period: str = "DAY",
    limit: int = 25,
    offset: int = 0,
    max_rows: int | None = None,
) -> str:
    """Get the Polymarket builder (API trader) leaderboard.

    Args:
        time_period: "DAY", "WEEK", "MONTH", or "ALL".
        limit: Max entries.
        offset: Pagination offset.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_builder_leaderboard(timePeriod=time_period, limit=limit, offset=offset)
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_accounting_snapshot(user: str) -> str:
    """Get full accounting snapshot for a user (balances, positions, PnL).

    Args:
        user: Wallet address.
    """
    result = _client().get_accounting_snapshot(user)
    parts = []
    for key, df in result.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            parts.append(f"### {key}\n{df.to_markdown(index=False)}")
    return "\n\n".join(parts) if parts else "No accounting data."


@mcp.tool()
def get_open_interest(market: str | None = None) -> str:
    """Get open interest for markets.

    Args:
        market: Comma-separated token IDs (omit for global).
    """
    result = _client().get_open_interest(market=_to_list(market))
    return json.dumps(result, default=str, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# REWARDS API
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_rewards_markets_current(
    sponsored: bool | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get currently active reward configurations.

    Args:
        sponsored: Filter sponsored rewards.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_rewards_markets_current(
        sponsored=sponsored, next_cursor=next_cursor or None
    )
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_rewards_markets_multi(
    query: str | None = None,
    tag_slug: str | None = None,
    event_id: str | None = None,
    order_by: str | None = None,
    position: str | None = None,
    min_volume_24hr: float | None = None,
    max_volume_24hr: float | None = None,
    min_spread: float | None = None,
    max_spread: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    page_size: int | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get markets with active liquidity rewards, with full filtering.

    Args:
        query: Text search on market question.
        tag_slug: Filter by tag slug.
        event_id: Filter by event ID.
        order_by: "rate_per_day", "volume_24hr", "spread", "competitiveness".
        position: Sort direction: "ASC" or "DESC".
        min_volume_24hr: Min 24h volume.
        max_volume_24hr: Max 24h volume.
        min_spread: Min spread.
        max_spread: Max spread.
        min_price: Min token price.
        max_price: Max token price.
        page_size: Items per page (max 500).
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_rewards_markets_multi(
        q=query,
        tag_slug=tag_slug,
        event_id=event_id,
        order_by=order_by,
        position=position,
        min_volume_24hr=min_volume_24hr,
        max_volume_24hr=max_volume_24hr,
        min_spread=min_spread,
        max_spread=max_spread,
        min_price=min_price,
        max_price=max_price,
        page_size=page_size,
        next_cursor=next_cursor or None,
    )
    return _cursor_to_str(dict(result), max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# CLOB PRIVATE (Read)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_balance_allowance(asset_type: int, token_id: str | None = None) -> str:
    """Get balance and allowance for a token. Requires L2 auth.

    Args:
        asset_type: 0=collateral, 1=conditional.
        token_id: Token ID (required for conditional).
    """
    result = _client().get_balance_allowance(asset_type=asset_type, token_id=token_id)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def get_user_trades(
    market: str | None = None,
    maker: str | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get authenticated user's CLOB trades. Requires L2 auth.

    Args:
        market: Condition ID filter.
        maker: Maker address filter.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_user_trades(market=market, maker=maker, next_cursor=next_cursor or None)
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_active_orders(
    market: str | None = None,
    asset_id: str | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get authenticated user's active orders. Requires L2 auth.

    Args:
        market: Condition ID filter.
        asset_id: Token ID filter.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_active_orders(
        market=market, asset_id=asset_id, next_cursor=next_cursor or None
    )
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_order(order_id: str) -> str:
    """Get details for a specific order. Requires L2 auth."""
    return json.dumps(_client().get_order(order_id), default=str, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# WRITE OPERATIONS (require user approval in MCP clients)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def build_order(
    token_id: str,
    price: float,
    size: float,
    side: str,
    expiration: int = 0,
) -> str:
    """Build and sign a CLOB order (does NOT submit it). Requires private key.

    Args:
        token_id: The clobTokenId to trade.
        price: Limit price (0-1).
        size: Number of shares.
        side: "BUY" or "SELL".
        expiration: Unix timestamp for expiry (0=GTC, no expiry).

    Returns the signed order dict, ready to pass to place_order.
    """
    order = _client().build_order(
        token_id=token_id,
        price=price,
        size=size,
        side=side,
        expiration=expiration,
    )
    return json.dumps(dict(order), default=str, indent=2)


@mcp.tool()
def place_order(
    token_id: str,
    price: float,
    size: float,
    side: str,
    order_type: str = "GTC",
    expiration: int = 0,
) -> str:
    """Build, sign, and submit a limit order. Requires private key + L2 auth.

    THIS WILL PLACE A REAL ORDER ON POLYMARKET.

    Args:
        token_id: The clobTokenId to trade.
        price: Limit price (0-1).
        size: Number of shares.
        side: "BUY" or "SELL".
        order_type: "GTC" (good-til-cancel), "GTD" (good-til-date), or "FOK" (fill-or-kill).
        expiration: Unix timestamp for GTD expiry (0=GTC).
    """
    client = _client()
    order = client.build_order(
        token_id=token_id,
        price=price,
        size=size,
        side=side,
        expiration=expiration,
    )
    if not client.address:
        return "Error: POLYMARKET_ADDRESS not set. Cannot place orders."
    result = client.place_order(
        order=dict(order),
        owner=client.address,
        orderType=order_type,
    )
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def cancel_order(order_id: str) -> str:
    """Cancel a specific active order. Requires L2 auth.

    THIS WILL CANCEL A REAL ORDER ON POLYMARKET.

    Args:
        order_id: The order ID to cancel.
    """
    result = _client().cancel_order(order_id)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def cancel_orders(order_ids: str) -> str:
    """Cancel multiple orders. Requires L2 auth.

    THIS WILL CANCEL REAL ORDERS ON POLYMARKET.

    Args:
        order_ids: Comma-separated order IDs.
    """
    ids = [s.strip() for s in order_ids.split(",") if s.strip()]
    result = _client().cancel_orders(ids)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def cancel_all_orders() -> str:
    """Cancel ALL active orders. Requires L2 auth.

    THIS WILL CANCEL ALL ORDERS ON POLYMARKET.
    """
    result = _client().cancel_all_orders()
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def cancel_orders_from_market(market: str = "", asset_id: str = "") -> str:
    """Cancel all orders for a specific market or token. Requires L2 auth.

    THIS WILL CANCEL REAL ORDERS ON POLYMARKET.

    Args:
        market: Condition ID to cancel orders from.
        asset_id: Token ID to cancel orders from.
    """
    result = _client().cancel_orders_from_market(market=market, asset_id=asset_id)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def send_heartbeat() -> str:
    """Send a heartbeat to keep active orders alive. Requires L2 auth."""
    return json.dumps(_client().send_heartbeat(), default=str, indent=2)


@mcp.tool()
def get_order_scoring(order_id: str) -> str:
    """Check if an order is scoring (earning rewards). Requires L2 auth.

    Args:
        order_id: The order ID to check.
    """
    return str(_client().get_order_scoring(order_id))


@mcp.tool()
def create_api_key(nonce: int = 0) -> str:
    """Create new L2 API credentials. Requires private key.

    Args:
        nonce: Key creation nonce (default 0).
    """
    result = _client().create_api_key(nonce=nonce)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def delete_api_key() -> str:
    """Delete the current API key. Requires L2 auth.

    THIS WILL DELETE YOUR API KEY.
    """
    return json.dumps(_client().delete_api_key(), default=str, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# BRIDGE API
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_bridge_supported_assets() -> str:
    """Get supported assets for bridging to/from Polymarket."""
    return json.dumps(_client().get_bridge_supported_assets(), default=str, indent=2)


@mcp.tool()
def get_bridge_transaction_status(address: str, max_rows: int | None = None) -> str:
    """Get bridge transaction status.

    Args:
        address: Bridge address (from create_deposit_address or create_withdrawal_address).
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_bridge_transaction_status(address)
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_bridge_quote(
    from_amount_base_unit: str,
    from_chain_id: str,
    from_token_address: str,
    recipient_address: str,
    to_chain_id: str,
    to_token_address: str,
) -> str:
    """Get a bridge quote for transferring assets to/from Polymarket.

    Args:
        from_amount_base_unit: Amount in base units (e.g. "1000000" = 1 USDC).
        from_chain_id: Source chain ID (e.g. "1" for Ethereum).
        from_token_address: Source token contract address.
        recipient_address: Destination wallet address.
        to_chain_id: Destination chain ID (e.g. "137" for Polygon).
        to_token_address: Destination token contract address.
    """
    result = _client().get_bridge_quote(
        from_amount_base_unit=from_amount_base_unit,
        from_chain_id=from_chain_id,
        from_token_address=from_token_address,
        recipient_address=recipient_address,
        to_chain_id=to_chain_id,
        to_token_address=to_token_address,
    )
    return json.dumps(result, default=str, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def derive_api_key(nonce: int = 0) -> str:
    """Derive L2 API credentials from private key. Requires private key.

    Sets credentials on the client for subsequent L2 calls.

    Args:
        nonce: Derivation nonce (default 0).
    """
    result = _client().derive_api_key(nonce=nonce)
    return json.dumps(dict(result), default=str, indent=2)


@mcp.tool()
def get_api_keys(max_rows: int | None = None) -> str:
    """List API keys for the authenticated user. Requires L2 auth."""
    df = _client().get_api_keys()
    return _df_to_str(df, max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL DISCOVERY (Gamma)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_event_by_id(id: int) -> str:
    """Get detailed info for a single event by its numeric ID."""
    return json.dumps(_client().get_event_by_id(id), default=str, indent=2)


@mcp.tool()
def get_tag_by_slug(slug: str) -> str:
    """Get a single tag by its slug."""
    return json.dumps(_client().get_tag_by_slug(slug), default=str, indent=2)


@mcp.tool()
def get_tag_by_id(id: int) -> str:
    """Get a single tag by its numeric ID."""
    return json.dumps(_client().get_tag_by_id(id), default=str, indent=2)


@mcp.tool()
def get_related_tags(
    slug: str | None = None,
    id: int | None = None,
    omit_empty: bool | None = None,
    status: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get tags related to a given tag (by slug or ID).

    Args:
        slug: Tag slug (use this or id).
        id: Tag numeric ID (use this or slug).
        omit_empty: Omit tags with no events.
        status: Filter by status.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    if slug:
        df = _client().get_related_tags_by_tag_slug(slug=slug, omit_empty=omit_empty, status=status)
    elif id is not None:
        df = _client().get_related_tags_by_tag_id(id=id, omit_empty=omit_empty, status=status)
    else:
        return "Error: provide either slug or id."
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_market_tags(id: int, max_rows: int | None = None) -> str:
    """Get tags for a specific market.

    Args:
        id: Market numeric ID.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    return _df_to_str(_client().get_market_tags(id), max_rows)


@mcp.tool()
def get_event_tags(id: int, max_rows: int | None = None) -> str:
    """Get tags for a specific event.

    Args:
        id: Event numeric ID.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    return _df_to_str(_client().get_event_tags(id), max_rows)


@mcp.tool()
def get_series_by_id(id: int) -> str:
    """Get a single series by its numeric ID."""
    return json.dumps(_client().get_series_by_id(id), default=str, indent=2)


@mcp.tool()
def get_sports_market_types() -> str:
    """Get the list of supported sports market types."""
    return json.dumps(_client().get_sports_market_types(), default=str, indent=2)


@mcp.tool()
def get_comment_by_id(id: int) -> str:
    """Get a single comment by its ID."""
    return json.dumps(_client().get_comment_by_id(id), default=str, indent=2)


@mcp.tool()
def get_comments_by_user(
    user_address: str,
    limit: int | None = None,
    offset: int | None = None,
    max_rows: int | None = None,
) -> str:
    """Get comments posted by a specific user.

    Args:
        user_address: Wallet address.
        limit: Max comments.
        offset: Pagination offset.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_comments_by_user_address(
        user_address=user_address, limit=limit, offset=offset
    )
    return _df_to_str(df, max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL PRICING (CLOB Public)
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_server_time() -> str:
    """Get the CLOB server time (Unix timestamp)."""
    return str(_client().get_server_time())


@mcp.tool()
def get_fee_rate(token_id: str | None = None) -> str:
    """Get the maker fee rate (basis points).

    Args:
        token_id: Token ID (optional, for market-specific rate).
    """
    return str(_client().get_fee_rate(token_id=token_id))


@mcp.tool()
def get_market_price(token_id: str, side: str) -> str:
    """Get the best price on one side of the book.

    Args:
        token_id: The clobTokenId.
        side: "BUY" or "SELL".
    """
    return f"{_client().get_market_price(token_id, side):.6f}"


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL DATA API
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_positions_value(
    user: str,
    market: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get position values (mark-to-market) for a user.

    Args:
        user: Wallet address.
        market: Comma-separated token IDs to filter.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_positions_value(user=user, market=_to_list(market))
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_live_volume(id: int) -> str:
    """Get live volume for a market.

    Args:
        id: Market numeric ID.
    """
    return json.dumps(_client().get_live_volume(id), default=str, indent=2)


@mcp.tool()
def get_traded_markets_count(user: str) -> str:
    """Get the number of markets a user has traded.

    Args:
        user: Wallet address.
    """
    return json.dumps(_client().get_traded_markets_count(user), default=str, indent=2)


@mcp.tool()
def get_builder_volume(
    time_period: str = "DAY",
    max_rows: int | None = None,
) -> str:
    """Get builder volume data.

    Args:
        time_period: "DAY", "WEEK", "MONTH", or "ALL".
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_builder_volume(timePeriod=time_period)
    return _df_to_str(df, max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL REWARDS
# ══════════════════════════════════════════════════════════════════════════════


@mcp.tool()
def get_rewards_market(
    condition_id: str,
    sponsored: bool | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get reward configs for a specific market.

    Args:
        condition_id: The market's condition ID.
        sponsored: Filter sponsored rewards.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_rewards_market(
        condition_id=condition_id,
        sponsored=sponsored,
        next_cursor=next_cursor or None,
    )
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_rewards_earnings(
    date: str,
    maker_address: str | None = None,
    sponsored: bool | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get per-market user earnings for a day. Requires L2 auth.

    Args:
        date: Date string (YYYY-MM-DD).
        maker_address: Maker address override.
        sponsored: Filter sponsored rewards.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_rewards_earnings(
        date=date,
        maker_address=maker_address,
        sponsored=sponsored,
        next_cursor=next_cursor or None,
    )
    return _cursor_to_str(dict(result), max_rows)


@mcp.tool()
def get_rewards_earnings_total(
    date: str,
    maker_address: str | None = None,
    sponsored: bool | None = None,
    max_rows: int | None = None,
) -> str:
    """Get total earnings for a user on a given day. Requires L2 auth.

    Args:
        date: Date string (YYYY-MM-DD).
        maker_address: Maker address override.
        sponsored: Filter sponsored rewards.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    df = _client().get_rewards_earnings_total(
        date=date, maker_address=maker_address, sponsored=sponsored
    )
    return _df_to_str(df, max_rows)


@mcp.tool()
def get_rewards_percentages(maker_address: str | None = None) -> str:
    """Get real-time reward percentages per market. Requires L2 auth.

    Args:
        maker_address: Maker address override.
    """
    result = _client().get_rewards_percentages(maker_address=maker_address)
    return json.dumps(result, default=str, indent=2)


@mcp.tool()
def get_rewards_user_markets(
    date: str | None = None,
    maker_address: str | None = None,
    sponsored: bool | None = None,
    q: str | None = None,
    tag_slug: str | None = None,
    order_by: str | None = None,
    position: str | None = None,
    page_size: int | None = None,
    next_cursor: str | None = None,
    max_rows: int | None = None,
) -> str:
    """Get user's reward markets with filtering. Requires L2 auth.

    Args:
        date: Date filter (YYYY-MM-DD).
        maker_address: Maker address override.
        sponsored: Filter sponsored rewards.
        q: Text search.
        tag_slug: Tag slug filter.
        order_by: Sort field.
        position: Sort direction: "ASC" or "DESC".
        page_size: Items per page.
        next_cursor: Cursor for pagination.
        max_rows: Max rows in output (default 200, 0=unlimited).
    """
    result = _client().get_rewards_user_markets(
        date=date,
        maker_address=maker_address,
        sponsored=sponsored,
        q=q,
        tag_slug=tag_slug,
        order_by=order_by,
        position=position,
        page_size=page_size,
        next_cursor=next_cursor or None,
    )
    return _cursor_to_str(dict(result), max_rows)


# ══════════════════════════════════════════════════════════════════════════════
# SERVER ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════


def main():
    """Run the Polymarket MCP server."""
    import sys

    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
