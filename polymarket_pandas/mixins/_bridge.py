"""Bridge API endpoints mixin."""
from __future__ import annotations

import pandas as pd


class BridgeMixin:
    # ── Bridge API ───────────────────────────────────────────────────────

    def create_deposit_address(self, address: str) -> dict:
        """
        Create deposit addresses for bridging funds into a Polymarket wallet.

        Args:
            address: Polymarket wallet address (``0x``-prefixed) where USDC.e
                will be credited after bridging.

        Returns:
            dict: ``{"address": {"evm": str, "svm": str, "btc": str}, "note": str}``.
        """
        return self._request_bridge("deposit", method="POST", data={"address": address})

    def create_withdrawal_address(
        self,
        address: str,
        to_chain_id: str,
        to_token_address: str,
        recipient_addr: str,
    ) -> dict:
        """
        Create withdrawal addresses for bridging funds out of a Polymarket wallet.

        Args:
            address: Source Polymarket wallet on Polygon (``0x``-prefixed).
            to_chain_id: Destination chain ID (e.g. ``"1"`` = Ethereum,
                ``"8453"`` = Base, ``"1151111081099710"`` = Solana).
            to_token_address: Destination token contract address.
            recipient_addr: Destination wallet address on the target chain.

        Returns:
            dict: ``{"address": {"evm": str, "svm": str, "btc": str}, "note": str}``.
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

    def get_bridge_supported_assets(self) -> list[dict]:
        """
        Get the list of chains and tokens supported by the Polymarket bridge.
        """
        data = self._request_bridge("supported-assets")
        return data.get("supportedAssets", data)

    def get_bridge_transaction_status(self, address: str) -> pd.DataFrame:
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
