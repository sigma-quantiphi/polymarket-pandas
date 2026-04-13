# CTF (On-Chain Operations)

On-chain merge, split, and redeem via Polymarket's Conditional Token Framework contracts on Polygon.

**Requirements:**

- Install with the `[ctf]` extra: `pip install "polymarket-pandas[ctf]"`
- `private_key` must be set (for signing transactions)
- Amounts are in USDC.e base units (6 decimals): `1_000_000` = 1.00 USDC
- For **proxy wallet** users (most Polymarket accounts): builder API credentials are required (`POLYMARKET_BUILDER_API_KEY`, `POLYMARKET_BUILDER_API_SECRET`, `POLYMARKET_BUILDER_API_PASSPHRASE`)

**Contract addresses (Polygon mainnet):**

| Contract | Address |
|---|---|
| ConditionalTokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| NegRiskAdapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| USDC.e (collateral) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

---

## Proxy Wallet vs EOA

Most Polymarket users have a **proxy wallet** (a Gnosis Safe or custom proxy) that holds their tokens. The client auto-detects this: when `address` differs from the EOA derived from `private_key`, CTF operations route through Polymarket's GSN relayer instead of sending direct on-chain transactions.

- **Direct (EOA)**: The EOA holds tokens and pays gas in MATIC.
- **Relayed (proxy)**: Tokens live in the proxy wallet. The relayer submits the transaction through the proxy's GSN relay hub (gasless for the user). Requires builder API credentials for HMAC authentication.

---

## Endpoints

### `estimate_ctf_tx(tx_data) -> GasEstimate`

Estimate gas cost for a CTF transaction without sending it. Also available via `estimate=True` on all CTF methods.

```python
est = client.merge_positions(
    condition_id="0x4aee6d11...",
    amount_usdc=10.0,
    estimate=True,
)
print(f"Gas: {est['gas']:,} units @ {est['gasPrice'] / 1e9:.1f} gwei")
print(f"Cost: {est['costMatic']:.6f} MATIC")
print(f"EOA balance: {est['eoaBalance'] / 1e18:.6f} MATIC")
```

Returns a `GasEstimate` TypedDict:

| Field | Type | Description |
|---|---|---|
| `gas` | int | Estimated gas units |
| `gasPrice` | int | Current gas price (wei) |
| `costWei` | int | `gas × gasPrice` |
| `costMatic` | float | Cost in MATIC |
| `eoaBalance` | int | EOA's MATIC balance (wei) |

### `split_position(condition_id, amount, ...) -> TransactionReceipt`

Split USDC.e collateral into Yes + No outcome tokens.

```python
result = client.split_position(
    condition_id="0x4aee6d11...",
    amount_usdc=1.0,          # or amount=1_000_000 (base units)
    neg_risk=False,
    auto_approve=True,        # approve USDC.e spending if needed
)
```

### `merge_positions(condition_id, amount, ...) -> TransactionReceipt`

Merge equal amounts of Yes + No tokens back into USDC.e.

```python
# Estimate first
est = client.merge_positions(
    condition_id="0x4aee6d11...",
    amount_usdc=10.0,
    estimate=True,
)

# Then merge
result = client.merge_positions(
    condition_id="0x4aee6d11...",
    amount_usdc=10.0,
    auto_approve=True,
)
```

### `redeem_positions(condition_id, index_sets=None, ...) -> TransactionReceipt`

Redeem winning outcome tokens for USDC.e after market resolution.

```python
result = client.redeem_positions(condition_id="0x4aee6d11...")
```

### `approve_collateral(spender=None, amount=None, ...) -> TransactionReceipt`

Approve a CTF contract to spend USDC.e. Called automatically when `auto_approve=True` is passed to `split_position` or `merge_positions`.

```python
# Manual approval (if not using auto_approve)
client.approve_collateral()  # defaults to ConditionalTokens, unlimited
```

---

## Common Parameters

All four CTF methods (`split_position`, `merge_positions`, `redeem_positions`, `approve_collateral`) accept:

| Parameter | Default | Description |
|---|---|---|
| `estimate` | `False` | Return `GasEstimate` instead of sending |
| `wait` | `True` | Block until mined (returns `status`, `blockNumber`, `gasUsed`) |
| `timeout` | `120` | Seconds to wait for receipt |

`split_position` and `merge_positions` additionally accept:

| Parameter | Default | Description |
|---|---|---|
| `amount` | — | Token amount in base units (6 decimals) |
| `amount_usdc` | — | Convenience float (e.g. `1.0` = 1 USDC). Mutually exclusive with `amount` |
| `neg_risk` | `False` | `True` for neg-risk markets (uses NegRiskAdapter) |
| `auto_approve` | `False` | Check on-chain allowance and approve if needed before the operation |

---

## Notes

- **Proxy wallet detection** is automatic. When `address` (proxy) differs from the EOA, all CTF operations route through the GSN relayer.
- **Gas estimation** for proxy wallets uses `state_override` to simulate from the proxy (which may have 0 MATIC).
- `web3` is lazily imported — users who never call CTF methods do not need `web3` installed.
- `neg_risk=True` routes split/merge through NegRiskAdapter (2-param ABI); `False` uses ConditionalTokens (5-param ABI).
- See `examples/merge_positions.py` for a complete working example with dry-run and gas estimation.
