# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
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
- Unit test suite (`tests/test_unit.py`) with 33 tests, using `pytest-httpx`
  for HTTP mocking — no live API calls required.
- CI workflow (`.github/workflows/ci.yml`): lint, typecheck, unit tests.
- `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` in `pyproject.toml`.
- Dev optional dependencies: `pytest`, `pytest-httpx`, `ruff`, `mypy`,
  `pandas-stubs`.
- PyPI classifiers and keywords.

### Fixed
- `filter_params(None)` now returns `{}` instead of `None`, preventing a silent
  `TypeError` in callers.
- `filter_params` no longer calls `pd.notnull` on list values (previously raised
  `ValueError: The truth value of an empty array is ambiguous` for empty lists).
- `__post_init__` expansion loop used `"series"` as a prefix, generating column
  names (`seriesEndDate`, etc.) that were never produced by any `expand_dataframe`
  call.

### Removed
- `load_dotenv()` at module import time — this was silently mutating `os.environ`
  for any application that imported the library. Callers who relied on `.env`
  loading should call `load_dotenv()` themselves before constructing a client.
- Unused dependencies `cachetools`, `pydantic`, `python-dateutil` from
  `pyproject.toml`.
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
