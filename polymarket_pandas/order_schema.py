"""Pandera DataFrameModel schemas for validating order input DataFrames.

``PlaceOrderSchema`` validates signed-order DataFrames passed to
:meth:`~polymarket_pandas.PolymarketPandas.place_orders`.

``SubmitOrderSchema`` validates unsigned-intent DataFrames passed to
:meth:`~polymarket_pandas.PolymarketPandas.submit_orders`.
"""

from __future__ import annotations

import pandera.pandas as pa


class PlaceOrderSchema(pa.DataFrameModel):
    """Schema for signed-order DataFrames submitted to ``place_orders``.

    Field constraints mirror the CLOB ``POST /orders`` request body.
    """

    # ── Signed order fields (from build_order / API spec) ──────────────
    salt: int = pa.Field(ge=0, description="Random salt for order uniqueness")
    maker: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{40}$",
        description="Maker (funder) Ethereum address",
    )
    signer: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{40}$",
        description="Signer Ethereum address",
    )
    taker: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]{40}$",
        description="Taker Ethereum address (0x0…0 for open orders)",
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
    expiration: str = pa.Field(
        str_matches=r"^\d+$",
        description="Unix expiration timestamp (0 = GTC)",
    )
    nonce: str = pa.Field(str_matches=r"^\d+$", description="Maker nonce")
    feeRateBps: str = pa.Field(
        str_matches=r"^\d+$",
        description="Fee rate in basis points",
    )
    signature: str = pa.Field(
        str_matches=r"^0x[0-9a-fA-F]+$",
        description="EIP-712 hex signature",
    )
    signatureType: int = pa.Field(isin=[0, 1, 2], description="Signature type enum")

    # ── Envelope fields added by submit_orders / build_and_submit ──────
    owner: str = pa.Field(description="API key of the order owner")
    orderType: str = pa.Field(
        isin=["FOK", "GTC", "GTD"],
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
        isin=["FOK", "GTC", "GTD"],
        nullable=True,
        description="Time-in-force (default GTC)",
    )
    expiration: object | None = pa.Field(nullable=True, description="Expiry (int/str/Timestamp)")
    nonce: object | None = pa.Field(nullable=True, description="Order nonce")
    negRisk: object | None = pa.Field(nullable=True, description="Neg-risk flag")
    tickSize: float | None = pa.Field(nullable=True, gt=0, description="Tick size override")
    feeRateBps: object | None = pa.Field(nullable=True, description="Fee rate bps override")

    class Config:
        strict = False
        coerce = True


# Keep backward compat alias
OrderSchema = PlaceOrderSchema

__all__ = ["OrderSchema", "PlaceOrderSchema", "SubmitOrderSchema"]
