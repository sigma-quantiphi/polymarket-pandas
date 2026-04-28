"""Pandera DataFrameModel schemas for validating order input DataFrames.

``PlaceOrderSchema`` validates signed-order DataFrames passed to
:meth:`~polymarket_pandas.PolymarketPandas.place_orders`.

``SubmitOrderSchema`` validates unsigned-intent DataFrames passed to
:meth:`~polymarket_pandas.PolymarketPandas.submit_orders`.
"""

from __future__ import annotations

import pandera.pandas as pa


class PlaceOrderSchema(pa.DataFrameModel):
    """Schema for signed-V2-order DataFrames submitted to ``place_orders``.

    Field constraints mirror the V2 CLOB ``POST /orders`` request body
    (signed order: 11 fields + signature). ``nonce``, ``feeRateBps``,
    ``taker``, and ``expiration`` were removed in V2.
    """

    # ── Signed order fields (from build_order / V2 API spec) ───────────
    salt: int = pa.Field(ge=0, description="Random salt for order uniqueness")
    maker: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{40}$",
        description="Maker (funder) Ethereum address",
    )
    signer: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{40}$",
        description="Signer Ethereum address",
    )
    tokenId: str = pa.Field(str_length={"min_value": 1}, description="ERC-1155 token ID")
    makerAmount: str = pa.Field(
        str_matches=r"^\d+$",
        description="Maker amount in fixed-math (6 decimals)",
    )
    takerAmount: str = pa.Field(
        str_matches=r"^\d+$",
        description="Taker amount in fixed-math (6 decimals)",
    )
    side: str = pa.Field(isin=["BUY", "SELL"], description="Order side")
    signatureType: int = pa.Field(isin=[0, 1, 2], description="Signature type enum")
    timestamp: str = pa.Field(
        str_matches=r"^\d+$",
        description="Order creation time in milliseconds (replaces V1 nonce)",
    )
    metadata: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{64}$",
        description="bytes32 hex string (zero by default)",
    )
    builder: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{64}$",
        description="bytes32 builder code (zero by default)",
    )
    signature: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]+$",
        description="EIP-712 hex signature",
    )
    # ``expiration`` is V2 wire-body-only (NOT part of the signed struct).
    # Optional — present for GTD orders, absent for GTC.
    expiration: str | None = pa.Field(
        nullable=True,
        str_matches=r"^\d+$",
        description="Optional GTD expiry (Unix seconds, wire-body only)",
    )

    # ── Envelope fields added by submit_orders / build_and_submit ──────
    owner: str = pa.Field(description="API key of the order owner")
    orderType: str = pa.Field(
        isin=["FOK", "GTC", "GTD", "FAK"],
        description="Order time-in-force type",
    )
    postOnly: bool | None = pa.Field(
        nullable=True,
        description="If True, reject order if it would immediately match (GTC/GTD only)",
    )

    class Config:
        strict = False
        coerce = True


class SubmitOrderSchema(pa.DataFrameModel):
    """Schema for unsigned-intent DataFrames submitted to ``submit_orders``.

    Required columns: ``token_id``, ``price``, ``size``, ``side``.
    Optional columns are nullable.
    """

    tokenId: str = pa.Field(str_length={"min_value": 1}, description="CLOB token ID")
    price: float = pa.Field(gt=0, le=1, description="Limit price (0, 1]")
    size: float = pa.Field(gt=0, description="Order size in shares")
    side: str = pa.Field(isin=["BUY", "SELL"], description="Order side")

    # ── Optional columns ───────────────────────────────────────────────
    postOnly: bool | None = pa.Field(
        nullable=True,
        description="If True, reject order if it would immediately match (GTC/GTD only)",
    )
    orderType: str | None = pa.Field(
        isin=["FOK", "GTC", "GTD", "FAK"],
        nullable=True,
        description="Time-in-force (default GTC)",
    )
    negRisk: object | None = pa.Field(nullable=True, description="Neg-risk flag")
    tickSize: float | None = pa.Field(nullable=True, gt=0, description="Tick size override")
    builderCode: object | None = pa.Field(
        nullable=True,
        description="Per-order V2 builder code (bytes32 hex)",
    )
    expiration: object | None = pa.Field(
        nullable=True,
        description="GTD expiration (int Unix seconds / ISO string / Timestamp)",
    )

    class Config:
        strict = False
        coerce = True


# Keep backward compat alias
OrderSchema = PlaceOrderSchema

__all__ = ["OrderSchema", "PlaceOrderSchema", "SubmitOrderSchema"]
