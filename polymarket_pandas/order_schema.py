"""Pandera DataFrameModel for validating EIP-712 CLOB order DataFrames."""

import pandera.pandas as pa


class OrderSchema(pa.DataFrameModel):
    """Base schema for orders (general for any exchange)."""

    salt: int = pa.Field(ge=0, description="Random salt used to create unique order")
    maker: str = pa.Field(description="Maker address (funder)")
    signer: str = pa.Field(description="Signer address")
    taker: str = pa.Field(description="Taker address (operator)")
    tokenId: str = pa.Field(description="ERC1155 token ID of conditional token being traded")
    makerAmount: str = pa.Field(description="Maximum amount maker is willing to spend")
    takerAmount: str = pa.Field(description="Minimum amount taker will pay the maker in return")
    expiration: str = pa.Field(description="Unix expiration timestamp")
    nonce: str = pa.Field(description="Maker’s exchange nonce of the order is associated")
    feeRateBps: str = pa.Field(description="Fee rate basis points as required by the operator")
    side: str = pa.Field(isin=["BUY", "SELL"], description="Buy or sell enum index")
    signatureType: int = pa.Field(ge=0, description="Signature type enum index")
    signature: str = pa.Field(description="Hex encoded signature")

    @classmethod
    def validate_price_for_limit_orders(cls, df):
        """Raise ValueError if any non-market order is missing a price."""
        limit_orders = df.query("type != 'market'")
        if limit_orders["price"].isnull().any():
            raise ValueError("Non market orders must include a price.")
