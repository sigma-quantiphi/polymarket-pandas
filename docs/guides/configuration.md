# Configuration

All credentials are read from environment variables (or a `.env` file via `python-dotenv`).
You can also pass them directly as constructor arguments.

## Environment Variables

| Env var | Constructor kwarg | Purpose |
|---|---|---|
| `POLYMARKET_ADDRESS` | `address` | Your proxy wallet address |
| `POLYMARKET_PRIVATE_KEY` | `private_key` | Private key for EIP-712 (L1) signing |
| `POLYMARKET_FUNDER` | `private_funder_key` | Funder private key |
| `POLYMARKET_API_KEY` | `_api_key` | CLOB API key |
| `POLYMARKET_API_SECRET` | `_api_secret` | CLOB API secret (used for L2 HMAC) |
| `POLYMARKET_API_PASSPHRASE` | `_api_passphrase` | CLOB API passphrase |
| `POLYMARKET_BUILDER_API_KEY` | `_builder_api_key` | Builder API key |
| `POLYMARKET_BUILDER_API_SECRET` | `_builder_api_secret` | Builder API secret |
| `POLYMARKET_BUILDER_API_PASSPHRASE` | `_builder_api_passphrase` | Builder API passphrase |
| `POLYMARKET_RELAYER_API_KEY` | `_relayer_api_key` | Relayer API key |
| `POLYMARKET_RELAYER_API_KEY_ADDRESS` | `_relayer_api_key_address` | Address owning the relayer key |
| `POLYMARKET_RPC_URL` | `rpc_url` | Polygon RPC URL (default: `https://polygon-rpc.com`) |
| `HTTP_PROXY` | `proxy_url` | HTTP proxy URL |

## Explicit Credentials

```python
from polymarket_pandas import PolymarketPandas

client = PolymarketPandas(
    address="0xYourAddress",
    private_key="0xYourKey",
    _api_key="your-api-key",
    _api_secret="your-secret",
    _api_passphrase="your-passphrase",
)
```

!!! tip
    If `private_key` is set but `address` is not, the address is automatically derived from the key.

## API Key Setup

CLOB API credentials can be derived from your wallet's private key. Once derived, they are
automatically set on the client instance -- no manual wiring needed.

```python
# Step 1 -- derive or create CLOB API credentials from your wallet key
creds = client.derive_api_key()   # uses private_key from env
# creds = client.create_api_key()  # creates a new key

# Step 2 -- credentials are auto-set, but you can also set them manually
client._api_key = creds["apiKey"]
client._api_secret = creds["secret"]
client._api_passphrase = creds["passphrase"]
```

!!! note
    `derive_api_key()` is deterministic -- calling it multiple times with the same private key
    returns the same credentials. `create_api_key()` generates a new key pair each time.

## Authentication Layers

Polymarket uses five authentication layers depending on the endpoint:

### None (Public)

No credentials required. Used by all Gamma discovery endpoints (`get_markets`, `get_events`,
`get_tags`, etc.), public CLOB endpoints (`get_orderbook`, `get_price_history`, etc.),
Data API endpoints (`get_positions`, `get_trades`, etc.), Bridge API, and XTracker API.

```python
client = PolymarketPandas()  # no credentials needed
markets = client.get_markets(closed=False)
```

### L2 HMAC-SHA256 (Private CLOB)

Used by all private CLOB endpoints: `get_user_trades`, `get_active_orders`, `place_order`,
`cancel_order`, `send_heartbeat`, etc. Requires `_api_key`, `_api_secret`, and `_api_passphrase`.

The client calls `_require_l2_auth()` before every private request. If credentials are missing,
a `PolymarketAuthError` is raised immediately -- before any network call.

### L1 EIP-712 (Key Creation)

Used only by `create_api_key()` and `derive_api_key()`. Requires `private_key` for
EIP-712 domain-separated signing. This is the only layer that touches the raw private key.

### Builder HMAC

Same HMAC-SHA256 scheme as L2, but with `POLY_BUILDER_*` headers and separate builder credentials.
Used by `get_builder_trades`. Also auto-attached alongside L2 auth on `place_order` / `place_orders`
(and `submit_order` / `submit_orders`) when builder credentials are configured, so matched fills
are credited to the builder for rewards.

### Relayer Key

Plain headers (`RELAYER_API_KEY` + `RELAYER_API_KEY_ADDRESS`) with no signing.
Used by `get_relayer_transactions`, `get_relayer_api_keys`, and `submit_transaction`.

## Full Environment Variables Reference

```dotenv
# Wallet / signing
POLYMARKET_ADDRESS=0xYourProxyWallet
POLYMARKET_PRIVATE_KEY=0xYourPrivateKey
POLYMARKET_FUNDER=0xFunderKey

# CLOB API (L2)
POLYMARKET_API_KEY=your-clob-api-key
POLYMARKET_API_SECRET=your-clob-api-secret
POLYMARKET_API_PASSPHRASE=your-clob-passphrase

# Builder API
POLYMARKET_BUILDER_API_KEY=your-builder-key
POLYMARKET_BUILDER_API_SECRET=your-builder-secret
POLYMARKET_BUILDER_API_PASSPHRASE=your-builder-passphrase

# Relayer API
POLYMARKET_RELAYER_API_KEY=your-relayer-key
POLYMARKET_RELAYER_API_KEY_ADDRESS=0xAddressThatOwnsRelayerKey

# Network
POLYMARKET_RPC_URL=https://polygon-bor-rpc.publicnode.com  # Polygon RPC for CTF ops
HTTP_PROXY=http://proxy:8080                                # HTTP proxy (optional)
```
