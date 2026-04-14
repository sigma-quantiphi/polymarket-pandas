# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [0.6.27] — 2026-04-14

### Fixed
- `get_balance_allowance` now sends `asset_type` as the string enum (`"COLLATERAL"` / `"CONDITIONAL"`) the CLOB server actually expects. Previously the integer values `0` / `1` were sent verbatim, triggering a server-side fallthrough that returned the misleading `"GetBalanceAndAllowance invalid params: assetAddress invalid hex address"` error. Integer shortcuts remain accepted — they're mapped client-side.
- For proxy wallets (`signature_type=1` or `2`), the `signatureType` query parameter is now auto-attached so the server resolves the balance against the proxy address rather than the authenticated EOA (which is empty for most proxy users).

---

## [0.6.26] — 2026-04-14

### Added
- `parse_title_threshold()` — vectorized extraction of `thresholdPrice` and `thresholdDirection` (`"above"` / `"below"`) for threshold-crossing binary markets (e.g. `what-price-will-solana-hit-on-*` with group title `↓ 65`, `will-nflx-hit-week-of-*` with group title `↑ $120`). Uses the compact `marketsGroupItemTitle` arrow form when available, otherwise falls back to parsing the free-text `marketsQuestion` (`$N` + `dip`/`reach` keywords + explicit `(LOW)`/`(HIGH)` annotations).

### Fixed
- `parse_title_bounds` arrow regex now tolerates an optional `$` prefix so titles like `↑ $120` (NFLX weeklies) parse alongside bare-number titles like `↑ 200,000`.

---

## [0.6.25] — 2026-04-14

### Added
- Neg-risk support for `redeem_positions` — pass `neg_risk=True` with `amounts=[yes_amount, no_amount]` to route through the NegRiskAdapter contract.
- `examples/redeem_positions.py` — streamlined redeem example with auto-detection of market type, gas estimation, `--dry-run`, `--all`, and `--condition-id` flags.

---

## [0.6.24] — 2026-04-13

### Added
- `GasEstimate` TypedDict and `estimate_ctf_tx()` public method for gas cost estimation.
- `estimate=True` parameter on `merge_positions`, `split_position`, `redeem_positions`, `approve_collateral` — returns gas estimate without sending.
- `auto_approve=True` parameter on `merge_positions` and `split_position` — checks on-chain USDC.e allowance and approves if needed.
- Proxy wallet support for CTF operations — auto-detects when tokens live in a proxy wallet and routes through Polymarket's GSN relayer.
- `examples/merge_positions.py` — focused example for merging Yes+No tokens back into USDC.e with dry-run and gas estimation.

### Fixed
- Gas estimation now uses `state_override` for proxy wallets (which have 0 MATIC) to simulate correctly.
- `.env.example` corrected to use `POLYMARKET_RELAYER_API_KEY_ADDRESS` (matching actual env var name).
- Vectorized `coalesce_end_date_from_title` in `parsers.py`.

---

## [0.6.21] — 2026-04-10

### Added
- `expand_user` parameter on `get_xtracker_trackings` and `get_xtracker_user_trackings` — flattens nested `user` dict into prefixed columns (`userHandle`, `userPlatform`, etc.).
- `expand_trackings` parameter on `get_xtracker_users` — flattens nested `trackings` list into rows with prefixed columns.
- `expand_count` parameter on `get_xtracker_users` (default `True`) — flattens `_count` dict into columns like `countPosts`.
- `examples/xtracker_overview.py` — end-to-end demo of all 7 XTracker endpoints.

### Fixed
- `get_xtracker_user` and `get_xtracker_tracking` now run through `preprocess_dict` so datetime fields (`startDate`, `endDate`, `createdAt`, etc.) are parsed as `pd.Timestamp`.
- `get_xtracker_user` materialises the nested `trackings` list as a `DataFrame[XTrackerTrackingSchema]`.
- `get_xtracker_tracking` preprocesses the nested `user` dict.
- Added `date`, `importedAt`, `lastSync` to `DEFAULT_STR_DATETIME_COLUMNS`.
- Added `user`, `trackings`, `count` to `_EXPAND_PREFIXES` so prefixed columns are datetime-parsed after expansion.

