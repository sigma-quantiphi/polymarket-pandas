"""UMA resolution / dispute mixin.

Exposes the Polymarket UMA CTF Adapter + UMA OptimisticOracleV2 flow so
callers can script market-resolution disputes (propose price, dispute,
settle, resolve).  Requires the ``web3`` optional dependency:
``pip install polymarket-pandas[ctf]``.

.. warning::
    **V1 flow only.** The contract addresses below are V1-era. After the
    V2 cutover (2026-04-28), Polymarket published a different
    UmaCtfAdapter address (``0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74``)
    that exposes a different ABI from the one declared here. The V1
    addresses still have on-chain bytecode and the regular (non-neg-risk)
    flow remains usable for V1 markets, but **V2 markets cannot be
    queried or disputed through this mixin until issue #20 is resolved**.

    The previously-shipped ``NegRiskUmaCtfAdapter`` address
    (``0x2F5e3684cb1F318ec51b00Edba38d79Ac2c7c324``) was verified to have
    **zero bytecode** on Polygon — no contract is deployed at that
    address. Any neg-risk UMA call now raises ``NotImplementedError``
    pointing at issue #20 instead of silently failing.

Contract layer (all on Polygon mainnet):

* ``UmaCtfAdapter``        — V1; stores per-question metadata and, on
                              ``resolve``, pulls the settled price from
                              OOv2 and reports payouts to the CTF.
* ``NegRiskUmaCtfAdapter`` — V1; **address unknown / not deployed**. See above.
* ``OptimisticOracleV2``   — V1; where all propose / dispute / settle calls
                              actually happen.  The adapter is only the
                              ``requester`` for OO lookups.

See ``CLAUDE.md`` for the design notes and gotchas.
"""

from __future__ import annotations

from polymarket_pandas.mixins._ctf import USDC_E
from polymarket_pandas.types import (
    GasEstimate,
    OptimisticOracleRequest,
    SubmitTransactionResponse,
    TransactionReceipt,
    UmaQuestion,
)

# ── Contract addresses (Polygon mainnet) ─────────────────────────────

UMA_CTF_ADAPTER = "0x157Ce2d672854c848c9b79C49a8Cc6cc89176a49"
# V1 address; on-chain probe (2026-04-29) showed 0 bytecode — no contract
# deployed at this address. Kept as a sentinel so existing imports don't
# break, but `_adapter_contract(neg_risk=True)` raises NotImplementedError.
# See issue #20 for the V2 NegRiskUmaCtfAdapter port.
NEG_RISK_UMA_CTF_ADAPTER: str | None = None
OPTIMISTIC_ORACLE_V2 = "0xeE3Afe347D5C74317041E2618C49534dAf887c24"

_NEG_RISK_NOT_SUPPORTED = (
    "Neg-risk UMA flow is not supported in this release. The "
    "NegRiskUmaCtfAdapter address shipped in v0.9.x "
    "(0x2F5e3684cb1F318ec51b00Edba38d79Ac2c7c324) has no on-chain "
    "bytecode, and the V2 contracts page does not list a replacement. "
    "Track issue #20 for the full V2 UMA port."
)

# bytes32("YES_OR_NO_QUERY") — right-padded with zeros to 32 bytes.
YES_OR_NO_IDENTIFIER = b"YES_OR_NO_QUERY".ljust(32, b"\x00")

# Legal proposed prices for YES_OR_NO_QUERY (UMIP-107).
PRICE_NO = 0
PRICE_YES = 10**18
PRICE_UNRESOLVED = 5 * 10**17  # 50/50
PRICE_IGNORE = -(2**255)  # type(int256).min
_VALID_PROPOSED_PRICES = frozenset({PRICE_NO, PRICE_YES, PRICE_UNRESOLVED, PRICE_IGNORE})

# Decoded OOv2 state enum (index → name).
_OO_STATES = (
    "Invalid",
    "Requested",
    "Proposed",
    "Expired",
    "Disputed",
    "Resolved",
    "Settled",
)

# ── Minimal ABIs ─────────────────────────────────────────────────────

_QUESTION_DATA_COMPONENTS = [
    {"name": "requestTimestamp", "type": "uint256"},
    {"name": "reward", "type": "uint256"},
    {"name": "proposalBond", "type": "uint256"},
    {"name": "liveness", "type": "uint256"},
    {"name": "emergencyResolutionTimestamp", "type": "uint256"},
    {"name": "resolved", "type": "bool"},
    {"name": "paused", "type": "bool"},
    {"name": "reset", "type": "bool"},
    {"name": "refund", "type": "bool"},
    {"name": "rewardToken", "type": "address"},
    {"name": "creator", "type": "address"},
    {"name": "ancillaryData", "type": "bytes"},
]

