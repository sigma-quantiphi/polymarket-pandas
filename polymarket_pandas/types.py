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
    RewardsMarketMultiSchema,
    RewardsMarketSchema,
    SamplingMarketSchema,
    SimplifiedMarketSchema,
    UserEarningSchema,
    UserRewardsMarketSchema,
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


class SignedOrder(TypedDict):
    """EIP-712 signed CLOB order dict."""

    salt: int
    maker: str
    signer: str
    taker: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    expiration: str
    nonce: str
    feeRateBps: str
    side: str
    signatureType: int
    signature: str


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


__all__ = [
    "ApiCredentials",
    "BalanceAllowance",
    "BridgeAddress",
    "BridgeAddressInfo",
    "BuilderTradesCursorPage",
    "CancelOrdersResponse",
    "CurrentRewardsCursorPage",
    "CursorPage",
    "LastTradePrice",
    "OrdersCursorPage",
    "RelayPayload",
    "RewardsMarketCursorPage",
    "RewardsMarketMultiCursorPage",
    "SamplingMarketsCursorPage",
    "SendOrderResponse",
    "SignedOrder",
    "SimplifiedMarketsCursorPage",
    "SubmitTransactionResponse",
    "TransactionReceipt",
    "UserEarningsCursorPage",
    "UserRewardsMarketsCursorPage",
    "UserTradesCursorPage",
]