---

## [0.6.20] — 2026-04-09

### Added
- **XTracker mixin** — new `polymarket_pandas.mixins._xtracker.XTrackerMixin` exposing all 7 endpoints of the `xtracker.polymarket.com` post-counter API (no auth, `{success, data, message}` envelope auto-unwrapped). Powers the "# tweets / # posts in window" markets (Elon, Trump, Zelenskyy, etc.).
  - Methods: `get_xtracker_users`, `get_xtracker_user`, `get_xtracker_user_posts`, `get_xtracker_user_trackings`, `get_xtracker_trackings`, `get_xtracker_tracking`, `get_xtracker_metrics`.
  - 5 new pandera schemas (`XTrackerUserSchema`, `XTrackerPostSchema`, `XTrackerTrackingSchema`, `XTrackerDailyStatSchema`, `XTrackerMetricSchema`) and 2 TypedDicts (`XTrackerUser`, `XTrackerTracking`).
  - `_request_xtracker` request helper on `PolymarketPandas` using a new `xtracker_url` field, plus MCP tool wrappers.
- New `polymarket_pandas.parsers` module with vectorized regex enrichers for `marketsGroupItemTitle`:
  - `classify_event_structure(data)` — labels each event as Single-Outcome / negRisk Multi-Outcome / Non-negRisk Multi-Outcome / Directional / Bracketed.
  - `parse_title_bounds(data)` — extracts `boundLow`, `boundHigh`, `direction`, `threshold` from bracket / arrow titles.
  - `parse_title_sports(data)` — extracts `spreadLine`, `totalLine`, `side` from sports market titles ("Spread -1.5", "O/U 8.5", "Over 2.5"). `spreadLine` is named to avoid colliding with the unrelated `MarketSchema.spread` API field.
  - `coalesce_end_date_from_title(data)` — fills NaT `marketsEndDate` by parsing the "Month Day" string in the title, inferring year from `marketsStartDate` with Dec→Jan rollover handling.
- `PolymarketPandas.fetch_sports_event(sports_market_type, ...)` — convenience method on `GammaMixin` that finds an open event containing markets of the given type via `get_markets(sports_market_types=[...])` and re-fetches the parent event with markets sliced by `conditionId`. Pass-through filter kwargs mirror `get_markets` (`limit`, `order`, `ascending`, `closed`, date / liquidity / volume ranges, `tag_id`).
- `examples/market_structures.py` — end-to-end demo printing one representative event for each of the 5 core structures plus 5 hand-picked extras (BTC up/down daily, Sports Moneyline / Spreads / Totals / Both Teams to Score).
- 22 new unit tests in `tests/test_parsers.py` covering the four parsers, plus 2 mocked HTTP tests in `tests/test_unit.py` for `fetch_sports_event`.

### Fixed
- `EventSchema.negRisk` — switched dtype from `bool` to `pd.BooleanDtype` so the upstream API's null values survive validation. Live `test_get_events` was crashing with `Could not coerce data_container into type bool` after Polymarket started returning `<NA>` for `negRisk` on some events.

---

## [0.6.19] — 2026-04-09

### Added
- Builder attribution on order placement: when `POLYMARKET_BUILDER_API_KEY` / `_SECRET` / `_PASSPHRASE` are configured, `place_order`, `place_orders`, `submit_order`, and `submit_orders` automatically attach `POLY_BUILDER_*` headers alongside L2 auth so matched fills are credited to the builder for rewards. Header-only — no changes to the signed EIP-712 order struct.
- `_request_clob_private(..., attribute=True)` keyword flag and `_has_builder_creds()` helper.
- `builder_client` test fixture and 4 unit tests covering header attach/skip behavior.

---

## [0.6.17] — 2026-04-03

### Fixed
- `ActiveOrderSchema.expiration` — changed from `str` to `pa.Timestamp` (matches preprocessing)

