"""TypedDict models for dict-returning endpoints.

These are structural subtypes of ``dict`` — existing code using
``result["key"]`` or ``result.get("key")`` continues to work unchanged.
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import (
    ActiveOrderSchema,
    BuilderTradeSchema,
    ClobTradeSchema,
    CurrentRewardSchema,
    EventSchema,
    MarketSchema,
    RewardsMarketMultiSchema,
    RewardsMarketSchema,
    SamplingMarketSchema,
    SimplifiedMarketSchema,
    UserEarningSchema,
    UserRewardsMarketSchema,
    XTrackerDailyStatSchema,
    XTrackerTrackingSchema,
)

# ── Cursor-paginated responses ────────────────────────────────────────


class CursorPage(TypedDict):
    """Base cursor-paginated response. Subclasses override ``data`` with a typed DataFrame."""

    data: pd.DataFrame
    next_cursor: str
    count: int
    limit: int


class OrdersCursorPage(CursorPage):
    """Active orders (CLOB ``/data/orders``)."""

    data: DataFrame[ActiveOrderSchema]  # type: ignore[misc]


class UserTradesCursorPage(CursorPage):
    """User trades (CLOB ``/data/trades``)."""

    data: DataFrame[ClobTradeSchema]  # type: ignore[misc]


class SamplingMarketsCursorPage(CursorPage):
    """Sampling markets (CLOB ``/sampling-markets``)."""

    data: DataFrame[SamplingMarketSchema]  # type: ignore[misc]


class SimplifiedMarketsCursorPage(CursorPage):
    """Simplified markets (CLOB ``/simplified-markets``)."""

    data: DataFrame[SimplifiedMarketSchema]  # type: ignore[misc]


class BuilderTradesCursorPage(CursorPage):
    """Builder trades (CLOB ``/builder/trades``)."""

    data: DataFrame[BuilderTradeSchema]  # type: ignore[misc]


class CurrentRewardsCursorPage(CursorPage):
    """Current reward configs (``/rewards/markets/current``)."""

    data: DataFrame[CurrentRewardSchema]  # type: ignore[misc]


class RewardsMarketMultiCursorPage(CursorPage):
    """Rewards markets multi (``/rewards/markets/multi``)."""

    data: DataFrame[RewardsMarketMultiSchema]  # type: ignore[misc]


class RewardsMarketCursorPage(CursorPage):
    """Rewards for a market (``/rewards/markets/{id}``)."""

    data: DataFrame[RewardsMarketSchema]  # type: ignore[misc]


class UserEarningsCursorPage(CursorPage):
    """User earnings (``/rewards/user``)."""

    data: DataFrame[UserEarningSchema]  # type: ignore[misc]


class UserRewardsMarketsCursorPage(CursorPage):
    """User reward markets (``/rewards/user/markets``)."""

    data: DataFrame[UserRewardsMarketSchema]  # type: ignore[misc]


class MarketsKeysetPage(TypedDict, total=False):
    """Keyset-paginated markets response (Gamma ``/markets/keyset``).

    ``next_cursor`` is omitted by the server on the final page.
    """

    data: DataFrame[MarketSchema]
    next_cursor: str


class EventsKeysetPage(TypedDict, total=False):
    """Keyset-paginated events response (Gamma ``/events/keyset``).

    ``next_cursor`` is omitted by the server on the final page.
    """

    data: DataFrame[EventSchema]
    next_cursor: str


# ── CTF transaction receipts ──────────────────────────────────────────
# Used by: approve_collateral, split_position, merge_positions,
# redeem_positions


class TransactionReceipt(TypedDict, total=False):
    """On-chain transaction receipt from CTF operations.

    ``blockNumber``, ``status``, and ``gasUsed`` are only present
    when ``wait=True``.
    """

    txHash: str
    blockNumber: int
    status: int
    gasUsed: int


class GasEstimate(TypedDict):
    """Gas cost estimate for a CTF transaction.

    Returned by CTF methods (``merge_positions``, ``split_position``,
    ``approve_collateral``, ``redeem_positions``) when called with
    ``estimate=True``.
    """

    gas: int
    gasPrice: int
    costWei: int
    costMatic: float
    eoaBalance: int


# ── CLOB API credentials ─────────────────────────────────────────────
# Used by: create_api_key, derive_api_key


class ApiCredentials(TypedDict):
    """API key credentials returned by key creation/derivation."""

    apiKey: str
    secret: str
    passphrase: str


# ── Balance / Allowance ──────────────────────────────────────────────
# Used by: get_balance_allowance


class BalanceAllowance(TypedDict):
    """Balance and allowance for a user's asset."""

    balance: str
    allowances: dict[str, str]


