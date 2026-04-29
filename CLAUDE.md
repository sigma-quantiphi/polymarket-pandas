# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev deps
uv pip install -e ".[dev]"

# Install with CTF (on-chain merge/split/redeem) support
uv pip install -e ".[ctf]"

# Run unit tests (mocked — no live API calls)
uv run pytest tests/test_unit.py -v

# Run a single test
uv run pytest tests/test_unit.py::test_get_orderbook_returns_dataframe -v

# Lint
uv run ruff check polymarket_pandas/

# Format
uv run ruff format polymarket_pandas/

# Type check
uv run mypy polymarket_pandas/

# Run async tests
uv run pytest tests/test_async_unit.py -v

# Import sanity check
uv run python -c "from polymarket_pandas import PolymarketPandas, AsyncPolymarketPandas, PolymarketWebSocket, AsyncPolymarketWebSocket"
```

## Package structure

```
polymarket_pandas/
  __init__.py          # Public exports (6 classes + 4 exceptions + 24 TypedDicts + 42 schemas)
  client.py            # PolymarketPandas dataclass — core infra + build_order
  async_client.py      # AsyncPolymarketPandas — async wrapper via composition + ThreadPoolExecutor
  exceptions.py        # PolymarketError hierarchy
  types.py             # TypedDicts for dict-returning endpoints (CursorPage, SignedOrder, etc.)
  schemas.py           # pandera DataFrameModels for DataFrame-returning endpoints
  utils.py             # Stateless helpers: preprocess_dataframe, preprocess_dict, filter_params,
  #                      instance_cache, to_unix_timestamp, etc.
  parsers.py           # Vectorized regex enrichers for marketsGroupItemTitle:
  #                      classify_event_structure, parse_title_bounds, parse_title_sports,
  #                      coalesce_end_date_from_title
  ws.py                # PolymarketWebSocket + PolymarketWebSocketSession (sync, websocket-client)
  async_ws.py          # AsyncPolymarketWebSocket + AsyncPolymarketWebSocketSession (async, websockets)
  order_schema.py      # pandera DataFrameModels for validating place_orders / submit_orders input
  py.typed             # PEP 561 marker
  mixins/
    __init__.py        # Re-exports all 9 mixin classes
    _gamma.py          # GammaMixin   — markets (offset + keyset pagination), events, tags,
    #                                    series, sports, comments, search, profiles,
    #                                    fetch_sports_event (multi-call discovery helper)
    _data.py           # DataMixin    — positions, trades, leaderboard, accounting snapshot, builders
    _clob_public.py    # ClobPublicMixin — orderbook, prices, midpoints, spreads, price history,
    #                                      sampling/simplified markets, builder trades, rebates
    _clob_private.py   # ClobPrivateMixin — user trades, orders (get/place/cancel), heartbeat, API keys
    _rewards.py        # RewardsMixin  — reward configs, earnings, percentages, user reward markets
    _relayer.py        # RelayerMixin — Safe deployment, nonces, transactions, relay payload, submit
    _bridge.py         # BridgeMixin  — deposit/withdrawal addresses, quotes, supported assets, status
    _ctf.py            # CTFMixin     — on-chain merge, split, redeem positions + batch_ctf_ops
    #                                    (bundled proxy-relayed inventory ops; requires web3)
    _uma.py            # UmaMixin      — UMA CTF Adapter + OptimisticOracleV2 —
    #                                    get_uma_question, get_oo_request,
    #                                    get_uma_state, propose_price,
    #                                    dispute_price, settle_oo, resolve_market
    _xtracker.py       # XTrackerMixin — xtracker.polymarket.com post-counter API
    #                                    (X / Truth Social tracking, feeds counter markets)