---

## [0.6.16] — 2026-04-03

### Fixed
- `ActiveOrderSchema` — added missing `expiration` and `createdAt` fields
- `PositionSchema` — added missing `endDate` and `eventId` fields

---

## [0.6.15] — 2026-04-03

### Added
- `PlaceOrderSchema` and `SubmitOrderSchema` pandera input validation for `place_orders` / `submit_orders`
- `post_only` parameter on `place_order`, `submit_order`, `place_orders`, `submit_orders`
- 15-order batch limit validation on `place_orders`

### Changed
- `SubmitOrderSchema` uses camelCase column names (`tokenId`, `orderType`, `postOnly`, `negRisk`, `tickSize`, `feeRateBps`) to match API convention
- `OrderSchema` is now an alias for `PlaceOrderSchema`

---

## [0.6.14] — 2026-04-02

### Changed
- Renamed `FIXIE_URL` env var to `HTTP_PROXY` for proxy configuration

---

## [0.6.13] — 2026-04-02

### Added
- **13 new pandera schemas** — every `pd.DataFrame`-returning method now has a
  schema: `TagSchema`, `SeriesSchema`, `CommentSchema`, `SportsMetadataSchema`,
  `TeamSchema`, `MidpointSchema`, `MarketPriceSchema`, `LastTradePricesSchema`,
  `BuilderVolumeSchema`, `PositionValueSchema`, `BridgeSupportedAssetSchema`,
  `BridgeTransactionSchema`. Return types updated to `DataFrame[Schema]`.
- **`ms_int_datetime_columns`** — new preprocessing field for Unix-millisecond
  timestamps (`createdTimeMs`, `estCheckoutTimeMs`), parallel to the existing
  `int_datetime_columns` (seconds). Wired through client, sync WS, async WS.
- **58 live integration tests** covering all non-authenticated endpoints with
  pandera schema validation against real API responses.

### Fixed
- **`get_price_history`** — now extracts the `history` list from the response
  dict and converts `t` to UTC `datetime64`. Previously returned a single
  `history` column of raw dicts.
- **`get_bridge_supported_assets`** — now returns a `DataFrame` with `token`
  object flattened via `json_normalize` into `tokenName`, `tokenSymbol`,
  `tokenAddress`, `tokenDecimals` columns. Previously returned `list[dict]`.
- **`PriceHistorySchema.t`** — changed from `int` to `Timestamp`.
- **`CurrentRewardSchema.sponsorsCount`** — changed from `int` to `float`
  (API returns NaN when absent).

---

## [0.6.12] — 2026-03-31

### Fixed
- **`get_accounting_snapshot`** now runs `preprocess_dataframe` on CSV data —
  `valuationTime` parsed as datetime, numeric coercion applied.
- Added `valuationTime` to `DEFAULT_STR_DATETIME_COLUMNS`.

### Added
- `examples/accounting_snapshot.py` — download and display user portfolio.

---

## [0.6.11] — 2026-03-31

### Changed
- **`pd.Timestamp` accepted in datetime filter params** — `get_price_history`
  (`startTs`, `endTs`), `get_user_trades` / `get_builder_trades` (`before`,
  `after`), `get_user_activity` (`start`, `end`), and their `_all` variants
  now accept `pd.Timestamp` in addition to `int`/`str`. Timestamps are
  auto-converted to Unix seconds (CLOB) or ISO-8601 (Gamma) as needed.
- `filter_params` now also converts `datetime.datetime` to ISO-8601.

---

## [0.6.9] — 2026-03-31

### Fixed
- **Bool columns now use nullable `BooleanDtype`** — previously `astype(bool)`
  silently converted NaN to `True`. Now NaN is preserved as `pd.NA`.
- **Added 12 missing bool columns** to `DEFAULT_BOOL_COLUMNS`:
  `acceptingOrders`, `automaticallyActive`, `enableOrderBook`, `ended`,
  `featured`, `live`, `negRisk`, `negRiskAugmented`, `new`,
  `requiresTranslation`, `showAllOutcomes`, `showMarketImages`. These (and
  their `events*`/`markets*` prefixed variants) were staying as `object` dtype.
