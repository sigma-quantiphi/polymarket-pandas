# Relayer

Relayer API endpoints (`relayer-v2.polymarket.com`) for Safe wallet deployment, nonce management, and transaction relay.

---

## Endpoints

### `check_safe_deployed(address) -> bool`

Check whether a Gnosis Safe proxy has been deployed for an address.

```python
deployed = client.check_safe_deployed("0xProxyAddress")
```

### `get_relayer_transaction(id) -> list[dict]`

Fetch a relayer transaction by its UUID.

```python
txs = client.get_relayer_transaction("0190b317-a1d3-7bec-9b91-eeb6dcd3a620")
```

Each transaction has: `transactionID`, `transactionHash`, `from`, `to`, `proxyAddress`, `data`, `nonce`, `value`, `signature`, `state`, `type`, `owner`, `metadata`, `createdAt`, `updatedAt`.

State values: `STATE_NEW`, `STATE_EXECUTED`, `STATE_MINED`, `STATE_CONFIRMED`, `STATE_INVALID`, `STATE_FAILED`.

Type values: `SAFE`, `PROXY`.

### `get_relayer_nonce(address, type) -> str`

Get the current nonce for an address.

```python
nonce = client.get_relayer_nonce("0xSignerAddress", type="PROXY")
```

### `get_relayer_transactions() -> pd.DataFrame`

Requires relayer credentials (`_relayer_api_key`, `_relayer_api_key_address`). Returns recent transactions for the authenticated account.

### `get_relay_payload(address, type) -> RelayPayload`

Returns `{"address": "<relayer_address>", "nonce": "<nonce>"}` -- needed to construct a transaction before signing.

```python
payload = client.get_relay_payload("0xSignerAddress", type="PROXY")
```

### `submit_transaction(...) -> SubmitTransactionResponse`

Submit a signed transaction to the relayer.

```python
result = client.submit_transaction(
    from_="0xSignerAddress",
    to="0xContractAddress",
    proxy_wallet="0xProxyWallet",
    data="0xEncodedCalldata",
    nonce="31",
    signature="0xSignatureHex",
    type="PROXY",
    signature_params={
        "gasPrice": "100000000000",
        "operation": "0",
        "safeTxnGas": "0",
        "baseGas": "0",
        "gasToken": "0x0000000000000000000000000000000000000000",
        "refundReceiver": "0x0000000000000000000000000000000000000000",
    },
)
# result: {"transactionID": str, "state": "STATE_NEW"}
# V2: transactionHash is no longer in the immediate response.
# Poll get_relayer_transaction for the on-chain hash.
tx = client.get_relayer_transaction(result["transactionID"])
print(tx[0]["transactionHash"])
```

---

## Relayer API Keys

Requires `_relayer_api_key` and `_relayer_api_key_address`.

### `get_relayer_api_keys() -> pd.DataFrame`

List relayer API keys for the authenticated account.

```python
keys = client.get_relayer_api_keys()
# columns: apiKey, address, createdAt, updatedAt
```
