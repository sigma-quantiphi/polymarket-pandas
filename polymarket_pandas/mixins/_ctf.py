"""CTF (Conditional Token Framework) on-chain operations mixin.

Provides merge, split, and redeem for Polymarket positions via direct
smart-contract calls on Polygon.  Requires the ``web3`` optional
dependency: ``pip install polymarket-pandas[ctf]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polymarket_pandas.exceptions import PolymarketAuthError
from polymarket_pandas.types import GasEstimate, SubmitTransactionResponse, TransactionReceipt

if TYPE_CHECKING:
    import pandas as pd

# ── Contract addresses (Polygon mainnet) ─────────────────────────────

PROXY_FACTORY = "0xaB45c5A4B0c941a2F231C04C3f49182e1A254052"
RELAY_HUB = "0xD216153c06E857cD7f72665E0aF1d7D82172F494"

USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

PARENT_COLLECTION_ID = b"\x00" * 32
DEFAULT_PARTITION = [1, 2]
DEFAULT_RPC_URL = "https://polygon-rpc.com"

# ── Minimal ABIs ─────────────────────────────────────────────────────

_ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

_CONDITIONAL_TOKENS_ABI = [
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "partition", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "splitPosition",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "partition", "type": "uint256[]"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "mergePositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "collateralToken", "type": "address"},
            {"name": "parentCollectionId", "type": "bytes32"},
            {"name": "conditionId", "type": "bytes32"},
            {"name": "indexSets", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

_NEG_RISK_ADAPTER_ABI = [
    {
        "inputs": [
            {"name": "_conditionId", "type": "bytes32"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "splitPosition",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_conditionId", "type": "bytes32"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "mergePositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_conditionId", "type": "bytes32"},
            {"name": "_amounts", "type": "uint256[]"},
        ],
        "name": "redeemPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "_marketId", "type": "bytes32"},
            {"name": "_indexSet", "type": "uint256"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "convertPositions",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

_PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "typeCode", "type": "uint8"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "data", "type": "bytes"},
                ],
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "proxy",
        "outputs": [{"name": "returnValues", "type": "bytes[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
]


class CTFMixin:
    """On-chain merge / split / redeem via the Polymarket CTF contracts."""

    # ── Internal helpers ─────────────────────────────────────────────

    def _require_web3(self) -> None:
        """Lazily import web3 and set up contract objects."""
        if hasattr(self, "_w3"):
            return
        try:
            from web3 import Web3
        except ImportError:
            raise ImportError(
                "web3 is required for CTF operations. "
                "Install it with: pip install polymarket-pandas[ctf]"
            ) from None

        from web3.middleware import ExtraDataToPOAMiddleware

        rpc_url = getattr(self, "rpc_url", DEFAULT_RPC_URL)
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
        self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self._ct_contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(CONDITIONAL_TOKENS),
            abi=_CONDITIONAL_TOKENS_ABI,
        )
        self._nr_contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(NEG_RISK_ADAPTER),
            abi=_NEG_RISK_ADAPTER_ABI,
        )
        self._usdc_contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E),
            abi=_ERC20_ABI,
        )

    def _require_ctf_auth(self) -> None:
        if not getattr(self, "private_key", None):
            raise PolymarketAuthError(
                detail=(
                    "private_key is required for CTF operations. "
                    "Set POLYMARKET_PRIVATE_KEY or pass private_key to the constructor."
                )
            )

    @staticmethod
    def _to_bytes32(value: str | bytes) -> bytes:
        """Normalize a condition ID to 32 bytes."""
        if isinstance(value, str):
            return bytes.fromhex(value.removeprefix("0x"))
        return value

    @staticmethod
    def _resolve_amount(amount: int | None, amount_usdc: float | None) -> int:
        """Resolve amount from either base units or USDC float."""
        if amount is not None and amount_usdc is not None:
            raise ValueError("Provide either amount or amount_usdc, not both.")
        if amount_usdc is not None:
            return int(amount_usdc * 1_000_000)
        if amount is None:
            raise ValueError("Provide either amount or amount_usdc.")
        return amount

    def _eoa_address(self) -> str:
        """Return the checksummed EOA address derived from private_key."""
        from eth_account import Account

        return Account.from_key(self.private_key).address

    def _tx_params(self) -> dict:
        """Base transaction params with ``from`` set to the EOA address."""
        params: dict = {"from": self._eoa_address()}
        # Suppress auto gas-estimation in build_transaction when using
        # a proxy wallet — the EOA has no tokens so estimation would fail.
        # estimate_ctf_tx / _send_ctf_tx handle gas separately.
        if self._has_proxy_wallet():
            params["gas"] = 0
        return params

    def _send_ctf_tx(
        self,
        tx_data: dict,
        *,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt:
        """Sign, send, and optionally wait for a CTF transaction."""
        self._require_ctf_auth()
        self._require_web3()

        account = self._w3.eth.account.from_key(self.private_key)
        tx_data["from"] = account.address
        tx_data["nonce"] = self._w3.eth.get_transaction_count(account.address)
        tx_data["chainId"] = self.chain_id

        if "gas" not in tx_data:
            tx_data["gas"] = self._w3.eth.estimate_gas(tx_data)
        # Don't add gasPrice if EIP-1559 fields already present
        if "maxFeePerGas" not in tx_data and "gasPrice" not in tx_data:
            tx_data["gasPrice"] = self._w3.eth.gas_price

        signed = account.sign_transaction(tx_data)
        tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)

        result: dict = {"txHash": tx_hash.hex()}
        if wait:
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            result["blockNumber"] = receipt["blockNumber"]
            result["status"] = receipt["status"]
            result["gasUsed"] = receipt["gasUsed"]
        return result

    def _has_proxy_wallet(self) -> bool:
        """True when address is a proxy wallet distinct from the EOA."""
        addr: str | None = getattr(self, "address", None)
        if not addr:
            return False
        return addr.lower() != self._eoa_address().lower()

    def _encode_proxy_calls(self, calls: list[tuple[int, str, int, bytes]]) -> str:
        """ABI-encode a ``proxy(calls)`` function call on the ProxyFactory."""
        from web3 import Web3

        factory = self._w3.eth.contract(
            address=Web3.to_checksum_address(PROXY_FACTORY),
            abi=_PROXY_FACTORY_ABI,
        )
        return factory.functions.proxy(calls).build_transaction(
            {"from": self._eoa_address(), "gas": 0}
        )["data"]

    def _sign_proxy_tx(
        self,
        from_: str,
        to: str,
        data: str,
        nonce: str,
        relay: str,
        gas_limit: str = "10000000",
    ) -> str:
        """Sign a Polymarket proxy transaction (GSN ``rlx:`` scheme)."""
        from eth_account import Account
        from eth_account.messages import encode_defunct

        # Build struct hash: keccak256("rlx:" + from + to + data +
        #   txFee(32) + gasPrice(32) + gasLimit(32) + nonce(32) +
        #   relayHub + relay)
        parts = (
            b"rlx:"
            + bytes.fromhex(from_[2:])
            + bytes.fromhex(to[2:])
            + bytes.fromhex(data[2:])
            + (0).to_bytes(32, "big")  # txFee = 0
            + (0).to_bytes(32, "big")  # gasPrice = 0
            + int(gas_limit).to_bytes(32, "big")
            + int(nonce).to_bytes(32, "big")
            + bytes.fromhex(RELAY_HUB[2:])
            + bytes.fromhex(relay[2:])
        )
        from eth_utils import keccak

        struct_hash = keccak(parts)
        signable = encode_defunct(struct_hash)
        return "0x" + Account.sign_message(signable, private_key=self.private_key).signature.hex()

    def _send_ctf_tx_relayed(self, to: str, tx_data: dict) -> SubmitTransactionResponse:
        """Submit a CTF transaction through the relayer (proxy wallet).

        Requires builder API credentials for HMAC authentication.
        """
        self._require_builder_auth()
        eoa = self._eoa_address()
        payload = self.get_relay_payload(address=eoa, type="PROXY")
        nonce = payload["nonce"]
        relay = payload["address"]

        # Wrap the raw call in a proxy(calls) envelope
        inner_data = bytes.fromhex(tx_data["data"][2:])
        proxy_data = self._encode_proxy_calls(
            [(1, to, 0, inner_data)]  # typeCode=1 (Call)
        )

        # Estimate gas for the proxy call
        try:
            from web3.types import HexStr

            est = self._w3.eth.estimate_gas(
                {"from": eoa, "to": PROXY_FACTORY, "data": HexStr(proxy_data)}
            )
            gas_limit = str(est)
        except Exception:
            gas_limit = "10000000"
        signature = self._sign_proxy_tx(
            from_=eoa,
            to=PROXY_FACTORY,
            data=proxy_data,
            nonce=nonce,
            relay=relay,
            gas_limit=gas_limit,
        )
        return self.submit_transaction(
            from_=eoa,
            to=PROXY_FACTORY,
            proxy_wallet=self.address,
            data=proxy_data,
            nonce=nonce,
            signature=signature,
            type="PROXY",
            signature_params={
                "gasPrice": "0",
                "gasLimit": gas_limit,
                "relayerFee": "0",
                "relayHub": RELAY_HUB,
                "relay": relay,
            },
        )

    def _ensure_allowance(self, spender: str, amount: int) -> None:
        """Approve *spender* if current USDC.e allowance is below *amount*."""
        owner = self.address if self._has_proxy_wallet() else self._eoa_address()
        allowance = self._usdc_contract.functions.allowance(
            owner, self._w3.to_checksum_address(spender)
        ).call()
        if allowance < amount:
            self.approve_collateral(spender=spender)

    # ── Public methods ───────────────────────────────────────────────

    def estimate_ctf_tx(self, tx_data: dict) -> GasEstimate:
        """Estimate gas cost for a CTF transaction without sending it.

        Args:
            tx_data: Transaction dict as returned by
                ``contract.functions.method(...).build_transaction(...)``.

        Returns:
            dict with ``gas``, ``gasPrice``, ``costWei``, ``costMatic``,
            and ``eoaBalance``.
        """
        self._require_ctf_auth()
        self._require_web3()
        eoa = self._eoa_address()
        # Simulate from proxy wallet when tokens live there
        if self._has_proxy_wallet():
            tx_data = {**tx_data, "from": self.address}
            # Proxy may have 0 MATIC; override balance so simulation runs
            state_override = {self.address: {"balance": hex(10**18)}}
            gas = self._w3.eth.estimate_gas(tx_data, state_override=state_override)
        else:
            gas = self._w3.eth.estimate_gas(tx_data)
        gas_price = self._w3.eth.gas_price
        cost_wei = gas * gas_price
        return {
            "gas": gas,
            "gasPrice": gas_price,
            "costWei": cost_wei,
            "costMatic": cost_wei / 1e18,
            "eoaBalance": self._w3.eth.get_balance(eoa),
        }

    def approve_collateral(
        self,
        spender: str | None = None,
        amount: int | None = None,
        *,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | GasEstimate:
        """Approve a CTF contract to spend USDC.e on your behalf.

        Args:
            spender: Contract address to approve.  Defaults to the
                ConditionalTokens contract.  Pass the NegRiskAdapter
                address for neg-risk markets.
            amount: Amount in USDC.e base units (6 decimals).
                ``None`` for max (unlimited) approval.
            estimate: If ``True``, return a :class:`GasEstimate` dict
                instead of sending the transaction.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.  If *estimate*, returns :class:`GasEstimate` instead.
        """
        self._require_ctf_auth()
        self._require_web3()
        if spender is None:
            spender = CONDITIONAL_TOKENS

        if amount is None:
            amount = 2**256 - 1
        tx = self._usdc_contract.functions.approve(
            self._w3.to_checksum_address(spender), amount
        ).build_transaction(self._tx_params())
        if estimate:
            return self.estimate_ctf_tx(tx)
        if self._has_proxy_wallet():
            return self._send_ctf_tx_relayed(to=USDC_E, tx_data=tx)
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def split_position(
        self,
        condition_id: str | bytes,
        amount: int | None = None,
        *,
        amount_usdc: float | None = None,
        neg_risk: bool = False,
        auto_approve: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | GasEstimate:
        """Split USDC.e collateral into Yes + No outcome tokens.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            amount: USDC.e amount in base units (6 decimals).
                E.g. ``1_000_000`` = 1.00 USDC.
            amount_usdc: Convenience alternative — amount in USDC
                (e.g. ``1.0`` for 1 USDC). Mutually exclusive with ``amount``.
            neg_risk: ``True`` for neg-risk (multi-outcome) markets
                (uses NegRiskAdapter); ``False`` for standard binary
                markets (uses ConditionalTokens).
            auto_approve: If ``True``, check USDC.e allowance and send
                an approval transaction if needed before splitting.
            estimate: If ``True``, return a :class:`GasEstimate` dict
                instead of sending the transaction.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.  If *estimate*, returns :class:`GasEstimate` instead.
        """
        self._require_ctf_auth()
        self._require_web3()
        amount = self._resolve_amount(amount, amount_usdc)
        cid = self._to_bytes32(condition_id)

        if neg_risk:
            tx = self._nr_contract.functions.splitPosition(cid, amount).build_transaction(
                self._tx_params()
            )
        else:
            tx = self._ct_contract.functions.splitPosition(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                DEFAULT_PARTITION,
                amount,
            ).build_transaction(self._tx_params())
        if estimate:
            return self.estimate_ctf_tx(tx)
        if auto_approve:
            spender = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
            self._ensure_allowance(spender, amount)
        if self._has_proxy_wallet():
            target = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
            return self._send_ctf_tx_relayed(to=target, tx_data=tx)
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def merge_positions(
        self,
        condition_id: str | bytes,
        amount: int | None = None,
        *,
        amount_usdc: float | None = None,
        neg_risk: bool = False,
        auto_approve: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | GasEstimate:
        """Merge equal amounts of Yes + No outcome tokens back into USDC.e.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            amount: Token amount in base units (6 decimals).
            amount_usdc: Convenience alternative — amount in USDC
                (e.g. ``1.0`` for 1 USDC). Mutually exclusive with ``amount``.
            neg_risk: ``True`` for neg-risk markets (NegRiskAdapter);
                ``False`` for standard binary markets (ConditionalTokens).
            auto_approve: If ``True``, check USDC.e allowance and send
                an approval transaction if needed before merging.
            estimate: If ``True``, return a :class:`GasEstimate` dict
                instead of sending the transaction.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.  If *estimate*, returns :class:`GasEstimate` instead.
        """
        self._require_ctf_auth()
        self._require_web3()
        amount = self._resolve_amount(amount, amount_usdc)
        cid = self._to_bytes32(condition_id)

        if neg_risk:
            tx = self._nr_contract.functions.mergePositions(cid, amount).build_transaction(
                self._tx_params()
            )
        else:
            tx = self._ct_contract.functions.mergePositions(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                DEFAULT_PARTITION,
                amount,
            ).build_transaction(self._tx_params())
        if estimate:
            return self.estimate_ctf_tx(tx)
        if auto_approve:
            spender = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
            self._ensure_allowance(spender, amount)
        if self._has_proxy_wallet():
            target = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS
            return self._send_ctf_tx_relayed(to=target, tx_data=tx)
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def redeem_positions(
        self,
        condition_id: str | bytes,
        index_sets: list[int] | None = None,
        *,
        neg_risk: bool = False,
        amounts: list[int] | None = None,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | GasEstimate:
        """Redeem winning outcome tokens for USDC.e after market resolution.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            index_sets: Outcome index sets to redeem (standard markets
                only). Defaults to ``[1, 2]`` (standard binary market).
                Ignored when ``neg_risk=True``.
            neg_risk: ``True`` for neg-risk markets (uses NegRiskAdapter);
                ``False`` for standard binary markets (ConditionalTokens).
            amounts: Required when ``neg_risk=True``. A 2-element list of
                token amounts in base units to redeem: ``[yes_amount,
                no_amount]``. Only the winning side has a non-zero value;
                the losing side should be ``0``. For standard markets
                the contract reads the user's full balance so amounts
                are not needed.
            estimate: If ``True``, return a :class:`GasEstimate` dict
                instead of sending the transaction.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.  If *estimate*, returns :class:`GasEstimate` instead.
        """
        self._require_ctf_auth()
        self._require_web3()
        cid = self._to_bytes32(condition_id)

        if neg_risk:
            if amounts is None or len(amounts) != 2:
                raise ValueError(
                    "Neg-risk redemption requires amounts=[yes_amount,"
                    " no_amount] in base units (6 decimals)."
                )
            tx = self._nr_contract.functions.redeemPositions(
                cid, [int(a) for a in amounts]
            ).build_transaction(self._tx_params())
            target = NEG_RISK_ADAPTER
        else:
            if index_sets is None:
                index_sets = DEFAULT_PARTITION
            tx = self._ct_contract.functions.redeemPositions(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                index_sets,
            ).build_transaction(self._tx_params())
            target = CONDITIONAL_TOKENS

        if estimate:
            return self.estimate_ctf_tx(tx)
        if self._has_proxy_wallet():
            return self._send_ctf_tx_relayed(to=target, tx_data=tx)
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def convert_positions(
        self,
        market_id: str | bytes,
        index_set: int,
        amount: int | None = None,
        *,
        amount_usdc: float | None = None,
        auto_approve: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | GasEstimate:
        """Convert NO tokens across outcomes into YES tokens + USDC collateral.

        Calls ``convertPositions`` on the NegRiskAdapter contract.  This is
        the key operation for neg-risk arbitrage: buy NO on all outcomes,
        then convert (N-1 NOs → 1 YES + (N-2) USDC), then merge (YES+NO → 1
        USDC).

        Args:
            market_id: Neg-risk market ID (hex string or bytes32).  This is
                the event-level ``negRiskMarketID`` from market data, **not**
                the ``conditionId``.
            index_set: Bitmask of which outcomes have NO positions to convert.
                Bit N set = outcome N's NO token is included.  E.g. for 5
                outcomes converting all NOs: ``0b11111`` = ``31``.
            amount: Token amount in base units (6 decimals).
            amount_usdc: Convenience alternative — amount in USDC
                (e.g. ``1.0`` for 1 USDC). Mutually exclusive with ``amount``.
            auto_approve: If ``True``, check USDC.e allowance and send
                an approval transaction if needed before converting.
            estimate: If ``True``, return a :class:`GasEstimate` dict
                instead of sending the transaction.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.  If *estimate*, returns :class:`GasEstimate` instead.
        """
        self._require_ctf_auth()
        self._require_web3()
        amount = self._resolve_amount(amount, amount_usdc)
        mid = self._to_bytes32(market_id)

        tx = self._nr_contract.functions.convertPositions(
            mid, index_set, amount
        ).build_transaction(self._tx_params())

        if estimate:
            return self.estimate_ctf_tx(tx)
        if auto_approve:
            self._ensure_allowance(NEG_RISK_ADAPTER, amount)
        if self._has_proxy_wallet():
            return self._send_ctf_tx_relayed(to=NEG_RISK_ADAPTER, tx_data=tx)
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    # ── Batch operations ─────────────────────────────────────────────

    _VALID_OPS = ("split", "merge", "redeem", "convert")

    def _build_ctf_call(self, op: dict) -> tuple[str, bytes, str | None, int]:
        """Build a single CTF call for use in a batch proxy envelope.

        Returns ``(target_address, calldata_bytes, approval_spender_or_None,
        approval_amount)``. Approval fields are ``(None, 0)`` for ops that
        don't need USDC.e approval (redeem).
        """
        op_name = op.get("op")
        if op_name not in self._VALID_OPS:
            raise ValueError(f"op must be one of {self._VALID_OPS}, got {op_name!r}")
        cid = self._to_bytes32(op["condition_id"])
        neg_risk = bool(op.get("neg_risk", False))
        target = NEG_RISK_ADAPTER if neg_risk else CONDITIONAL_TOKENS

        if op_name == "convert":
            amount = self._resolve_amount(op.get("amount"), op.get("amount_usdc"))
            index_set = op.get("index_set")
            if index_set is None:
                raise ValueError("convert op requires 'index_set' (bitmask of NO outcomes).")
            mid = self._to_bytes32(op.get("market_id") or op["condition_id"])
            tx = self._nr_contract.functions.convertPositions(
                mid, int(index_set), amount
            ).build_transaction(self._tx_params())
            return NEG_RISK_ADAPTER, bytes.fromhex(tx["data"][2:]), NEG_RISK_ADAPTER, amount

        if op_name in ("split", "merge"):
            amount = self._resolve_amount(op.get("amount"), op.get("amount_usdc"))
            fn_name = "splitPosition" if op_name == "split" else "mergePositions"
            contract = self._nr_contract if neg_risk else self._ct_contract
            if neg_risk:
                fn = getattr(contract.functions, fn_name)(cid, amount)
            else:
                fn = getattr(contract.functions, fn_name)(
                    self._w3.to_checksum_address(USDC_E),
                    PARENT_COLLECTION_ID,
                    cid,
                    DEFAULT_PARTITION,
                    amount,
                )
            tx = fn.build_transaction(self._tx_params())
            return target, bytes.fromhex(tx["data"][2:]), target, amount

        # redeem
        if neg_risk:
            amounts = op.get("amounts")
            if amounts is None or len(amounts) != 2:
                raise ValueError("Neg-risk redeem requires amounts=[yes_amount, no_amount].")
            tx = self._nr_contract.functions.redeemPositions(
                cid, [int(a) for a in amounts]
            ).build_transaction(self._tx_params())
        else:
            index_sets = op.get("index_sets") or DEFAULT_PARTITION
            tx = self._ct_contract.functions.redeemPositions(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                index_sets,
            ).build_transaction(self._tx_params())
        return target, bytes.fromhex(tx["data"][2:]), None, 0

    def _send_ctf_batch_relayed(
        self, calls: list[tuple[int, str, int, bytes]]
    ) -> SubmitTransactionResponse:
        """Submit a batch of proxy calls through the relayer in one transaction."""
        self._require_builder_auth()
        eoa = self._eoa_address()
        payload = self.get_relay_payload(address=eoa, type="PROXY")
        nonce = payload["nonce"]
        relay = payload["address"]

        proxy_data = self._encode_proxy_calls(calls)

        try:
            from web3.types import HexStr

            est = self._w3.eth.estimate_gas(
                {"from": eoa, "to": PROXY_FACTORY, "data": HexStr(proxy_data)}
            )
            gas_limit = str(est)
        except Exception:
            gas_limit = "10000000"
        signature = self._sign_proxy_tx(
            from_=eoa,
            to=PROXY_FACTORY,
            data=proxy_data,
            nonce=nonce,
            relay=relay,
            gas_limit=gas_limit,
        )
        return self.submit_transaction(
            from_=eoa,
            to=PROXY_FACTORY,
            proxy_wallet=self.address,
            data=proxy_data,
            nonce=nonce,
            signature=signature,
            type="PROXY",
            signature_params={
                "gasPrice": "0",
                "gasLimit": gas_limit,
                "relayerFee": "0",
                "relayHub": RELAY_HUB,
                "relay": relay,
            },
        )

    def batch_ctf_ops(
        self,
        ops: list[dict] | pd.DataFrame,
        *,
        auto_approve: bool = False,
        estimate: bool = False,
    ) -> SubmitTransactionResponse | GasEstimate:
        """Bundle multiple split/merge/redeem operations into one proxy call.

        Each op dict accepts: ``op`` (``"split"`` | ``"merge"`` | ``"redeem"``),
        ``condition_id``, ``amount`` or ``amount_usdc`` (split/merge),
        ``neg_risk`` (bool), ``index_sets`` (redeem, standard), ``amounts``
        (redeem, neg-risk). A DataFrame is converted via ``to_dict("records")``.

        Gas savings come from a single proxy signature / GSN relay hop instead
        of one per op. The underlying CTF calls still run individually.

        Only proxy-wallet users are supported — Polymarket does not publish a
        multicall target for EOAs. EOA senders get a clear error; use the
        individual methods instead.

        Args:
            ops: List of op dicts or a DataFrame with columns named the same.
            auto_approve: If ``True``, aggregate split/merge amounts per
                spender and send a single approval per spender if the current
                allowance is insufficient.
            estimate: If ``True``, return a :class:`GasEstimate` for the
                batched proxy call without submitting.

        Returns:
            :class:`SubmitTransactionResponse` on success, or
            :class:`GasEstimate` when ``estimate=True``.
        """
        import pandas as pd

        self._require_ctf_auth()
        self._require_web3()

        if isinstance(ops, pd.DataFrame):
            ops = ops.to_dict(orient="records")
        if not ops:
            raise ValueError("ops must be a non-empty list of operation dicts.")
        if not self._has_proxy_wallet():
            raise PolymarketAuthError(
                detail=(
                    "batch_ctf_ops requires a proxy wallet; Polymarket's EOA path "
                    "has no multicall target. Use individual split/merge/redeem "
                    "calls instead."
                )
            )

        calls: list[tuple[int, str, int, bytes]] = []
        approvals: dict[str, int] = {}
        for op in ops:
            target, data, spender, approval_amount = self._build_ctf_call(op)
            calls.append((1, target, 0, data))  # typeCode=1 (Call)
            if spender is not None:
                approvals[spender] = approvals.get(spender, 0) + approval_amount

        if estimate:
            proxy_data = self._encode_proxy_calls(calls)
            tx = {"to": PROXY_FACTORY, "data": proxy_data, "from": self._eoa_address()}
            return self.estimate_ctf_tx(tx)

        if auto_approve:
            for spender, total in approvals.items():
                self._ensure_allowance(spender, total)

        return self._send_ctf_batch_relayed(calls)