_UMA_ADAPTER_ABI = [
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "getQuestion",
        "outputs": [{"components": _QUESTION_DATA_COMPONENTS, "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "isInitialized",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "isFlagged",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "ready",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "getExpectedPayouts",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "questionID", "type": "bytes32"}],
        "name": "resolve",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

_OO_REQUEST_COMPONENTS = [
    {"name": "proposer", "type": "address"},
    {"name": "disputer", "type": "address"},
    {"name": "currency", "type": "address"},
    {"name": "settled", "type": "bool"},
    {
        "components": [
            {"name": "eventBased", "type": "bool"},
            {"name": "refundOnDispute", "type": "bool"},
            {"name": "callbackOnPriceProposed", "type": "bool"},
            {"name": "callbackOnPriceDisputed", "type": "bool"},
            {"name": "callbackOnPriceSettled", "type": "bool"},
            {"name": "bond", "type": "uint256"},
            {"name": "customLiveness", "type": "uint256"},
        ],
        "name": "requestSettings",
        "type": "tuple",
    },
    {"name": "proposedPrice", "type": "int256"},
    {"name": "resolvedPrice", "type": "int256"},
    {"name": "expirationTime", "type": "uint256"},
    {"name": "reward", "type": "uint256"},
    {"name": "finalFee", "type": "uint256"},
]

_OO_ABI = [
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
        ],
        "name": "getRequest",
        "outputs": [{"components": _OO_REQUEST_COMPONENTS, "name": "", "type": "tuple"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
        ],
        "name": "getState",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
        ],
        "name": "hasPrice",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
            {"name": "proposedPrice", "type": "int256"},
        ],
        "name": "proposePrice",
        "outputs": [{"name": "totalBond", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
        ],
        "name": "disputePrice",
        "outputs": [{"name": "totalBond", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "requester", "type": "address"},
            {"name": "identifier", "type": "bytes32"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "ancillaryData", "type": "bytes"},
        ],
        "name": "settle",
        "outputs": [{"name": "payout", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


class UmaMixin:
    """Resolution / dispute flow for Polymarket's UMA CTF Adapter."""

    # ── Internal helpers ─────────────────────────────────────────────

    def _require_uma_contracts(self) -> None:
        """Lazily instantiate UMA adapter + OOv2 web3 contract objects.

        The neg-risk adapter is **not** instantiated — its address has
        no on-chain bytecode (see module docstring). Neg-risk callers
        get a clear ``NotImplementedError`` from
        :meth:`_adapter_contract` instead of a silent revert.
        """
        self._require_web3()
        if hasattr(self, "_uma_adapter"):
            return
        self._uma_adapter = self._w3.eth.contract(
            address=self._w3.to_checksum_address(UMA_CTF_ADAPTER),
            abi=_UMA_ADAPTER_ABI,
        )
        self._uma_nr_adapter = None  # see module docstring + issue #20
        self._oo_v2 = self._w3.eth.contract(
            address=self._w3.to_checksum_address(OPTIMISTIC_ORACLE_V2),
            abi=_OO_ABI,
        )

    @staticmethod
    def _adapter_address(neg_risk: bool) -> str:
        if neg_risk:
            raise NotImplementedError(_NEG_RISK_NOT_SUPPORTED)
        return UMA_CTF_ADAPTER

    def _adapter_contract(self, neg_risk: bool):
        if neg_risk:
            raise NotImplementedError(_NEG_RISK_NOT_SUPPORTED)
        return self._uma_adapter

    @staticmethod
    def _validate_proposed_price(price: int) -> None:
        if price not in _VALID_PROPOSED_PRICES:
            raise ValueError(
                f"Invalid proposed price {price!r}. Must be one of: "
                "0 (NO), 5e17 (50/50), 1e18 (YES), or -(2**255) (ignore)."
            )

    def _send_uma_tx(
        self,
        tx_data: dict,
        to: str,
        *,
        as_proxy: bool,
        estimate: bool,
        wait: bool,
        timeout: int,
    ) -> TransactionReceipt | SubmitTransactionResponse | GasEstimate:
        """Common tail for UMA write methods: estimate / proxy-route / EOA send."""
        if estimate:
            return self.estimate_ctf_tx(tx_data)
        if as_proxy and self._has_proxy_wallet():
            return self._send_ctf_tx_relayed(to=to, tx_data=tx_data)
        # UMA disputes are typically run from an EOA even when a proxy
        # wallet is configured — see CLAUDE.md.  Force the ``from`` to
        # the EOA so build_transaction's proxy-friendly ``gas=0`` hack
        # (see _tx_params) doesn't leak in.
        tx_data = {**tx_data, "from": self._eoa_address()}
        tx_data.pop("gas", None)
        return self._send_ctf_tx(tx_data, wait=wait, timeout=timeout)

    # ── Read methods ─────────────────────────────────────────────────

    def get_uma_question(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
    ) -> UmaQuestion:
        """Fetch the UMA adapter's stored metadata for a question.

        Args:
            question_id: The ``questionID`` (``keccak256(ancillaryData)``)
                as hex string or 32-byte value.
            neg_risk: ``True`` to read from :data:`NEG_RISK_UMA_CTF_ADAPTER`.

        Returns:
            :class:`UmaQuestion` with the raw on-chain fields.  The
            ``ancillaryData`` bytes are returned as-is — do not
            reconstruct them on the client side.
        """
        self._require_uma_contracts()
        qid = self._to_bytes32(question_id)
        raw = self._adapter_contract(neg_risk).functions.getQuestion(qid).call()
        return {
            "requestTimestamp": raw[0],
            "reward": raw[1],
            "proposalBond": raw[2],
            "liveness": raw[3],
            "emergencyResolutionTimestamp": raw[4],
            "resolved": raw[5],
            "paused": raw[6],
            "reset": raw[7],
            "refund": raw[8],
            "rewardToken": raw[9],
            "creator": raw[10],
            "ancillaryData": bytes(raw[11]),
        }

    def get_oo_request(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
    ) -> OptimisticOracleRequest:
        """Fetch the live OOv2 ``Request`` for a question.

        Always re-reads the adapter to get the current
        ``requestTimestamp`` (which rotates after each dispute-reset).
        """
        self._require_uma_contracts()
        q = self.get_uma_question(question_id, neg_risk=neg_risk)
        requester = self._adapter_address(neg_risk)
        raw = self._oo_v2.functions.getRequest(
            self._w3.to_checksum_address(requester),
            YES_OR_NO_IDENTIFIER,
            q["requestTimestamp"],
            q["ancillaryData"],
        ).call()
        settings = raw[4]
        return {
            "proposer": raw[0],
            "disputer": raw[1],
            "currency": raw[2],
            "settled": raw[3],
            "bond": settings[5],
            "customLiveness": settings[6],
            "proposedPrice": raw[5],
            "resolvedPrice": raw[6],
            "expirationTime": raw[7],
            "reward": raw[8],
            "finalFee": raw[9],
        }

    def get_uma_state(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
    ) -> str:
        """Return the OOv2 state as one of the names in :data:`_OO_STATES`."""
        self._require_uma_contracts()
        q = self.get_uma_question(question_id, neg_risk=neg_risk)
        idx = self._oo_v2.functions.getState(
            self._w3.to_checksum_address(self._adapter_address(neg_risk)),
            YES_OR_NO_IDENTIFIER,
            q["requestTimestamp"],
            q["ancillaryData"],
        ).call()
        if 0 <= idx < len(_OO_STATES):
            return _OO_STATES[idx]
        raise ValueError(f"Unknown OOv2 state index {idx}")

    def ready_to_resolve(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
    ) -> bool:
        """Return ``True`` if :func:`resolve_market` can be called."""
        self._require_uma_contracts()
        qid = self._to_bytes32(question_id)
        return bool(self._adapter_contract(neg_risk).functions.ready(qid).call())

    # ── Write methods ────────────────────────────────────────────────

    def propose_price(
        self,
        question_id: str | bytes,
        price: int,
        *,
        neg_risk: bool = False,
        auto_approve: bool = True,
        as_proxy: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | SubmitTransactionResponse | GasEstimate:
        """Propose a resolution price on OOv2 for a UMA-resolved market.

        Approves ``reward + proposalBond`` USDC.e to OOv2 if
        ``auto_approve=True`` (the default) and the current allowance is
        insufficient.

        Args:
            question_id: The UMA ``questionID`` (hex string or 32 bytes).
            price: Proposed price.  Must be one of :data:`PRICE_NO`
                (0), :data:`PRICE_UNRESOLVED` (5e17), :data:`PRICE_YES`
                (1e18), or :data:`PRICE_IGNORE` (-(2**255)).
            neg_risk: ``True`` for neg-risk markets.
            auto_approve: Pre-check USDC.e allowance and send an approval
                transaction if below ``reward + bond``.
            as_proxy: Route via the GSN relayer (proxy wallet) instead
                of sending from the EOA.  Default ``False`` — dispute
                bots typically run from a hot EOA.
            estimate: Return a :class:`GasEstimate` without sending.
            wait: Wait for the transaction receipt.
            timeout: Seconds to wait for the receipt.
        """
        self._require_ctf_auth()
        self._require_uma_contracts()
        self._validate_proposed_price(price)

        state = self.get_uma_state(question_id, neg_risk=neg_risk)
        if state != "Requested":
            raise ValueError(
                f"Cannot propose price: OOv2 state is {state!r}, expected 'Requested'."
            )

        q = self.get_uma_question(question_id, neg_risk=neg_risk)
        requester = self._w3.to_checksum_address(self._adapter_address(neg_risk))
        tx = self._oo_v2.functions.proposePrice(
            requester,
            YES_OR_NO_IDENTIFIER,
            q["requestTimestamp"],
            q["ancillaryData"],
            int(price),
        ).build_transaction(self._tx_params())

        if auto_approve and not estimate:
            self._ensure_allowance(OPTIMISTIC_ORACLE_V2, q["reward"] + q["proposalBond"])
        return self._send_uma_tx(
            tx,
            to=OPTIMISTIC_ORACLE_V2,
            as_proxy=as_proxy,
            estimate=estimate,
            wait=wait,
            timeout=timeout,
        )

    def dispute_price(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
        auto_approve: bool = True,
        as_proxy: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | SubmitTransactionResponse | GasEstimate:
        """Dispute the currently-proposed price on OOv2.

        Approves ``proposalBond`` USDC.e (no reward) to OOv2 when
        ``auto_approve=True``.  First dispute auto-resets the adapter
        with a fresh ``requestTimestamp``; a second dispute escalates
        to UMA's DVM and resolution may take 48–72h.
        """
        self._require_ctf_auth()
        self._require_uma_contracts()

        state = self.get_uma_state(question_id, neg_risk=neg_risk)
        if state != "Proposed":
            raise ValueError(f"Cannot dispute: OOv2 state is {state!r}, expected 'Proposed'.")

        q = self.get_uma_question(question_id, neg_risk=neg_risk)
        requester = self._w3.to_checksum_address(self._adapter_address(neg_risk))
        tx = self._oo_v2.functions.disputePrice(
            requester,
            YES_OR_NO_IDENTIFIER,
            q["requestTimestamp"],
            q["ancillaryData"],
        ).build_transaction(self._tx_params())

        if auto_approve and not estimate:
            self._ensure_allowance(OPTIMISTIC_ORACLE_V2, q["proposalBond"])
        return self._send_uma_tx(
            tx,
            to=OPTIMISTIC_ORACLE_V2,
            as_proxy=as_proxy,
            estimate=estimate,
            wait=wait,
            timeout=timeout,
        )

    def settle_oo(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
        as_proxy: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | SubmitTransactionResponse | GasEstimate:
        """Settle the OOv2 price for a question (anyone can call)."""
        self._require_ctf_auth()
        self._require_uma_contracts()

        q = self.get_uma_question(question_id, neg_risk=neg_risk)
        requester = self._w3.to_checksum_address(self._adapter_address(neg_risk))
        tx = self._oo_v2.functions.settle(
            requester,
            YES_OR_NO_IDENTIFIER,
            q["requestTimestamp"],
            q["ancillaryData"],
        ).build_transaction(self._tx_params())
        return self._send_uma_tx(
            tx,
            to=OPTIMISTIC_ORACLE_V2,
            as_proxy=as_proxy,
            estimate=estimate,
            wait=wait,
            timeout=timeout,
        )

    def resolve_market(
        self,
        question_id: str | bytes,
        *,
        neg_risk: bool = False,
        as_proxy: bool = False,
        estimate: bool = False,
        wait: bool = True,
        timeout: int = 120,
    ) -> TransactionReceipt | SubmitTransactionResponse | GasEstimate:
        """Call ``adapter.resolve(questionID)`` to push payouts to the CTF.

        Requires :func:`ready_to_resolve` to return ``True`` — i.e. OOv2
        must have a settleable or settled price.
        """
        self._require_ctf_auth()
        self._require_uma_contracts()

        qid = self._to_bytes32(question_id)
        adapter = self._adapter_contract(neg_risk)
        tx = adapter.functions.resolve(qid).build_transaction(self._tx_params())
        return self._send_uma_tx(
            tx,
            to=self._adapter_address(neg_risk),
            as_proxy=as_proxy,
            estimate=estimate,
            wait=wait,
            timeout=timeout,
        )


# Re-export the token constant so examples can refer to
# ``from polymarket_pandas.mixins._uma import USDC_E`` without reaching
# into ``_ctf``.
__all__ = [
    "NEG_RISK_UMA_CTF_ADAPTER",
    "OPTIMISTIC_ORACLE_V2",
    "PRICE_IGNORE",
    "PRICE_NO",
    "PRICE_UNRESOLVED",
    "PRICE_YES",
    "UMA_CTF_ADAPTER",
    "USDC_E",
    "UmaMixin",
    "YES_OR_NO_IDENTIFIER",
]
