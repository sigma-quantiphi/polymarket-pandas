# CTF (On-Chain Operations)

On-chain merge, split, and redeem via Polymarket's Conditional Token Framework contracts on Polygon.

**Requirements:**

- Install with the `[ctf]` extra: `pip install "polymarket-pandas[ctf]"`
- `private_key` must be set (for signing transactions)
- A funded EOA wallet with MATIC for gas
- Amounts are in USDC.e base units (6 decimals): `1_000_000` = 1.00 USDC

**Contract addresses (Polygon mainnet):**

| Contract | Address |
|---|---|
| ConditionalTokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| NegRiskAdapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |
| USDC.e (collateral) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |

---

## Endpoints

### `split_position(condition_id, amount, neg_risk=False, wait=True, timeout=120) -> TransactionReceipt`

Split USDC.e collateral into Yes + No outcome tokens.

```python
result = client.split_position(
    condition_id="0x4aee6d11...",
    amount=1_000_000,       # 1.00 USDC
    neg_risk=False,         # True for neg-risk (multi-outcome) markets
)
# result: {"txHash": "0x...", "status": 1, "blockNumber": 12345, "gasUsed": 150000}
```

The `amount_usdc` convenience parameter accepts a float (e.g. `amount_usdc=1.0`) as an alternative to `amount` in base units. Mutually exclusive with `amount`.

### `merge_positions(condition_id, amount, neg_risk=False, wait=True, timeout=120) -> TransactionReceipt`

Merge equal amounts of Yes + No tokens back into USDC.e.

```python
result = client.merge_positions(
    condition_id="0x4aee6d11...",
    amount=1_000_000,
)
```

Also accepts `amount_usdc` as an alternative to `amount`.

### `redeem_positions(condition_id, index_sets=None, wait=True, timeout=120) -> TransactionReceipt`

Redeem winning outcome tokens for USDC.e after market resolution.

```python
result = client.redeem_positions(condition_id="0x4aee6d11...")
```

### `approve_collateral(spender=None, amount=None, wait=True, timeout=120) -> TransactionReceipt`

Approve a CTF contract to spend USDC.e. Required before `split_position` or `merge_positions`. Defaults to unlimited approval for the ConditionalTokens contract.

```python
from polymarket_pandas.mixins._ctf import CONDITIONAL_TOKENS, NEG_RISK_ADAPTER

# For standard binary markets
client.approve_collateral(spender=CONDITIONAL_TOKENS)

# For neg-risk markets
client.approve_collateral(spender=NEG_RISK_ADAPTER)
```

---

## Notes

- `neg_risk=True` routes split/merge through the NegRiskAdapter (2-param ABI); `False` uses ConditionalTokens (5-param ABI with collateral, parentCollectionId=bytes32(0), partition=[1,2]).
- `wait=True` (default) blocks until the transaction is mined and returns `txHash`, `status`, `blockNumber`, `gasUsed`. With `wait=False`, only `txHash` is returned immediately.
- `web3` is lazily imported -- users who never call CTF methods do not need `web3` installed.