```

## Entity Relationships

Polymarket entities form a hierarchy: **Series → Events → Markets → Tokens**. The SDK bridges two parallel ID systems:

- **Gamma API** (discovery): uses slugs, numeric IDs, nested JSON. Methods: `get_markets`, `get_events`, `get_series`.
- **CLOB/Data APIs** (trading): uses `conditionId` (1:1 with market) and `clobTokenIds` (1 per outcome). Methods: `get_orderbook`, `get_positions`, `get_user_trades`, `build_order`.

Typical flow: discover via Gamma → extract `conditionId`/`clobTokenIds` → query CLOB/Data.

**Gotcha**: The `market` parameter means **token ID** in the Data API (`get_positions`) but **condition ID** in CLOB private (`get_user_trades`).

Full reference with workflows, expansion logic, and lookup methods: `.claude/skills/entity-relationships.md`

## Architecture

### `PolymarketPandas` — HTTP client

A `@dataclass` that inherits from all 9 mixins. `client.py` contains infrastructure, order building, and pagination; all endpoint methods live in the mixins. The class has seven base URLs:

| Field | Base URL | Auth |
|---|---|---|
| `data_url` | `https://data-api.polymarket.com/` | none |
| `gamma_url` | `https://gamma-api.polymarket.com/` | none |
| `clob_url` | `https://clob.polymarket.com/` | none / L2 / builder |
| `relayer_url` | `https://relayer-v2.polymarket.com/` | relayer key |
| `bridge_url` | `https://bridge.polymarket.com/` | none |
| `xtracker_url` | `https://xtracker.polymarket.com/api/` | none |
| `rpc_url` | `https://polygon-rpc.com` (configurable) | none (used by CTFMixin) |

**Request helpers** (all call `_handle_response` which maps HTTP errors to custom exceptions):
- `_request_data`, `_request_gamma`, `_request_clob` — unauthenticated
- `_request_clob_private` — L2 HMAC auth, calls `_require_l2_auth()` guard first
- `_request_clob_builder` — builder HMAC auth, calls `_require_builder_auth()` guard first
- `_request_relayer` — accepts optional `auth_headers` dict (relayer API key)
- `_request_bridge` — unauthenticated
- `_request_xtracker` — unauthenticated, auto-unwraps the `{success, data, message}` envelope and raises `PolymarketAPIError` when `success=false`

**Authentication layers:**
- **L1 (EIP-712)** — `_build_l1_headers`: used only for `create_api_key` / `derive_api_key`. Requires `private_key`.
- **L2 (HMAC-SHA256)** — `_build_l2_headers`: all private CLOB endpoints. Requires `_api_key` / `_api_secret` / `_api_passphrase`.
- **Builder HMAC** — `_build_builder_headers`: same scheme as L2 but with `POLY_BUILDER_*` headers and builder credentials. Used by `_request_clob_builder` for `get_builder_trades` only. **V2 (2026-04-28 cutover): no longer attached to `place_order` / `place_orders`** — builder attribution is now per-order via the signed `builder` (bytes32) field. Set `builder_code=` on the constructor or `POLYMARKET_BUILDER_CODE` env var; per-call override via `build_order(..., builder_code=...)`.
- **Relayer key** — plain headers `RELAYER_API_KEY` + `RELAYER_API_KEY_ADDRESS` (no signing). Built by `_relayer_auth_headers()`.

All credentials fall back to env vars (`POLYMARKET_ADDRESS`, `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_API_KEY`, `POLYMARKET_BUILDER_CODE`, etc.).

### Exceptions (`exceptions.py`)

```
PolymarketError
└── PolymarketAPIError(status_code, url, detail)
    ├── PolymarketAuthError     — 401/403 or missing credentials
    └── PolymarketRateLimitError — 429
```

All four are exported from the top-level package. `_handle_response` maps HTTP errors to the hierarchy. `_require_l2_auth` / `_require_builder_auth` raise `PolymarketAuthError` before any network call if credentials are missing.

`_extract(data, key)` raises `PolymarketAPIError` with context when an expected key is missing from a response dict — used by scalar-returning endpoints like `get_tick_size`, `get_midpoint_price`, etc.

### Order building (`build_order`) — V2

