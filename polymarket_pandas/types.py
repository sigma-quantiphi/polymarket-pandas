"""TypedDict models for dict-returning endpoints.

These are structural subtypes of ``dict`` — existing code using
``result["key"]`` or ``result.get("key")`` continues to work unchanged.
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd
import pandera.pandas as pa

from polymarket_pandas.schemas import ActiveOrderSchema, ClobTradeSchema

# ── Cursor-paginated responses ────────────────────────────────────────
# Used by: get_sampling_markets, get_simplified_markets,
# get_sampling_simplified_markets, get_builder_trades,
# get_rewards_markets_current, get_rewards_markets_multi,
# get_rewards_market, get_rewards_earnings, get_rewards_user_markets


class CursorPage(TypedDict):
    """Cursor-paginated response wrapper (generic)."""

    data: pd.DataFrame
    next_cursor: str
    count: int
    limit: int


# ── Typed cursor-paginated responses ─────────────────────────────────
# Used by: get_active_orders


class OrdersCursorPage(TypedDict):
    """Cursor-paginated response for active orders.

    ``data`` is a DataFrame conforming to :class:`ActiveOrderSchema`.
    """

    data: pa.DataFrame[ActiveOrderSchema]
    next_cursor: str
    count: int
    limit: int


# Used by: get_user_trades


class UserTradesCursorPage(TypedDict):
    """Cursor-paginated response for user trades.

    ``data`` is a DataFrame conforming to :class:`ClobTradeSchema`.
    """

    data: pa.DataFrame[ClobTradeSchema]
    next_cursor: str
    count: int
    limit: int


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
    "CancelOrdersResponse",
    "CursorPage",
    "LastTradePrice",
    "OrdersCursorPage",
    "RelayPayload",
    "SendOrderResponse",
    "SignedOrder",
    "SubmitTransactionResponse",
    "TransactionReceipt",
    "UserTradesCursorPage",
]
