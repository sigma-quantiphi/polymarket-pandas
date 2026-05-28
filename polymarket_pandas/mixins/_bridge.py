"""Bridge API endpoints mixin."""

from __future__ import annotations

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import (
    BridgeSupportedAssetSchema,
    BridgeTransactionSchema,
)
from polymarket_pandas.types import BridgeAddress


class BridgeMixin:
    # ── Bridge API ───────────────────────────────────────────────────────

    def create_deposit_address(self, address: str) -> BridgeAddress:
        """
        Create deposit addresses for bridging funds into a Polymarket wallet.

        Args:
            address: Polymarket wallet address (``0x``-prefixed) where USDC.e
                will be credited after bridging.

        Returns:
            dict: ``{"address": {"evm": str, "svm": str, "btc": str}, "note": str}``.
        """
        return self._request_bridge("deposit", method="POST", data={"address": address})

    def withdraw(
        self,
        address: str,
        to_chain_id: str,
        to_token_address: str,
        recipient_addr: str,
    ) -> BridgeAddress:
        """Initiate a Polymarket → multi-chain withdrawal.

        POSTs to ``/withdraw`` to register the destination and obtain
        bridge addresses (EVM / SVM / BTC). To actually move funds, the
        user transfers **pUSD** from their Polymarket wallet on Polygon
        to the returned bridge address; the bridge then auto-swaps to
        the requested ``to_token_address`` on ``to_chain_id`` and
        forwards to ``recipient_addr``.

        Polymarket recommends the following end-to-end flow:

        1. ``get_bridge_supported_assets`` — confirm the destination is supported.
        2. ``get_bridge_quote`` — preview fees and output amount.
        3. ``withdraw`` (this method) — register the destination, get bridge addresses.
        4. Transfer pUSD to the returned ``evm``/``svm``/``btc`` address.
        5. ``get_bridge_transaction_status`` — poll until ``status == "completed"``.

        Per Polymarket docs: do not pre-generate withdrawal addresses;
        only call this when you are ready to transfer.

        Args:
            address: Source Polymarket wallet on Polygon (``0x``-prefixed).
            to_chain_id: Destination chain ID as a string. Common values:
                ``"1"`` = Ethereum, ``"8453"`` = Base, ``"42161"`` = Arbitrum,
                ``"1151111081099710"`` = Solana, ``"20000000000001"`` = Bitcoin.
            to_token_address: Destination token contract address on
                ``to_chain_id``.
            recipient_addr: Destination wallet address (EVM hex, Solana
                base58, or Bitcoin address as appropriate for the chain).

        Returns:
            ``BridgeAddress`` — ``{"address": {"evm": str, "svm": str,
            "btc": str}, "note": str}``. Transfer pUSD to the address
            matching your destination chain family.

        See:
            https://docs.polymarket.com/api-reference/bridge/create-withdrawal-addresses
        """
        return self._request_bridge(
            "withdraw",
            method="POST",
            data={
                "address": address,
                "toChainId": to_chain_id,
                "toTokenAddress": to_token_address,
                "recipientAddr": recipient_addr,
            },
        )

    # Backwards-compat alias (pre-v0.13.2 name). Prefer ``withdraw``.
    create_withdrawal_address = withdraw

    def get_bridge_quote(
        self,
        from_amount_base_unit: str,
        from_chain_id: str,
        from_token_address: str,
        recipient_address: str,
        to_chain_id: str,
        to_token_address: str,
    ) -> dict:
        """
        Get a price quote for a bridge transaction.
        """
        return self._request_bridge(
            "quote",
            method="POST",
            data={
                "fromAmountBaseUnit": from_amount_base_unit,
                "fromChainId": from_chain_id,
                "fromTokenAddress": from_token_address,
                "recipientAddress": recipient_address,
                "toChainId": to_chain_id,
                "toTokenAddress": to_token_address,
            },
        )

    def get_bridge_supported_assets(self) -> DataFrame[BridgeSupportedAssetSchema]:
        """
        Get the list of chains and tokens supported by the Polymarket bridge.

        The nested ``token`` object is flattened into ``tokenName``,
        ``tokenSymbol``, ``tokenAddress``, and ``tokenDecimals`` columns.

        Returns:
            pd.DataFrame: One row per chain/token combination.
        """
        data = self._request_bridge("supported-assets")
        assets = data.get("supportedAssets", data)
        df = pd.json_normalize(assets, sep="_")
        return self.preprocess_dataframe(df)

    def get_bridge_transaction_status(self, address: str) -> DataFrame[BridgeTransactionSchema]:
        """
        Get the status of bridge transactions associated with a deposit or
        withdrawal address.

        Args:
            address: The EVM, SVM, or BTC address returned by
                :meth:`create_deposit_address` or :meth:`create_withdrawal_address`.

        Returns:
            pd.DataFrame: Transaction rows with columns ``fromChainId``,
            ``fromTokenAddress``, ``fromAmountBaseUnit``, ``toChainId``,
            ``toTokenAddress``, ``status``, ``txHash``, ``createdTimeMs``.
        """
        data = self._request_bridge(f"status/{address}")
        return self.response_to_dataframe(data.get("transactions", []))
