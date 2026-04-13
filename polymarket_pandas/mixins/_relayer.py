"""Relayer API endpoints mixin."""

from __future__ import annotations

import pandas as pd

from polymarket_pandas.types import RelayPayload, SubmitTransactionResponse


class RelayerMixin:
    # ── Relayer API Keys ─────────────────────────────────────────────────

    def get_relayer_api_keys(self) -> pd.DataFrame:
        """
        Get all relayer API keys for the authenticated account.

        Requires ``POLYMARKET_RELAYER_API_KEY`` and
        ``POLYMARKET_RELAYER_API_KEY_ADDRESS`` to be set.

        Returns:
            pd.DataFrame: Rows with columns ``apiKey``, ``address``,
            ``createdAt``, ``updatedAt``.
        """
        data = self._request_relayer("relayer/api/keys", auth_headers=self._relayer_auth_headers())
        return self.response_to_dataframe(data)

    # ── Relayer API ──────────────────────────────────────────────────────

    def check_safe_deployed(self, address: str) -> bool:
        """
        Check whether a Safe smart wallet is deployed for a given address.

        Args:
            address: User's Polymarket proxy address (``0x``-prefixed).

        Returns:
            bool: ``True`` if the Safe is deployed.
        """
        data = self._request_relayer("deployed", params={"address": address})
        return bool(self._extract(data, "deployed"))

    def get_relayer_transaction(self, id: str) -> list[dict]:
        """
        Get a relayer transaction by its ID.

        Args:
            id: Transaction ID (UUID string).

        Returns:
            list[dict]: Transaction records.
        """
        return self._request_relayer("transaction", params={"id": id})

    def get_relayer_nonce(self, address: str, type: str) -> str:
        """
        Get the current nonce for a user's Safe or Proxy wallet.

        Args:
            address: User's signer address (``0x``-prefixed).
            type: ``"PROXY"`` or ``"SAFE"``.

        Returns:
            str: The current nonce as a string.
        """
        data = self._request_relayer("nonce", params={"address": address, "type": type})
        return self._extract(data, "nonce")

    def get_relayer_transactions(self) -> pd.DataFrame:
        """
        Get recent relayer transactions for the authenticated account.

        Requires ``POLYMARKET_RELAYER_API_KEY`` and
        ``POLYMARKET_RELAYER_API_KEY_ADDRESS`` to be set.
        """
        data = self._request_relayer("transactions", auth_headers=self._relayer_auth_headers())
        return self.response_to_dataframe(data)

    def get_relay_payload(self, address: str, type: str) -> RelayPayload:
        """
        Get the relayer address and current nonce needed to construct a relayed
        transaction.

        Args:
            address: User's signer address (``0x``-prefixed).
            type: ``"PROXY"`` or ``"SAFE"``.

        Returns:
            dict: ``{"address": str, "nonce": str}``.
        """
        return self._request_relayer("relay-payload", params={"address": address, "type": type})

    def submit_transaction(
        self,
        from_: str,
        to: str,
        proxy_wallet: str,
        data: str,
        nonce: str,
        signature: str,
        type: str,
        signature_params: dict,
    ) -> SubmitTransactionResponse:
        """
        Submit a transaction to the Polymarket relayer.

        Requires ``POLYMARKET_RELAYER_API_KEY`` and
        ``POLYMARKET_RELAYER_API_KEY_ADDRESS`` to be set.

        Args:
            from_: Signer address (``0x``-prefixed).
            to: Target contract address (``0x``-prefixed).
            proxy_wallet: User's Polymarket proxy wallet address.
            data: Encoded transaction data (``0x``-prefixed hex string).
            nonce: Transaction nonce (string).
            signature: Transaction signature (``0x``-prefixed hex string).
            type: ``"PROXY"`` or ``"SAFE"``.
            signature_params: Dict with keys ``gasPrice``, ``operation``,
                ``safeTxnGas``, ``baseGas``, ``gasToken``, ``refundReceiver``.

        Returns:
            dict: ``{"transactionID": str, "transactionHash": str, "state": str}``.
        """
        body = {
            "from": from_,
            "to": to,
            "proxyWallet": proxy_wallet,
            "data": data,
            "nonce": nonce,
            "signature": signature,
            "type": type,
            "signatureParams": signature_params,
        }
        # Prefer builder HMAC auth (required for PROXY type relay
        # coordination); fall back to relayer API key auth.
        if self._has_builder_creds():
            headers = self._build_builder_headers(
                method="POST", request_path="/submit", body=body
            )
        else:
            headers = self._relayer_auth_headers()
        return self._request_relayer(
            "submit",
            method="POST",
            data=body,
            auth_headers=headers,
        )