- **Added `finishedTimestamp`** to `DEFAULT_STR_DATETIME_COLUMNS` — sports
  events `eventsFinishedTimestamp` was not being parsed as datetime.

---

## [0.6.8] — 2026-03-31

### Added
- **`expand_rewards_config`** flag on `get_rewards_markets_current`,
  `get_rewards_markets_multi`, `get_rewards_market`, `get_rewards_user_markets`
  (and their `_all` variants) — flattens nested `rewards_config` list into one
  row per config entry with `rewardsConfig*` prefixed columns.
- **`expand_tokens`** flag on `get_rewards_markets_multi`, `get_rewards_market`,
  `get_rewards_user_markets` — flattens nested `tokens` list into rows with
  `tokensTokenId`, `tokensOutcome`, `tokensPrice` columns.
- **`expand_earnings`** flag on `get_rewards_user_markets` — flattens nested
  `earnings` list into rows with `earningsAssetAddress`, `earningsEarnings`,
  `earningsAssetRate` columns.
- Pandera schemas updated with all expanded field annotations.
- `examples/async_trades_orders.py` — async client example fetching trades and
  active orders.

### Fixed
- **Unix-timestamp datetime columns** (`createdAt`, `matchTime`, etc.) from CLOB
  API were parsed as 1970 dates. `preprocess_dataframe` now auto-detects numeric
  strings/ints (>1e9) in `str_datetime_columns` and converts with `unit="s"`.

---

## [0.6.7] — 2026-03-30

### Fixed
- `expand_dataframe` TypeError on NaN fields (e.g. `eventsSeries`).

---

## [0.6.6] — 2026-03-30

### Changed
- **Replaced `pd.json_normalize` with manual list-of-dicts construction** in
  `expand_dataframe` — 2.8x faster, eliminates `PerformanceWarning: DataFrame
  is highly fragmented`, and correctly preserves nested dicts for cascading
  expansion (fixes `expand_series` silently not working).

---

## [0.6.5] — 2026-03-30

### Added
- **`expand_outcomes=False`** flag on `get_markets`, `get_events`, and their `_all`
  variants — explodes `outcomes`, `outcomePrices`, and `clobTokenIds` as parallel
  lists into one row per outcome. Takes precedence over `expand_clob_token_ids`.
- **`feeSchedule` dict flattening** — nested dict columns are automatically expanded
  into prefixed scalar columns (e.g. `feeScheduleMaker`, `feeScheduleTaker`).
  Configurable via `dict_columns` on the client.
- **`outcomePrices` always coerced to `list[float]`** — even without
  `expand_outcomes`, list values are floats instead of strings.
- **`umaBond` / `umaReward`** added to numeric columns — auto-coerced from strings.

---

## [0.6.4] — 2026-03-30

### Added
- **11 new `_all` auto-pagination methods** — `get_series_all`, `get_teams_all`,
  `get_comments_all`, `get_comments_by_user_address_all`, `get_positions_all`,
  `get_closed_positions_all`, `get_market_positions_all`, `get_trades_all`,
  `get_user_activity_all`, `get_leaderboard_all`, `get_builder_leaderboard_all`.
  All available on both `PolymarketPandas` and `AsyncPolymarketPandas`.
- **Explicit parameter signatures on all 22 `_all` methods** — mirrors base
  method parameters (minus `offset`/`next_cursor`) for full IDE autocomplete and
  type checking. No more `**kwargs`.

### Fixed
- **`_autopage` now works correctly with `expand_*` flags** — pagination uses
  pre-expansion API record count (`df.attrs["_raw_count"]`) so offset tracking
  isn't inflated by `expand_dataframe` or `explode`.
- **Fixed `_autopage` infinite loop** when `use_tqdm=False` — the stop condition
  (`len_pages`) was only updated inside the progress bar branch.
- **Fixed `eventsSeries` KeyError** in `get_markets` — not all records have a
  series after event expansion; now guarded with column existence check.