`build_order(token_id, price, size, side, ...)` in `client.py` constructs and EIP-712-signs a CLOB **V2** order. Returns a `SignedOrder` TypedDict ready for `place_order()`.

**V1 fields removed (2026-04-28 cutover):** `taker`, `expiration`, `nonce`, `feeRateBps`. Fees are determined by the operator at match time (no longer signed). Order uniqueness comes from `timestamp` (ms), not nonce. Cancellation is via the existing `/cancel-*` REST endpoints (the on-chain nonce wipe is gone).

**V2 fields added:** `timestamp` (uint256, ms), `metadata` (bytes32, defaults zero), `builder` (bytes32, defaults zero) — all in the signed struct.

**Signing details:**
- **Domain**: `name="Polymarket CTF Exchange"`, `version="2"`, `chainId=137`, `verifyingContract=<exchange>`
- **V2 exchange contracts** (Polygon mainnet):
  - Standard: `CTF_EXCHANGE = 0xE111180000d2663C0091e4f400237545B87B996B`
  - Neg-risk: `NEG_RISK_CTF_EXCHANGE = 0xe2222d279d744050d28e00520010520000310F59`
- **Order struct (signed; field order matters for the EIP-712 hash):** `salt, maker, signer, tokenId, makerAmount, takerAmount, side, signatureType, timestamp, metadata, builder` — 11 fields total.
- **Amount calculation**: `makerAmount` / `takerAmount` depend on `side`:
  - BUY: makerAmount = pUSD spent = `size * price * 1e6`, takerAmount = shares received = `size * 1e6`
  - SELL: makerAmount = shares sold = `size * 1e6`, takerAmount = pUSD received = `size * price * 1e6`
- **Tick-size rounding**: price/size decimals derived from tick_size (0.1→1dp, 0.01→2dp, 0.001→3dp, 0.0001→4dp)
- **Signature types**: 0=EOA, 1=POLY_PROXY (default), 2=POLY_GNOSIS_SAFE
- **Builder code helper**: `_normalize_builder_code(s)` left-pads short hex to 32 bytes; `None`/empty → zero bytes32.

### CTFMixin — On-chain operations (`_ctf.py`)

On-chain merge / split / redeem via Polymarket's Conditional Token Framework contracts on Polygon. Requires `web3` optional dependency: `pip install polymarket-pandas[ctf]`.

**V2 collateral migration (2026-04-28):** USDC.e → pUSD. The CTF / NegRiskAdapter contracts are unchanged on chain but now denominate positions in pUSD. USDC.e remains the underlying asset for `wrap_collateral` / `unwrap_collateral`.

**Contract addresses (Polygon mainnet):**

| Contract | Address |
|---|---|
| ConditionalTokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| NegRiskAdapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| pUSD (V2 collateral) | `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` |
| USDC.e (underlying) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| CollateralOnramp (`wrap`) | `0x93070a847efEf7F70739046A929D47a521F5B8ee` |
| CollateralOfframp (`unwrap`) | `0x2957922Eb93258b93368531d39fAcCA3B4dC5854` |
| ProxyFactory (GSN) | `0xaB45c5A4B0c941a2F231C04C3f49182e1A254052` |
| RelayHub (GSN) | `0xD216153c06E857cD7f72665E0aF1d7D82172F494` |

**Methods:**

