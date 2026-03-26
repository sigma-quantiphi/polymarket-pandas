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
  __init__.py          # Public exports (6 classes + 4 exceptions)
  client.py            # PolymarketPandas dataclass — core infra + build_order
  async_client.py      # AsyncPolymarketPandas — async wrapper via composition + ThreadPoolExecutor
  exceptions.py        # PolymarketError hierarchy
  utils.py             # Stateless helpers: preprocess_dataframe, preprocess_dict, filter_params,
  #                      instance_cache, etc.
  ws.py                # PolymarketWebSocket + PolymarketWebSocketSession (sync, websocket-client)
  async_ws.py          # AsyncPolymarketWebSocket + AsyncPolymarketWebSocketSession (async, websockets)
  order_schema.py      # pandera DataFrameModel for validating place_orders input
  py.typed             # PEP 561 marker
  mixins/
    __init__.py        # Re-exports all 7 mixin classes
    _gamma.py          # GammaMixin   — markets, events, tags, series, sports, comments, search, profiles
    _data.py           # DataMixin    — positions, trades, leaderboard, accounting snapshot, builders
    _clob_public.py    # ClobPublicMixin — orderbook, prices, midpoints, spreads, price history,
    #                                      sampling/simplified markets, builder trades, rebates
    _clob_private.py   # ClobPrivateMixin — user trades, orders (get/place/cancel), heartbeat, API keys
    _relayer.py        # RelayerMixin — Safe deployment, nonces, transactions, relay payload, submit
    _bridge.py         # BridgeMixin  — deposit/withdrawal addresses, quotes, supported assets, status
    _ctf.py            # CTFMixin     — on-chain merge, split, redeem positions (requires web3)
```

## Architecture

### `PolymarketPandas` — HTTP client

A `@dataclass` that inherits from all 7 mixins. `client.py` contains infrastructure, order building, and pagination; all endpoint methods live in the mixins. The class has six base URLs:

| Field | Base URL | Auth |
|---|---|---|
| `data_url` | `https://data-api.polymarket.com/` | none |
| `gamma_url` | `https://gamma-api.polymarket.com/` | none |
| `clob_url` | `https://clob.polymarket.com/` | none / L2 / builder |
| `relayer_url` | `https://relayer-v2.polymarket.com/` | relayer key |
| `bridge_url` | `https://bridge.polymarket.com/` | none |
| `rpc_url` | `https://polygon-rpc.com` (configurable) | none (used by CTFMixin) |

**Request helpers** (all call `_handle_response` which maps HTTP errors to custom exceptions):
- `_request_data`, `_request_gamma`, `_request_clob` — unauthenticated
- `_request_clob_private` — L2 HMAC auth, calls `_require_l2_auth()` guard first
- `_request_clob_builder` — builder HMAC auth, calls `_require_builder_auth()` guard first
- `_request_relayer` — accepts optional `auth_headers` dict (relayer API key)
- `_request_bridge` — unauthenticated

**Authentication layers:**
- **L1 (EIP-712)** — `_build_l1_headers`: used only for `create_api_key` / `derive_api_key`. Requires `private_key`.
- **L2 (HMAC-SHA256)** — `_build_l2_headers`: all private CLOB endpoints. Requires `_api_key` / `_api_secret` / `_api_passphrase`.
- **Builder HMAC** — `_build_builder_headers`: same scheme as L2 but with `POLY_BUILDER_*` headers and builder credentials.
- **Relayer key** — plain headers `RELAYER_API_KEY` + `RELAYER_API_KEY_ADDRESS` (no signing). Built by `_relayer_auth_headers()`.

All credentials fall back to env vars (`POLYMARKET_ADDRESS`, `POLYMARKET_PRIVATE_KEY`, `POLYMARKET_API_KEY`, etc.).

### Exceptions (`exceptions.py`)

```
PolymarketError
└── PolymarketAPIError(status_code, url, detail)
    ├── PolymarketAuthError     — 401/403 or missing credentials
    └── PolymarketRateLimitError — 429
```

All four are exported from the top-level package. `_handle_response` maps HTTP errors to the hierarchy. `_require_l2_auth` / `_require_builder_auth` raise `PolymarketAuthError` before any network call if credentials are missing.

`_extract(data, key)` raises `PolymarketAPIError` with context when an expected key is missing from a response dict — used by scalar-returning endpoints like `get_tick_size`, `get_midpoint_price`, etc.

### Order building (`build_order`)

`build_order(token_id, price, size, side, ...)` in `client.py` constructs and EIP-712-signs a CLOB order. Returns a dict ready for `place_order()`.