### Changed
- Default `limit` set to `300` across all Gamma endpoints (`get_markets`,
  `get_events`, `get_series`, `get_teams`, `get_comments`,
  `get_comments_by_user_address`). Was `500` or `None`.

---

## [0.6.3] — 2026-03-30

### Fixed
- PyPI release for v0.6.4 changes (intermediate version).

---

## [0.6.2] — 2026-03-28

### Added
- **MCP server expanded to 74 tools** — near-complete coverage of the Polymarket
  API. Only CTF on-chain ops, relayer ops, and batch DataFrame-input methods excluded.
- New MCP tools: `cancel_orders_from_market`, `send_heartbeat`, `get_order_scoring`,
  `create_api_key`, `delete_api_key`, `get_event_by_id`, `get_tag_by_slug/id`,
  `get_related_tags`, `get_market_tags`, `get_event_tags`, `get_series_by_id`,
  `get_sports_market_types`, `get_comment_by_id`, `get_comments_by_user`,
  `get_server_time`, `get_fee_rate`, `get_market_price`, `get_positions_value`,
  `get_live_volume`, `get_traded_markets_count`, `get_builder_volume`,
  `get_rewards_market`, `get_rewards_earnings`, `get_rewards_earnings_total`,
  `get_rewards_percentages`, `get_rewards_user_markets`.

---

## [0.6.1] — 2026-03-28

### Added
- **MCP server expanded to 47 tools** — all SDK endpoints now exposed with every
  API parameter. LLM controls output size via `max_rows`.
- **6 write tools**: `build_order`, `place_order`, `cancel_order`, `cancel_orders`,
  `cancel_all_orders`, `derive_api_key`.
- `POLYMARKET_MCP_MAX_ROWS` env var for default table output size (default 200).
- Each tool's `max_rows` param overrides per-call (0=unlimited).

---

## [0.6.0] — 2026-03-28

### Added
- **MCP server (FastMCP)** — query Polymarket data from any MCP client (Claude Code,
  Claude Desktop, etc.) with 22 read-only tools.
  `pip install polymarket-pandas[mcp]` then `polymarket-mcp`.
- **Tags explorer page** with all `get_tags` parameters.
- All endpoint parameters exposed as interactive sidebar controls in explorer.

### Fixed
- Added `umaResolutionStatuses` to JSON columns for proper parsing.
- Fixed `json_normalize` PerformanceWarning with `.copy()` defragmentation.

---

## [0.5.0] — 2026-03-28

### Added
- **Streamlit Explorer Dashboard** — interactive dashboard for exploring all public
  Polymarket endpoints with Plotly visualizations. 10 pages: Markets, Events, Series,
  Orderbook, Prices, Positions, Trades, Leaderboard, Rewards, Bridge.
  `pip install polymarket-pandas[explorer]` then `polymarket-explore`.

---

## [0.4.1] — 2026-03-27

### Fixed
- Fix pandera FutureWarning: use `pandera.pandas` submodule instead of deprecated
  top-level import.

---

## [0.4.0] — 2026-03-27

### Added
- **12 TypedDicts** for dict-returning endpoints — IDE autocomplete for all keys.
- **11 specific CursorPage types** (e.g. `OrdersCursorPage`, `UserTradesCursorPage`)
  with `data: DataFrame[Schema]`.
- **22 pandera DataFrameModel schemas** — field names verified against official
  Polymarket OpenAPI specs, `strict=False`, `coerce=True`.
- `build_order(expiration=...)` now accepts `pd.Timestamp`, ISO-8601 strings, or
  `datetime` in addition to `int`.
- `get_user_trades_all()` and `get_active_orders_all()` — auto-paginate cursor methods.
- `to_unix_timestamp()` helper in `utils.py`.

### Fixed
- `get_active_orders` / `get_user_trades` — was wrapping pagination envelope into
  DataFrame columns. Now returns proper `OrdersCursorPage` / `UserTradesCursorPage`.