| Method | Description |
|---|---|
| `wrap_collateral(amount=None, amount_usdc=None, to=None, auto_approve=False, estimate=False)` | Wrap USDC.e → pUSD via `CollateralOnramp.wrap()` |
| `unwrap_collateral(amount=None, amount_usdc=None, to=None, auto_approve=False, estimate=False)` | Unwrap pUSD → USDC.e via `CollateralOfframp.unwrap()` |
| `split_position(condition_id, amount=None, amount_usdc=None, neg_risk=False, auto_approve=False, estimate=False)` | Split pUSD into Yes + No outcome tokens |
| `merge_positions(condition_id, amount=None, amount_usdc=None, neg_risk=False, auto_approve=False, estimate=False)` | Merge Yes + No tokens back into pUSD |
| `redeem_positions(condition_id, index_sets=None, neg_risk=False, amounts=None, estimate=False)` | Redeem winning tokens after market resolution (neg-risk requires `amounts=[yes, no]`) |
| `approve_collateral(spender=None, amount=None, token=PUSD, estimate=False)` | Approve a CTF / onramp / offramp contract to spend pUSD (or USDC.e via `token=USDC_E`) |
| `batch_ctf_ops(ops, auto_approve=False, estimate=False)` | Bundle N split/merge/redeem/convert/wrap/unwrap ops into a single proxy-relayed tx. `ops` is a `list[dict]` or `DataFrame`. Proxy-wallet only — raises `PolymarketAuthError` for EOAs. Allowance checks are aggregated per `(spender, token)` pair. |
| `estimate_ctf_tx(tx_data)` | Estimate gas cost without sending; returns `GasEstimate` dict |

**Key design:**
- `web3` is lazily imported — `_require_web3()` initializes `_w3`, `_ct_contract`, `_nr_contract`, `_usdc_contract` on first call. Users who never call CTF methods never need web3 installed.
- Auth guard: `_require_ctf_auth()` checks `private_key` before `_require_web3()` in every public method.
- `neg_risk=True` routes split/merge through NegRiskAdapter (2-param ABI); `False` uses ConditionalTokens (5-param ABI with collateral=pUSD, parentCollectionId=bytes32(0), partition=[1,2]).
- Amounts are in pUSD base units (6 decimals): `1_000_000` = 1.00 pUSD.
- Returns dict with `txHash`, `status`, `blockNumber`, `gasUsed` (when `wait=True`).
- `estimate=True` on any method returns a `GasEstimate` dict (`gas`, `gasPrice`, `costWei`, `costMatic`, `eoaBalance`) without sending.
- `auto_approve=True` on `split_position`/`merge_positions` checks the on-chain USDC.e allowance and sends an approval tx if insufficient.

**Proxy wallet support:**
- `_has_proxy_wallet()` returns `True` when `address` (proxy) differs from the EOA derived from `private_key`.
- When a proxy wallet is detected, CTF operations auto-route through Polymarket's GSN relayer via `_send_ctf_tx_relayed()` instead of sending direct on-chain transactions.
- Proxy signing uses the GSN `"rlx:"` struct hash scheme (`_sign_proxy_tx`) — NOT EIP-712 SafeTx.
- The inner call is wrapped in a `ProxyFactory.proxy(calls)` envelope via `_encode_proxy_calls()`.
- Builder HMAC auth (`_require_builder_auth()`) is required for relayed transactions — the relayer needs `POLY_BUILDER_*` headers to coordinate relay workers correctly.
- Gas estimation for proxy wallets uses `state_override` to simulate from the proxy address (which may have 0 MATIC).
- `_ensure_allowance()` checks the proxy wallet's allowance (not the EOA's) when a proxy is active.

### UmaMixin — Resolution / dispute (`_uma.py`)

Automates the UMA optimistic-oracle flow that resolves Polymarket markets. Shares the `ctf` extra (no new dependency) and reuses `_require_web3`, `_eoa_address`, `_has_proxy_wallet`, `_tx_params`, `_send_ctf_tx`, `_send_ctf_tx_relayed`, `_ensure_allowance`, `estimate_ctf_tx` from `CTFMixin`.

**⚠️ V1 flow only (as of v0.9.3).** The contracts here are V1-era and continue to work for V1-resolved markets. The V2 contracts page lists a different `UmaCtfAdapter` (`0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74`) with a different ABI; calls against it from this mixin produce `BadFunctionCallOutput`. `NegRiskUmaCtfAdapter` is `None` because the historical address has zero on-chain bytecode and the V2 page does not list a replacement; neg-risk UMA calls raise `NotImplementedError`. Full V2 UMA support tracked in #20.

**Contract layer (Polygon):**

