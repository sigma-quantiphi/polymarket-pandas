"""CLOB private API endpoints mixin (L2 auth required)."""

from __future__ import annotations

import pandas as pd
from pandas import DataFrame


class ClobPrivateMixin:
    # ── CLOB API: Private ────────────────────────────────────────────────

    def get_balance_allowance(
        self,
        asset_type: int,
        token_id: str | None = None,
    ) -> dict:
        """
        Get balance and allowance for the authenticated user (L2 auth).

        Args:
            asset_type (int): Asset type — 0 for COLLATERAL (USDC), 1 for CONDITIONAL token.
            token_id (str | None): Required when asset_type=1.

        Returns:
            dict: Balance and allowance details.
        """
        return self._request_clob_private(
            path="balance-allowance",
            params={"asset_type": asset_type, "token_id": token_id},
        )

    def get_user_trades(
        self,
        id: str | None = None,
        taker: str | None = None,
        maker: str | None = None,
        market: str | None = None,
        before: str | None = None,
        after: str | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve trades for the authenticated user based on provided filters.
        """
        data = self._request_clob_private(
            path="data/trades",
            params={
                "id": id,
                "taker": taker,
                "maker": maker,
                "market": market,
                "before": before,
                "after": after,
            },
        )
        return self.response_to_dataframe(data["data"])

    def get_order(self, order_id: str) -> dict:
        """
        Get information about an existing order.

        Args:
            order_id (str): ID of the order to retrieve.

        Returns:
            dict: A dictionary containing the order information.
        """
        return self._request_clob_private(path=f"data/order/{order_id}")

    def get_active_orders(
        self,
        id: str | None = None,
        market: str | None = None,
        asset_id: str | None = None,
    ) -> pd.DataFrame:
        """
        Get active orders for a specific market, asset, or order ID.
        """
        data = self._request_clob_private(
            path="data/orders",
            params={
                "id": id,
                "market": market,
                "asset_id": asset_id,
            },
        )
        return self.response_to_dataframe(data)

    def get_order_scoring(self, order_id: str) -> bool:
        """Check whether an order is being scored for rewards.

        https://docs.polymarket.com/api-reference/clob/get-order-scoring

        Args:
            order_id: The order ID to check.

        Returns:
            True if the order is being scored, False otherwise.
        """
        data = self._request_clob_private(path="order-scoring", params={"order_id": order_id})
        return bool(self._extract(data, "scoring"))

    def place_order(self, order: dict, owner: str, orderType: str) -> dict:
        """
        Create and place an order using the Polymarket CLOB API.

        Args:
            order (dict): The signed order object.
            owner (str): API key of the order owner.
            orderType (str): The order type, e.g., "FOK", "GTC", "GTD".

        Returns:
            dict: Response from the API.
        """
        return self._request_clob_private(
            path="order",
            method="POST",
            data={"order": order, "owner": owner, "orderType": orderType},
        )

    def place_orders(self, orders: pd.DataFrame) -> DataFrame:
        """
        Place multiple orders in a batch (up to 15 orders).
        """
        orders_data = []
        data = orders.copy()
        data["expiration"] = data["expiration"].astype(int)
        for [owner, orderType], sub_orders in data.groupby(["owner", "orderType"]):
            for x in sub_orders.to_dict("records"):
                order = {
                    "order": x,
                    "owner": owner,
                    "orderType": orderType,
                }
                orders_data.append(order.copy())
        response = self._request_clob_private(
            path="orders",
            method="POST",
            data=orders_data,
        )
        return self.response_to_dataframe(response)

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a single order."""
        return self._request_clob_private(
            path="order",
            method="DELETE",
            data={"orderID": order_id},
        )

    def cancel_orders(self, order_ids: list[str]) -> dict:
        """Cancel multiple orders."""
        return self._request_clob_private(
            path="orders",
            method="DELETE",
            data=order_ids,
        )

    def cancel_all_orders(self) -> dict:
        """Cancel all orders."""
        return self._request_clob_private(path="cancel-all", method="DELETE")

    def cancel_orders_from_market(
        self, market: str | None = None, asset_id: str | None = None
    ) -> dict:
        """Cancel orders from a specific market or asset."""
        return self._request_clob_private(
            path="cancel-market-orders",
            method="DELETE",
            params={
                "market": market,
                "asset_id": asset_id,
            },
        )

    def send_heartbeat(self) -> dict:
        """Send a heartbeat to keep open orders alive.

        https://docs.polymarket.com/api-reference/clob/post-heartbeat
        """
        return self._request_clob_private(path="heartbeats", method="POST")

    # ── CLOB API: API Keys ───────────────────────────────────────────────

    def create_api_key(self, nonce: int = 0) -> dict:
        """
        Create a new API key using an L1 (EIP-712) signature.

        Args:
            nonce (int): Nonce value for the signature. Default is 0.

        Returns:
            dict: The created API key credentials (apiKey, secret, passphrase).
        """
        headers = self._build_l1_headers(nonce=nonce)
        response = self._client.post(f"{self.clob_url}auth/api-key", headers=headers)
        response.raise_for_status()
        return response.json()

    def derive_api_key(self, nonce: int = 0) -> dict:
        """
        Derive an existing API key using an L1 (EIP-712) signature.

        Args:
            nonce (int): Nonce value for the signature. Default is 0.

        Returns:
            dict: The derived API key credentials (apiKey, secret, passphrase).
        """
        headers = self._build_l1_headers(nonce=nonce)
        response = self._client.get(f"{self.clob_url}auth/derive-api-key", headers=headers)
        response.raise_for_status()
        return response.json()

    def get_api_keys(self) -> pd.DataFrame:
        """Get all API keys for the authenticated user (L2 auth)."""
        data = self._request_clob_private(path="auth/api-key")
        return self.response_to_dataframe(data)

    def delete_api_key(self) -> dict:
        """Delete the current API key (L2 auth)."""
        return self._request_clob_private(path="auth/api-key", method="DELETE")