### Breaking
- `get_active_orders()` and `get_user_trades()` now return cursor-paginated dicts
  instead of DataFrames. Access the DataFrame via `result["data"]`.

---

## [0.3.1] — 2026-03-26

### Fixed
- Fix `AsyncPolymarketPandas` missing `get_tick_size`, `get_neg_risk`, `get_fee_rate`
  and `preprocess_dict` methods. Async wrapper generator now uses `callable()` to
  detect all public methods including `cachetools.cachedmethod` descriptors
  (102 methods, up from 98).

---

## [0.3.0] — 2026-03-26

### Added
- **`AsyncPolymarketPandas`** — async version of the HTTP client using
  composition + `ThreadPoolExecutor`. All 98 public methods auto-generated
  as `async def` wrappers. Supports `async with` context manager.
- **`AsyncPolymarketWebSocket`** — native async WebSocket client using
  `websockets` library. Supports `async for event_type, payload in session:`
  iteration, auto-reconnection with exponential backoff, and async
  `subscribe()`/`unsubscribe()`.
- **`amount_usdc` parameter** on `split_position()` and `merge_positions()` —
  convenience alternative to raw base-unit `amount` (e.g. `amount_usdc=1.0`
  instead of `amount=1_000_000`).
- **Auto-set credentials** — `derive_api_key()` and `create_api_key()` now
  automatically set `_api_key`, `_api_secret`, `_api_passphrase` on the client.
- **`preprocess_dict()`** — full type coercion (numeric, datetime, bool, JSON)
  for single-dict responses. Applied to `get_market_by_id()` and
  `get_market_by_slug()` so JSON-string fields like `clobTokenIds` are
  automatically parsed to Python lists.
- `websockets>=13.0` added to core dependencies.
- `pytest-asyncio` added to dev dependencies.
- 16 new async unit tests (`tests/test_async_unit.py`).

---

## [0.2.0] — 2026-03-26

### Added
- **CTFMixin** — on-chain merge, split, redeem positions via Polymarket's
  Conditional Token Framework contracts on Polygon. Requires optional `web3`
  dependency: `pip install polymarket-pandas[ctf]`.
- **Order signing** — `build_order()` with full EIP-712 signing, tick-size-aware
  amount calculation, and automatic market parameter resolution.
- **`submit_order` / `submit_orders`** — high-level convenience methods that
  auto-fetch `neg_risk`, `tick_size`, `fee_rate_bps` from the CLOB API (cached).
- `submit_orders` accepts a **pandas DataFrame** and batch-submits via the
  `/orders` endpoint (groups of 15).
- **`instance_cache`** decorator (`utils.py`) backed by `cachetools` — per-instance
  method caching with optional TTL. Used for `get_tick_size` (300s TTL),
  `get_neg_risk`, and `get_fee_rate` (permanent).
- `_ENV_DEFAULTS` dict — env var resolution deferred to `__post_init__`, so
  `load_dotenv()` can run before client construction.
- Auto-derive `address` from `private_key` when not explicitly set.
- `proxy_url`, `rpc_url`, `timeout` fields on the client dataclass.
- Column default tuples extracted to `utils.py` constants
  (`DEFAULT_NUMERIC_COLUMNS`, etc.).
- `LICENSE` file (Apache-2.0).
- `CONTRIBUTING.md` with development setup and PR guidelines.
- PyPI publish workflow (`.github/workflows/release.yml`) — triggered on
  GitHub release, uses trusted publisher (OIDC).
- Custom exception hierarchy: `PolymarketError`, `PolymarketAPIError`,
  `PolymarketAuthError`, `PolymarketRateLimitError` — all exported from the
  top-level package.
- HTTP error mapping in `_handle_response`: 401/403 → `PolymarketAuthError`,
  429 → `PolymarketRateLimitError`, other non-2xx → `PolymarketAPIError`.
- Auth guards `_require_l2_auth` / `_require_builder_auth` raise
  `PolymarketAuthError` with a descriptive message before any network call is
  attempted.
- `close()`, `__enter__`, `__exit__` on `PolymarketPandas` for proper
  connection-pool cleanup and context-manager support.