# ── Bridge addresses ─────────────────────────────────────────────────
# Used by: create_deposit_address, create_withdrawal_address


class BridgeAddressInfo(TypedDict):
    """Chain-specific deposit/withdrawal addresses."""

    evm: str
    svm: str
    btc: str


class BridgeAddress(TypedDict):
    """Bridge address response."""

    address: BridgeAddressInfo
    note: str


# ── Relayer ───────────────────────────────────────────────────────────
# Used by: get_relay_payload


class RelayPayload(TypedDict):
    """Relay payload with address and nonce."""

    address: str
    nonce: str


# Used by: submit_transaction


class SubmitTransactionResponse(TypedDict):
    """Response from submitting a relayer transaction."""

    transactionID: str
    transactionHash: str
    state: str


# ── Signed order ──────────────────────────────────────────────────────
# Used by: build_order


class SignedOrder(TypedDict, total=False):
    """EIP-712 signed CLOB V2 order dict (11 signed fields + signature).

    V1 fields ``taker``, ``nonce``, ``feeRateBps`` are removed.
    ``timestamp`` (ms) replaces ``nonce`` for uniqueness; ``metadata``
    and ``builder`` (both bytes32 hex) are added.

    ``expiration`` is V2 **wire-body only** — not part of the signed
    EIP-712 struct. Present for GTD orders, absent for GTC.
    """

    # Signed fields (always present)
    salt: int
    maker: str
    signer: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    side: str
    signatureType: int
    timestamp: str
    metadata: str
    builder: str
    signature: str
    # Optional wire-body fields
    expiration: str


# ── V2 CLOB market info ───────────────────────────────────────────────
# Used by: get_clob_market_info


class ClobMarketInfoFee(TypedDict, total=False):
    """Fee details inside ``ClobMarketInfo.fd`` (V2)."""

    r: float  # rate
    e: float  # exponent


class ClobMarketInfoToken(TypedDict):
    """Token entry inside ``ClobMarketInfo.t`` (V2)."""

    t: str  # tokenID
    o: str  # outcome


class ClobMarketInfo(TypedDict, total=False):
    """V2 ``GET /clob-markets/{conditionId}`` response (abbreviated keys).

    Confirmed keys (live response 2026-04-28): ``mts`` (min tick),
    ``mos`` (min order size), ``fd`` (fee details), ``t`` (tokens),
    plus several short-named auxiliary keys whose semantics are not yet
    documented (``aot``, ``r``, ``ao``, ``cbos``, ``ibce``, ``c``).
    All keys are optional in this TypedDict to allow forward compatibility.
    """

    mts: float  # minimum tick size
    mos: float  # minimum order size
    fd: ClobMarketInfoFee
    t: list[ClobMarketInfoToken]


# ── Order placement responses ─────────────────────────────────────────
# Used by: place_order, submit_order


class SendOrderResponse(TypedDict, total=False):
    """Response from placing a single order."""

    success: bool
    orderID: str
    status: str
    makingAmount: str
    takingAmount: str
    transactionsHashes: list[str]
    tradeIDs: list[str]
    errorMsg: str