| Role | Address |
|---|---|
| UmaCtfAdapter (V1) | `0x157Ce2d672854c848c9b79C49a8Cc6cc89176a49` |
| NegRiskUmaCtfAdapter | `None` — see #20 |
| OptimisticOracleV2 (V1) | `0xeE3Afe347D5C74317041E2618C49534dAf887c24` |

**Adapter vs OO split.** Adapters only store per-question metadata and, on `resolve(questionID)`, pull the settled price from OOv2 and call `ctf.reportPayouts`. All proposer / disputer / settler traffic goes to **OOv2 directly** with the adapter passed as the `requester`. USDC.e approvals therefore target **OOv2, not the adapter** — `propose_price` / `dispute_price` call `_ensure_allowance(OPTIMISTIC_ORACLE_V2, ...)`.

**Public methods.** `get_uma_question`, `get_oo_request`, `get_uma_state` (enum decoded to `"Requested"/"Proposed"/..."Settled"`), `ready_to_resolve`, `propose_price`, `dispute_price`, `settle_oo`, `resolve_market`. Write methods support `estimate=True` → `GasEstimate` and `wait=True/False`.

**EOA-by-default for bots.** Unlike CTF merge/split/redeem, UMA write methods send from the **EOA** (derived from `private_key`) even when a proxy wallet is configured. Dispute bots typically run from a hot EOA with MATIC + USDC.e; GSN-relayed proxy submission is opt-in via `as_proxy=True`. See `_send_uma_tx` in `_uma.py`.

**Gotchas encoded in the mixin:**
- `requestTimestamp` rotates after each dispute-reset → every write re-reads `getQuestion` rather than caching.
- Proposer pulls `reward + proposalBond`; disputer pulls only `proposalBond`.
- `ancillaryData` is read from the adapter (includes appended `,initializer:<creator>`); never reconstructed.
- Valid proposed prices only: `0`, `5e17`, `1e18`, `-(2**255)` → `ValueError` otherwise before any network call.
- State-machine preconditions: `propose_price` requires `"Requested"`; `dispute_price` requires `"Proposed"` → raises `ValueError` with current state instead of letting the EVM revert.
- After a **second** dispute, OOv2 escalates to UMA's DVM and `hasPrice` stays false for 48–72h — caller should back off, not retry.

### DataFrame preprocessing

Every method returning a list of objects runs through `preprocess_dataframe` (defined in `utils.py`, bound as `self.preprocess_dataframe`). The pipeline:

1. Rename snake_case columns → camelCase (`snake_columns_to_camel`)
2. Drop `icon` / `image` columns (configurable via `drop_columns`)
3. Coerce by column name: numeric, ISO-datetime string, Unix-ms-datetime, bool, JSON-string

The column name lists (`numeric_columns`, `str_datetime_columns`, etc.) are tuples on the dataclass. `__post_init__` expands them via `expand_column_lists` (from `utils.py`) to also include prefixed variants (`eventsEndDate`, `marketsActive`, etc.) that appear after `expand_dataframe` normalizes nested fields.

`PolymarketWebSocket` shares the same column config and expands lists the same way.

### Nested expansion (`expand_dataframe`)

`get_markets` and `get_events` accept flags like `expand_events`, `expand_series`, `expand_clob_token_ids`. These call `utils.expand_dataframe`, which uses `pd.json_normalize(record_path=..., meta=..., record_prefix=...)` to inline nested list fields as prefixed columns (e.g. `events_` prefix → `eventsEndDate` after camelCase). This is why `expand_column_lists` generates prefixed column name variants — so preprocessing still applies to expanded columns.

### Pagination

Two patterns:

- **Offset-based** — `_autopage(fetcher, ...)`: used by `get_tags_all`, `get_events_all`, `get_markets_all`, `get_series_all`, `get_teams_all`, `get_comments_all`, `get_comments_by_user_address_all`, `get_positions_all`, `get_closed_positions_all`, `get_market_positions_all`, `get_trades_all`, `get_user_activity_all`, `get_leaderboard_all`, `get_builder_leaderboard_all`. Reads default `limit` from the fetcher's signature via `inspect.signature`, increments `offset` by pre-expansion record count (`page.attrs["_raw_count"]`), stops on a short page. All `_all` methods have explicit parameter signatures matching their base methods.
- **Cursor-based** — `_autopage_cursor(fetcher, ...)`: used by `get_sampling_markets_all`, `get_simplified_markets_all`, `get_sampling_simplified_markets_all`, `get_user_trades_all`, `get_active_orders_all`, and rewards `_all` methods. Stops when `next_cursor == "LTE="` (sentinel) or falsy.
- **Keyset (Gamma)** — `get_markets_keyset` / `get_markets_keyset_all` and `get_events_keyset` / `get_events_keyset_all`: Gamma's `/markets/keyset` and `/events/keyset` endpoints use `after_cursor` (not `offset`) and omit `next_cursor` on the final page. Markets keyset returns `MarketsKeysetPage`; events keyset returns `EventsKeysetPage` (both `{"data": DataFrame[Schema], "next_cursor": str | None}`). The `_all` variants run their own loop rather than using `_autopage_cursor` because the cursor kwarg name (`after_cursor`) and termination signal (absence of key, not `"LTE="` sentinel) both differ.

Cursor-paginated single-page methods (`get_sampling_markets`, `get_simplified_markets`, `get_sampling_simplified_markets`, `get_builder_trades`, `get_user_trades`, `get_active_orders`, and all rewards cursor methods) return `CursorPage` TypedDict: `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}` instead of a bare DataFrame.

### `AsyncPolymarketPandas` — Async HTTP client (`async_client.py`)

Wraps the sync `PolymarketPandas` via composition. Creates an internal sync instance and runs each method in a `ThreadPoolExecutor` (default 10 workers). All 102 public methods are auto-generated as `async def` wrappers at class creation time via `_populate_async_methods()`, which iterates `dir(PolymarketPandas)` and creates wrappers using `loop.run_in_executor()`.

**Why composition, not inheritance:** The mixins call `self._request_*()` synchronously. Making them truly async would require rewriting all 77+ mixin methods. The executor pattern gives non-blocking behavior with zero sync code changes.

**Note:** `_populate_async_methods` uses `callable()` not `inspect.isfunction` — the latter misses `cachetools.cachedmethod` descriptors (e.g. `get_tick_size`).

### `PolymarketWebSocket` (sync) and `AsyncPolymarketWebSocket` (async)

**Sync** (`ws.py`): `@dataclass` using `websocket-client`. `from_client(client)` shares column config. Each channel method returns a `PolymarketWebSocketSession` wrapping `WebSocketApp`. A daemon ping thread keeps the connection alive.

**Async** (`async_ws.py`): `@dataclass` using `websockets` library (native async). Channel methods return `AsyncPolymarketWebSocketSession` supporting:
- `async for event_type, payload in session:` iteration
- `async with session:` context manager
- Auto-reconnection with exponential backoff
- Async `subscribe()`/`unsubscribe()` on live connections
- `asyncio.Task`-based ping (not threading)

Both share the same message parsing logic (DataFrame construction, `_preprocess`) and column config via `from_client()`.

### `instance_cache` (`utils.py`)

Decorator for per-instance method caching, backed by `cachetools.cachedmethod`. Stores a `Cache` or `TTLCache` on the instance as `_cache_{method_name}`.

```python
@instance_cache(ttl=300)   # TTLCache, re-fetched every 5 min
def get_tick_size(self, token_id): ...

@instance_cache            # permanent Cache
def get_neg_risk(self, token_id): ...
```

Used by `get_tick_size`, `get_neg_risk`, `get_fee_rate` in `_clob_public.py`. These are auto-fetched by `build_order()` when market params aren't provided.

### `preprocess_dict` (`utils.py`)