- `py.typed` marker (PEP 561) — downstream type checkers now see the package's
  annotations.
- `expand_column_lists` utility in `utils.py`; `"series"` removed from prefix
  list (was generating unused column variants).
- Relayer API endpoints: `check_safe_deployed`, `get_relayer_transaction`,
  `get_relayer_nonce`, `get_relayer_transactions`, `get_relay_payload`,
  `submit_transaction`, `get_relayer_api_keys`.
- Bridge API endpoints: `create_deposit_address`, `create_withdrawal_address`,
  `get_bridge_quote`, `get_bridge_supported_assets`,
  `get_bridge_transaction_status`.
- CLOB endpoints: `get_sampling_markets`, `get_simplified_markets`,
  `get_sampling_simplified_markets` (cursor-paginated), plus `_all` variants.
- `get_builder_trades` (CLOB, builder auth).
- `get_rebates` (CLOB, public).
- Cursor-based auto-pager `_autopage_cursor` and `*_all` helpers for the three
  new cursor-paginated endpoints.
- `PolymarketWebSocket` with channels: `market_channel`, `user_channel`,
  `sports_channel`, `rtds_channel`.
- `PolymarketWebSocket.from_client` class method to share column config with an
  existing HTTP client.
- Unit test suite (`tests/test_unit.py`) with 75+ tests, using `pytest-httpx`
  for HTTP mocking — no live API calls required.
- CI workflow (`.github/workflows/ci.yml`): lint, typecheck, unit tests.
- `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` in `pyproject.toml`.
- Dev optional dependencies: `pytest`, `pytest-httpx`, `ruff`, `mypy`,
  `pandas-stubs`.
- PyPI classifiers and keywords.

### Fixed
- `_round_normal` now uses `Decimal` with `ROUND_HALF_UP` to avoid float
  representation bugs (e.g. `round(0.85 * 10) = 8` instead of 9).
- `cancel_orders_from_market` now sends params as JSON body (was query string,
  causing "Invalid order payload" errors).
- CTF `build_transaction` calls now pass `from` address (was zero-address,
  causing "approve from the zero address" reverts).
- POA middleware injected for Polygon compatibility in CTF operations.
- EIP-1559 / legacy gas field conflict resolved in `_send_ctf_tx`.
- `filter_params(None)` now returns `{}` instead of `None`, preventing a silent
  `TypeError` in callers.
- `filter_params` no longer calls `pd.notnull` on list values (previously raised
  `ValueError: The truth value of an empty array is ambiguous` for empty lists).
- `OrderSchema` side validation aligned to uppercase `"BUY"` / `"SELL"` to match
  `build_order` output.

### Removed
- `load_dotenv()` at module import time — this was silently mutating `os.environ`
  for any application that imported the library. Callers who relied on `.env`
  loading should call `load_dotenv()` themselves before constructing a client.
- Overly tight upper-bound version pins on `eth-account` and `httpx`.

---

## [0.1.0] — Initial release

### Added
- `PolymarketPandas` HTTP client wrapping the full Gamma, Data, and CLOB REST
  APIs with automatic DataFrame output and type coercion.
- Gamma API: markets, events, tags, series, sports, comments, search, profiles.
- Data API: positions, closed positions, market positions, top holders, positions
  value, leaderboard, trades, user activity, accounting snapshot, live volume,
  open interest, traded markets count, builder leaderboard, builder volume.
- CLOB public API: order book, prices, midpoints, spreads, last trade prices,
  fee rate, tick size, price history, server time.
- CLOB private API (L2 HMAC auth): user trades, orders (get/place/cancel),
  order scoring, heartbeat.
- CLOB auth management (L1 EIP-712): create/derive/get/delete API keys.
- Auto-pagination helpers `get_markets_all`, `get_events_all`, `get_tags_all`.
- `preprocess_dataframe` pipeline: snake → camelCase column rename, numeric /
  datetime / bool / JSON-string coercion, drop of `icon` / `image` columns.
