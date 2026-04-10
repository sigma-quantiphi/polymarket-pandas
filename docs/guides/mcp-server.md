# MCP Server

Query Polymarket data from any MCP client (Claude Code, Claude Desktop, etc.) with
74 tools covering the full API surface.

## Installation

```bash
pip install "polymarket-pandas[mcp]"
```

## Running the Server

```bash
# stdio transport (default)
polymarket-mcp

# SSE transport
polymarket-mcp --sse
```

## Claude Code / Claude Desktop Setup

Add to your MCP settings (`~/.claude/settings.json` or Claude Desktop config):

```json
{
  "mcpServers": {
    "polymarket": {
      "command": "polymarket-mcp"
    }
  }
}
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `POLYMARKET_ADDRESS` | Wallet address for position/trade queries |
| `POLYMARKET_PRIVATE_KEY` | Private key for order signing |
| `POLYMARKET_API_KEY` | L2 API key for private endpoints |
| `POLYMARKET_API_SECRET` | L2 API secret |
| `POLYMARKET_API_PASSPHRASE` | L2 API passphrase |
| `POLYMARKET_MCP_MAX_ROWS` | Default max rows in table output (default 200) |

!!! tip
    Each tool also accepts a `max_rows` parameter to override the default per-call.
    Set `max_rows=0` for unlimited output.

## Available Tools (74)

### Discovery (19 tools)

`search_markets`, `get_markets`, `get_market_by_slug`, `get_market_by_id`,
`get_events`, `get_event_by_slug`, `get_event_by_id`, `get_tags`, `get_tag_by_slug`,
`get_tag_by_id`, `get_related_tags`, `get_market_tags`, `get_event_tags`,
`get_series`, `get_series_by_id`, `get_teams`, `get_comments`, `get_comment_by_id`,
`get_comments_by_user`, `get_profile`, `get_sports_metadata`, `get_sports_market_types`

### Pricing (12 tools)

`get_orderbook`, `get_midpoint_price`, `get_spread`, `get_last_trade_price`,
`get_tick_size`, `get_neg_risk`, `get_fee_rate`, `get_market_price`,
`get_price_history`, `get_builder_trades`, `get_rebates`, `get_server_time`

### Data (14 tools)

`get_positions`, `get_closed_positions`, `get_market_positions`, `get_top_holders`,
`get_positions_value`, `get_trades`, `get_user_activity`, `get_leaderboard`,
`get_builder_leaderboard`, `get_builder_volume`, `get_accounting_snapshot`,
`get_open_interest`, `get_live_volume`, `get_traded_markets_count`

### Rewards (7 tools)

`get_rewards_markets_current`, `get_rewards_markets_multi`, `get_rewards_market`,
`get_rewards_earnings`, `get_rewards_earnings_total`, `get_rewards_percentages`,
`get_rewards_user_markets`

### Private (7 tools)

`get_balance_allowance`, `get_user_trades`, `get_active_orders`, `get_order`,
`get_order_scoring`, `get_api_keys`, `send_heartbeat`

### Write (9 tools)

`build_order`, `place_order`, `cancel_order`, `cancel_orders`, `cancel_all_orders`,
`cancel_orders_from_market`, `create_api_key`, `derive_api_key`, `delete_api_key`

### Bridge (3 tools)

`get_bridge_supported_assets`, `get_bridge_transaction_status`, `get_bridge_quote`

!!! warning
    CTF on-chain operations, relayer operations, and batch DataFrame-input methods
    (`place_orders`, `submit_orders`) are not exposed as MCP tools.
