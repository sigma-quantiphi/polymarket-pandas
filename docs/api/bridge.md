# Bridge

Bridge API endpoints (`bridge.polymarket.com`) for cross-chain deposits, withdrawals, and asset bridging. No authentication required for read endpoints.

---

## Endpoints

### `get_bridge_supported_assets() -> list[dict]`

Get all supported assets and chains for bridging.

```python
assets = client.get_bridge_supported_assets()
# Each item: {chainId, chainName, token: {name, symbol, address, decimals}, minCheckoutUsd}
```

### `get_bridge_quote(...) -> dict`

Get a price estimate before bridging.

```python
quote = client.get_bridge_quote(
    from_amount_base_unit="1000000",        # 1 USDC (6 decimals)
    from_chain_id="1",                      # Ethereum
    from_token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    recipient_address="0xYourPolymarketWallet",
    to_chain_id="137",                      # Polygon
    to_token_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
)
# quote keys: quoteId, estCheckoutTimeMs, estInputUsd, estOutputUsd,
#             estToTokenBaseUnit, estFeeBreakdown (appFeeUsd, gasUsd, ...)
```

### `create_deposit_address(address) -> BridgeAddress`

Create multi-chain deposit addresses. Send funds to the returned address to have USDC.e credited to your Polymarket wallet.

```python
result = client.create_deposit_address("0xYourPolymarketWallet")
# result: {"address": {"evm": "0x...", "svm": "...", "btc": "bc1q..."}, "note": "..."}
```

### `create_withdrawal_address(address, to_chain_id, to_token_address, recipient_addr) -> BridgeAddress`

Bridge funds out of Polymarket to another chain.

```python
result = client.create_withdrawal_address(
    address="0xYourPolymarketWallet",
    to_chain_id="1",                    # Ethereum mainnet
    to_token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    recipient_addr="0xRecipientOnEthereum",
)
```

### `get_bridge_transaction_status(address) -> pd.DataFrame`

Poll for transaction status using an address returned by deposit/withdraw.

```python
status = client.get_bridge_transaction_status("0xDepositAddress...")
# columns: fromChainId, fromTokenAddress, fromAmountBaseUnit,
#          toChainId, toTokenAddress, status, txHash, createdTimeMs
```

Status values: `DEPOSIT_DETECTED`, `PROCESSING`, `ORIGIN_TX_CONFIRMED`, `SUBMITTED`, `COMPLETED`, `FAILED`.