**Signing details:**
- **Domain**: `name="Polymarket CTF Exchange"`, `version="1"`, `chainId=137`, `verifyingContract=<exchange>`
- **Exchange contracts** (Polygon mainnet):
  - Standard: `CTF_EXCHANGE = 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`
  - Neg-risk: `NEG_RISK_CTF_EXCHANGE = 0xC5d563A36AE78145C45a50134d48A1215220f80a`
- **Amount calculation**: `makerAmount` / `takerAmount` depend on `side`:
  - BUY: makerAmount = USDC spent = `size * price * 1e6`, takerAmount = shares received = `size * 1e6`
  - SELL: makerAmount = shares sold = `size * 1e6`, takerAmount = USDC received = `size * price * 1e6`
- **Tick-size rounding**: price/size decimals derived from tick_size (0.1→1dp, 0.01→2dp, 0.001→3dp, 0.0001→4dp)
- **Signature types**: 0=EOA, 1=POLY_PROXY (default), 2=POLY_GNOSIS_SAFE

### CTFMixin — On-chain operations (`_ctf.py`)

On-chain merge / split / redeem via Polymarket's Conditional Token Framework contracts on Polygon. Requires `web3` optional dependency: `pip install polymarket-pandas[ctf]`.

**Contract addresses (Polygon mainnet):**

| Contract | Address |
|---|---|
| ConditionalTokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| NegRiskAdapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| USDC.e (collateral) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

**Methods:**

| Method | Description |
|---|---|
| `split_position(condition_id, amount=None, amount_usdc=None, neg_risk=False)` | Split USDC.e into Yes + No outcome tokens |
| `merge_positions(condition_id, amount=None, amount_usdc=None, neg_risk=False)` | Merge Yes + No tokens back into USDC.e |
| `redeem_positions(condition_id, index_sets=None)` | Redeem winning tokens after market resolution |
| `approve_collateral(spender=None, amount=None)` | Approve USDC.e spending for a CTF contract |

**Key design:**
- `web3` is lazily imported — `_require_web3()` initializes `_w3`, `_ct_contract`, `_nr_contract`, `_usdc_contract` on first call. Users who never call CTF methods never need web3 installed.
- Auth guard: `_require_ctf_auth()` checks `private_key` before `_require_web3()` in every public method.
- `neg_risk=True` routes split/merge through NegRiskAdapter (2-param ABI); `False` uses ConditionalTokens (5-param ABI with collateral, parentCollectionId=bytes32(0), partition=[1,2]).
- Amounts are in USDC.e base units (6 decimals): `1_000_000` = 1.00 USDC.
- Returns dict with `txHash`, `status`, `blockNumber`, `gasUsed` (when `wait=True`).

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

- **Offset-based** — `_autopage(fetcher, ...)`: used by `get_tags_all`, `get_events_all`, `get_markets_all`. Reads default `limit` from the fetcher's signature via `inspect.signature`, increments `offset` by returned row count, stops on a short page.
- **Cursor-based** — `_autopage_cursor(fetcher, ...)`: used by `get_sampling_markets_all`, `get_simplified_markets_all`, `get_sampling_simplified_markets_all`. Stops when `next_cursor == "LTE="` (sentinel) or falsy.

Cursor-paginated single-page methods (`get_sampling_markets`, `get_simplified_markets`, `get_sampling_simplified_markets`, `get_builder_trades`) return `{"data": DataFrame, "next_cursor": str, "count": int, "limit": int}` instead of a bare DataFrame.

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

### `OrderSchema` (`order_schema.py`)

A `pandera.DataFrameModel` for validating order DataFrames before passing them to `place_orders`. Fields match the CLOB signed-order struct. Side validation: uppercase `"BUY"` / `"SELL"`.

## Tests

- `tests/test_unit.py` — 75 sync unit tests, all HTTP mocked via `pytest-httpx` or `unittest.mock`. No live API calls.
- `tests/test_async_unit.py` — 16 async tests using `pytest-asyncio`.
- `tests/test_integration.py` — 13 integration tests (live API, optional).
- `tests/conftest.py` — `client` (unauthenticated), `authed_client` (stub L2 credentials), and `ctf_client` (stub private key) fixtures.

Test categories:
- Utility functions (snake_to_camel, filter_params, expand_column_lists)
- HTTP endpoint responses (mocked via pytest-httpx)
- WebSocket channels (market, user, sports, RTDS)
- CTF operations (auth guards, web3 import guard, contract routing, tx wait/no-wait, amount_usdc)
- Order building (buy/sell amounts, neg-risk signing, validation, DataFrame submit_orders)
- Async client (methods exist, HTTP calls work, auth errors, properties)
- Async WebSocket (from_client, channel creation, credential validation)