Same type coercion as `preprocess_dataframe` but for single dict responses: snake→camel key rename, numeric/datetime/bool/JSON-string parsing, drop icon/image. Applied to `get_market_by_id()` and `get_market_by_slug()` via `self.preprocess_dict()` on the client.

### Auto-set credentials

`derive_api_key()` and `create_api_key()` in `_clob_private.py` auto-set `_api_key`, `_api_secret`, `_api_passphrase` on the client via `_apply_api_creds()`. No manual credential wiring needed after key derivation.

### `amount_usdc` convenience parameter

`split_position()` and `merge_positions()` accept `amount_usdc: float` as an alternative to `amount: int`. Converts via `int(amount_usdc * 1_000_000)`. Mutually exclusive — raises `ValueError` if both provided.

### `filter_params` (`utils.py`)

All `_request_*` helpers pass `params` through `filter_params` before sending. It removes `None` values and empty lists, and converts `pd.Timestamp` values to ISO-8601 strings for date-range parameters.

### Order input schemas (`order_schema.py`)

Two `pandera.DataFrameModel` schemas for **runtime input validation** (validated automatically, not annotation-only):

- **`PlaceOrderSchema`** (V2) — validates signed-order DataFrames for `place_orders()`. Enforces Ethereum address format, numeric string patterns for amounts/timestamp, 32-byte hex for `metadata`/`builder`, `side` ∈ `["BUY","SELL"]`, `signatureType` ∈ `[0,1,2]`, `orderType` ∈ `["FOK","GTC","GTD"]`. Optional `postOnly` bool. V1 fields `nonce`/`feeRateBps`/`taker`/`expiration` are no longer accepted.
- **`SubmitOrderSchema`** — validates unsigned-intent DataFrames for `submit_orders()`. Required camelCase columns: `tokenId`, `price` (0,1], `size` (>0), `side`. Optional: `orderType`, `postOnly`, `negRisk`, `tickSize`, `builderCode`.
- **`OrderSchema`** — backward-compat alias for `PlaceOrderSchema`.

`place_orders()` also enforces the CLOB API's 15-order-per-call limit.

### Post-only orders

`place_order`, `place_orders`, `submit_order`, and `submit_orders` support post-only mode. `postOnly` is a **JSON envelope field** (not part of the signed EIP-712 struct) that tells the matching engine to reject the order if it would immediately fill.

- `place_order(..., post_only=True)` / `submit_order(..., post_only=True)` — function arg (snake_case)
- `place_orders` / `submit_orders` — read `postOnly` column from DataFrame (camelCase)
- Only valid with `GTC` / `GTD` order types; raises `ValueError` otherwise.

### Typed returns (`types.py` and `schemas.py`)

**TypedDicts** (`types.py`): Structural subtypes of `dict` for dict-returning endpoints. No runtime overhead, full IDE autocomplete.

- **Cursor-paginated** (all inherit from `CursorPage` base with `next_cursor`, `count`, `limit`): `OrdersCursorPage`, `UserTradesCursorPage`, `SamplingMarketsCursorPage`, `SimplifiedMarketsCursorPage`, `BuilderTradesCursorPage`, `CurrentRewardsCursorPage`, `RewardsMarketMultiCursorPage`, `RewardsMarketCursorPage`, `UserEarningsCursorPage`, `UserRewardsMarketsCursorPage`. Each has `data: DataFrame[SpecificSchema]`.
- **Other dicts**: `SignedOrder`, `SendOrderResponse`, `CancelOrdersResponse`, `TransactionReceipt`, `ApiCredentials`, `BalanceAllowance`, `BridgeAddress`, `BridgeAddressInfo`, `RelayPayload`, `SubmitTransactionResponse`, `LastTradePrice`, `MarketsKeysetPage`, `EventsKeysetPage`, `ClobMarketInfo` (V2).

**Pandera schemas** (`schemas.py`): `DataFrameModel` subclasses (via `pandera.pandas`) for DataFrame-returning endpoints. All use `strict=False` (extra columns allowed) and `coerce=True`. Annotation-only by default (no runtime validation unless user calls `.validate()`). Field names verified against the official Polymarket OpenAPI specs.

