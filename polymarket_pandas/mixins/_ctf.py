"""CTF (Conditional Token Framework) on-chain operations mixin.

Provides merge, split, and redeem for Polymarket positions via direct
smart-contract calls on Polygon.  Requires the ``web3`` optional
dependency: ``pip install polymarket-pandas[ctf]``.
"""

from __future__ import annotations

from polymarket_pandas.exceptions import PolymarketAuthError

# ── Contract addresses (Polygon mainnet) ─────────────────────────────

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

        rpc_url = getattr(self, "rpc_url", DEFAULT_RPC_URL)
        self._w3 = Web3(Web3.HTTPProvider(rpc_url))
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

    def _send_ctf_tx(
        self,
        tx_data: dict,
        *,
        wait: bool = True,
        timeout: int = 120,
    ) -> dict:
        """Sign, send, and optionally wait for a CTF transaction."""
        self._require_ctf_auth()
        self._require_web3()

        account = self._w3.eth.account.from_key(self.private_key)
        tx_data["from"] = account.address
        tx_data["nonce"] = self._w3.eth.get_transaction_count(account.address)
        tx_data["chainId"] = self.chain_id

        if "gas" not in tx_data:
            tx_data["gas"] = self._w3.eth.estimate_gas(tx_data)
        if "gasPrice" not in tx_data:
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

    # ── Public methods ───────────────────────────────────────────────

    def approve_collateral(
        self,
        spender: str | None = None,
        amount: int | None = None,
        *,
        wait: bool = True,
        timeout: int = 120,
    ) -> dict:
        """Approve a CTF contract to spend USDC.e on your behalf.

        Args:
            spender: Contract address to approve.  Defaults to the
                ConditionalTokens contract.  Pass the NegRiskAdapter
                address for neg-risk markets.
            amount: Amount in USDC.e base units (6 decimals).
                ``None`` for max (unlimited) approval.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.
        """
        self._require_ctf_auth()
        self._require_web3()
        if spender is None:
            spender = CONDITIONAL_TOKENS

        if amount is None:
            amount = 2**256 - 1
        tx = self._usdc_contract.functions.approve(
            self._w3.to_checksum_address(spender), amount
        ).build_transaction({})
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def split_position(
        self,
        condition_id: str | bytes,
        amount: int,
        *,
        neg_risk: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> dict:
        """Split USDC.e collateral into Yes + No outcome tokens.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            amount: USDC.e amount in base units (6 decimals).
                E.g. ``1_000_000`` = 1.00 USDC.
            neg_risk: ``True`` for neg-risk (multi-outcome) markets
                (uses NegRiskAdapter); ``False`` for standard binary
                markets (uses ConditionalTokens).
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.
        """
        self._require_ctf_auth()
        self._require_web3()
        cid = self._to_bytes32(condition_id)

        if neg_risk:
            tx = self._nr_contract.functions.splitPosition(
                cid, amount
            ).build_transaction({})
        else:
            tx = self._ct_contract.functions.splitPosition(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                DEFAULT_PARTITION,
                amount,
            ).build_transaction({})
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def merge_positions(
        self,
        condition_id: str | bytes,
        amount: int,
        *,
        neg_risk: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> dict:
        """Merge equal amounts of Yes + No outcome tokens back into USDC.e.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            amount: Token amount in base units (6 decimals).
            neg_risk: ``True`` for neg-risk markets (NegRiskAdapter);
                ``False`` for standard binary markets (ConditionalTokens).
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.
        """
        self._require_ctf_auth()
        self._require_web3()
        cid = self._to_bytes32(condition_id)

        if neg_risk:
            tx = self._nr_contract.functions.mergePositions(
                cid, amount
            ).build_transaction({})
        else:
            tx = self._ct_contract.functions.mergePositions(
                self._w3.to_checksum_address(USDC_E),
                PARENT_COLLECTION_ID,
                cid,
                DEFAULT_PARTITION,
                amount,
            ).build_transaction({})
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)

    def redeem_positions(
        self,
        condition_id: str | bytes,
        index_sets: list[int] | None = None,
        *,
        wait: bool = True,
        timeout: int = 120,
    ) -> dict:
        """Redeem winning outcome tokens for USDC.e after market resolution.

        Args:
            condition_id: Market condition ID (hex string or bytes32).
            index_sets: Outcome index sets to redeem.  Defaults to
                ``[1, 2]`` (standard binary market).
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.

        Returns:
            dict with ``txHash`` and, if *wait*, ``status``, ``blockNumber``,
            ``gasUsed``.
        """
        self._require_ctf_auth()
        self._require_web3()
        cid = self._to_bytes32(condition_id)
        if index_sets is None:
            index_sets = DEFAULT_PARTITION

        tx = self._ct_contract.functions.redeemPositions(
            self._w3.to_checksum_address(USDC_E),
            PARENT_COLLECTION_ID,
            cid,
            index_sets,
        ).build_transaction({})
        return self._send_ctf_tx(tx, wait=wait, timeout=timeout)