# Used by: cancel_order, cancel_orders, cancel_all_orders,
# cancel_orders_from_market


class CancelOrdersResponse(TypedDict):
    """Response from cancelling orders."""

    canceled: list[str]
    not_canceled: dict[str, str]


# ── Last trade price ──────────────────────────────────────────────────
# Used by: get_last_trade_price


class LastTradePrice(TypedDict):
    """Last trade price for a single token."""

    price: str
    side: str


# ── xtracker single-resource responses ────────────────────────────────
# Used by: get_xtracker_user, get_xtracker_tracking


class XTrackerUser(TypedDict, total=False):
    """Single user response from ``GET xtracker.polymarket.com/api/users/{handle}``.

    Same shape as a row from ``get_xtracker_users``, plus a nested
    ``trackings`` list and a ``_count`` summary.
    """

    id: str
    handle: str
    name: str
    platform: str
    platformId: str
    avatarUrl: str
    bio: str
    verified: bool
    lastSync: pd.Timestamp
    createdAt: pd.Timestamp
    updatedAt: pd.Timestamp
    trackings: DataFrame[XTrackerTrackingSchema]


class XTrackerTracking(TypedDict, total=False):
    """Single tracking response from ``GET xtracker.polymarket.com/api/trackings/{id}``.

    When ``include_stats=True``, the ``stats`` field is materialised as a
    DataFrame of the daily counter (one row per bucket) with the
    aggregate ``total`` / ``cumulative`` / ``pace`` / ``percentComplete`` /
    ``daysElapsed`` / ``daysRemaining`` / ``daysTotal`` / ``isComplete``
    fields exposed via ``stats.attrs``.
    """

    id: str
    userId: str
    title: str
    startDate: pd.Timestamp
    endDate: pd.Timestamp
    target: int
    marketLink: str
    isActive: bool
    createdAt: pd.Timestamp
    updatedAt: pd.Timestamp
    stats: DataFrame[XTrackerDailyStatSchema]


# ── UMA resolution ───────────────────────────────────────────────────
# Used by: get_uma_question, get_oo_request


class UmaQuestion(TypedDict):
    """UMA CTF Adapter stored metadata for a single question."""

    requestTimestamp: int
    reward: int
    proposalBond: int
    liveness: int
    emergencyResolutionTimestamp: int
    resolved: bool
    paused: bool
    reset: bool
    refund: bool
    rewardToken: str
    creator: str
    ancillaryData: bytes


class OptimisticOracleRequest(TypedDict):
    """UMA OptimisticOracleV2 ``Request`` state for a question."""

    proposer: str
    disputer: str
    currency: str
    settled: bool
    bond: int
    customLiveness: int
    proposedPrice: int
    resolvedPrice: int
    expirationTime: int
    reward: int
    finalFee: int


__all__ = [
    "ApiCredentials",
    "BalanceAllowance",
    "BridgeAddress",
    "BridgeAddressInfo",
    "BuilderTradesCursorPage",
    "CancelOrdersResponse",
    "ClobMarketInfo",
    "ClobMarketInfoFee",
    "ClobMarketInfoToken",
    "CurrentRewardsCursorPage",
    "CursorPage",
    "EventsKeysetPage",
    "LastTradePrice",
    "MarketsKeysetPage",
    "OrdersCursorPage",
    "RelayPayload",
    "RewardsMarketCursorPage",
    "RewardsMarketMultiCursorPage",
    "SamplingMarketsCursorPage",
    "SendOrderResponse",
    "SignedOrder",
    "SimplifiedMarketsCursorPage",
    "SubmitTransactionResponse",
    "OptimisticOracleRequest",
    "TransactionReceipt",
    "UmaQuestion",
    "UserEarningsCursorPage",
    "UserRewardsMarketsCursorPage",
    "UserTradesCursorPage",
    "XTrackerTracking",
    "XTrackerUser",
]