**Rule: every public method that returns a `pd.DataFrame` MUST have a pandera schema in `schemas.py` and use `DataFrame[Schema]` as its return type annotation. Integration tests validate live API data against these schemas.**

- **Gamma API**: `MarketSchema`, `EventSchema`, `TagSchema`, `SeriesSchema`, `CommentSchema`, `SportsMetadataSchema`, `TeamSchema`
- **CLOB API**: `OrderbookSchema`, `ClobTradeSchema`, `ActiveOrderSchema`, `PriceHistorySchema`, `MidpointSchema`, `MarketPriceSchema`, `LastTradePricesSchema`, `SendOrderResponseSchema`, `SamplingMarketSchema`, `SimplifiedMarketSchema`, `BuilderTradeSchema`
- **Data API**: `PositionSchema`, `ClosedPositionSchema`, `DataTradeSchema`, `ActivitySchema`, `LeaderboardSchema`, `BuilderLeaderboardSchema`, `BuilderVolumeSchema`, `PositionValueSchema`
- **Rewards API**: `CurrentRewardSchema`, `RewardsMarketMultiSchema`, `RewardsMarketSchema`, `UserEarningSchema`, `UserRewardsMarketSchema`, `RebateSchema`
- **Bridge API**: `BridgeSupportedAssetSchema`, `BridgeTransactionSchema`

### `to_unix_timestamp` (`utils.py`)

Converts `int`, `float`, `str` (ISO-8601), `pd.Timestamp`, or `datetime.datetime` to Unix seconds (int). Used by date-range query parameters. Naive timestamps are assumed UTC. (Previously also used by `build_order` for the V1 `expiration` field, which was removed in V2.)

## Explorer (Streamlit Dashboard)

Interactive dashboard for exploring all public endpoints. Installed as an optional extra:

```bash
uv pip install -e ".[explorer]"

# Run via CLI entry point
polymarket-explore

# Or directly
streamlit run explorer/home.py
```

```
explorer/
  app.py              # CLI entry point (runs streamlit)
  home.py             # Home page, sidebar config, shared client
  pages/
    01_markets.py     # get_markets — filters, volume chart
    02_events.py      # get_events — expand markets, volume chart
    03_series.py      # get_series — expand events, hierarchy chart
    04_orderbook.py   # get_orderbook — depth chart (bids/asks)
    05_prices.py      # get_price_history, midpoint, spread, last trade
    06_positions.py   # get_positions / get_closed_positions — portfolio pie
    07_trades.py      # get_trades — price scatter plot
    08_leaderboard.py # get_leaderboard / get_builder_leaderboard
    09_rewards.py     # reward configs, markets with rewards
    10_bridge.py      # supported assets, transaction status
```

Each page shows: raw DataFrame, Plotly visualization, and collapsible Python code snippet.

## Tests

- `tests/test_unit.py` — 108 sync unit tests, all HTTP mocked via `pytest-httpx` or `unittest.mock`. No live API calls.
- `tests/test_async_unit.py` — 16 async tests using `pytest-asyncio`.
- `tests/test_integration.py` — 13 integration tests (live API, optional).
- `tests/conftest.py` — `client` (unauthenticated), `authed_client` (stub L2 credentials), and `ctf_client` (stub private key) fixtures.

Test categories:
- Utility functions (snake_to_camel, filter_params, expand_column_lists, to_unix_timestamp)
- HTTP endpoint responses (mocked via pytest-httpx)
- WebSocket channels (market, user, sports, RTDS)
- CTF operations (auth guards, web3 import guard, contract routing, tx wait/no-wait, amount_usdc)
- Order building (buy/sell amounts, neg-risk signing, validation, DataFrame submit_orders, datetime expiry)
- Typed returns (schema validation smoke tests, TypedDict imports, CursorPage returns)
- Async client (methods exist, HTTP calls work, auth errors, properties)
- Async WebSocket (from_client, channel creation, credential validation)
