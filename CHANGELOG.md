# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

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
