"""CLOB private API endpoints mixin (L2 auth required)."""

from __future__ import annotations

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import SendOrderResponseSchema
from polymarket_pandas.types import (
    ApiCredentials,
    BalanceAllowance,
    CancelOrdersResponse,
    OrdersCursorPage,
    SendOrderResponse,
    UserTradesCursorPage,
)

# Polymarket CLOB server expects string enums, not integers.
_ASSET_TYPE_ENUMS = {0: "COLLATERAL", 1: "CONDITIONAL"}


class ClobPrivateMixin:
    # ── CLOB API: Private ────────────────────────────────────────────────

    def get_balance_allowance(
        self,
        asset_type: int | str,
        token_id: str | None = None,
    ) -> BalanceAllowance:
        """Get balance and allowance for the authenticated user (L2 auth).

        Args:
            asset_type: ``"COLLATERAL"`` (USDC.e) or ``"CONDITIONAL"`` (outcome
                token). The integer shortcuts ``0`` and ``1`` are accepted and
                mapped to the enum values the CLOB server expects.
            token_id: Required when ``asset_type`` is ``"CONDITIONAL"``.

        Returns:
            dict with ``balance`` and ``allowances``.

        For proxy wallets (``signature_type=1`` or ``2``), the server looks
        up the proxy's USDC balance rather than the EOA's when
        ``signatureType`` is in the query. This method auto-attaches that
        param when a non-default ``signature_type`` is configured on the
        client, so proxy users see their real trading balance without
        having to touch internals.
        """
        if isinstance(asset_type, int):
            asset_type = _ASSET_TYPE_ENUMS[asset_type]
        params: dict = {"asset_type": asset_type, "token_id": token_id}
        if self.signature_type is not None:
            params["signatureType"] = self.signature_type
        return self._request_clob_private(path="balance-allowance", params=params)

    def get_user_trades(
        self,
        id: str | None = None,
        taker: str | None = None,
        maker: str | None = None,
        market: str | None = None,
        before: str | pd.Timestamp | None = None,
        after: str | pd.Timestamp | None = None,
        next_cursor: str | None = None,
    ) -> UserTradesCursorPage:
        """Retrieve trades for the authenticated user based on provided filters.

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed trade rows
            - ``next_cursor`` (str): pass to the next call to page forward;
              ``"LTE="`` means the last page has been reached
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Args:
            id: Trade ID filter.
            taker: Taker address filter.
            maker: Maker address filter.
            market: Market condition ID.
            before: Return trades before this value. Accepts a Unix
                timestamp string or ``pd.Timestamp``.
            after: Return trades after this value. Accepts a Unix
                timestamp string or ``pd.Timestamp``.
            next_cursor: Opaque base64 cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob_private(
            path="data/trades",
            params={
                "id": id,
                "taker": taker,
                "maker": maker,
                "market": market,
                "before": before,
                "after": after,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

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
        next_cursor: str | None = None,
    ) -> OrdersCursorPage:
        """Get active orders for a specific market, asset, or order ID.

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed order rows
            - ``next_cursor`` (str): pass to the next call to page forward;
              ``"LTE="`` means the last page has been reached
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Args:
            id: Order ID filter.
            market: Market condition ID.
            asset_id: CLOB token ID.
            next_cursor: Opaque base64 cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob_private(
            path="data/orders",
            params={
                "id": id,
                "market": market,
                "asset_id": asset_id,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

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

    def place_order(
        self,
        order: dict,
        owner: str,
        orderType: str,
        post_only: bool = False,
        defer_exec: bool = False,
    ) -> SendOrderResponse:
        """
        Create and place an order using the Polymarket CLOB V2 API.

        Args:
            order (dict): The signed order object.
            owner (str): API key of the order owner.
            orderType (str): Time-in-force — ``"GTC"``, ``"GTD"``, ``"FOK"``,
                or ``"FAK"`` (V2: fill-and-kill, distinct from FOK).
            post_only: If True, reject the order if it would immediately
                match (maker-only). Only valid with GTC/GTD.
            defer_exec: V2 envelope flag — deferred execution hint to the
                matching engine. Defaults to ``False``.

        Returns:
            dict: Response from the API.

        Note:
            V2: ``POLY_BUILDER_*`` HMAC attribution headers are no longer
            attached. Builder attribution is per-order via the signed
            ``builder`` (bytes32) field — set ``builder_code`` on the
            client or pass it through :meth:`build_order`.
        """
        if post_only and orderType not in ("GTC", "GTD"):
            raise ValueError(f"post_only is only valid with GTC or GTD, got {orderType!r}")
        data: dict = {"order": order, "owner": owner, "orderType": orderType}
        if post_only:
            data["postOnly"] = True
        if defer_exec:
            data["deferExec"] = True
        return self._request_clob_private(
            path="order",
            method="POST",
            data=data,
        )

    def place_orders(self, orders: pd.DataFrame) -> DataFrame[SendOrderResponseSchema]:
        """Place multiple signed orders in a batch (up to 15 per call).

        The DataFrame must contain signed order fields (from
        :meth:`~polymarket_pandas.PolymarketPandas.build_order`) plus
        ``owner`` and ``orderType`` columns.

        Args:
            orders: DataFrame of signed orders.

        Returns:
            pd.DataFrame: API responses.

        Raises:
            pandera.errors.SchemaError: If the DataFrame fails validation.
            ValueError: If more than 15 orders are provided.

        Note:
            V2: ``POLY_BUILDER_*`` HMAC attribution headers are no longer
            attached. Builder attribution is per-order via the signed
            ``builder`` (bytes32) field. Use :meth:`submit_orders` (which
            wraps :meth:`build_order`) to thread ``builder_code`` through
            from the input intent DataFrame's ``builderCode`` column.
        """
        from polymarket_pandas.order_schema import PlaceOrderSchema

        if len(orders) > 15:
            raise ValueError(f"CLOB API accepts at most 15 orders per call, got {len(orders)}")
        PlaceOrderSchema.validate(orders)
        envelope_cols = {"owner", "orderType", "postOnly", "deferExec"}
        order_cols = [c for c in orders.columns if c not in envelope_cols]
        has_post_only = "postOnly" in orders.columns
        has_defer_exec = "deferExec" in orders.columns
        orders_data = []
        for row in orders.itertuples(index=False):
            order_dict = {c: getattr(row, c) for c in order_cols}
            entry: dict = {
                "order": order_dict,
                "owner": row.owner,
                "orderType": row.orderType,
            }
            if has_post_only and getattr(row, "postOnly", False):
                if row.orderType not in ("GTC", "GTD"):
                    raise ValueError(
                        f"postOnly is only valid with GTC or GTD, got {row.orderType!r}"
                    )
                entry["postOnly"] = True
            if has_defer_exec and getattr(row, "deferExec", False):
                entry["deferExec"] = True
            orders_data.append(entry)
        response = self._request_clob_private(
            path="orders",
            method="POST",
            data=orders_data,
        )
        return self.response_to_dataframe(response)

    def cancel_order(self, order_id: str) -> CancelOrdersResponse:
        """Cancel a single order."""
        return self._request_clob_private(
            path="order",
            method="DELETE",
            data={"orderID": order_id},
        )

    def cancel_orders(self, order_ids: list[str]) -> CancelOrdersResponse:
        """Cancel multiple orders."""
        return self._request_clob_private(
            path="orders",
            method="DELETE",
            data=order_ids,
        )

    def cancel_all_orders(self) -> CancelOrdersResponse:
        """Cancel all orders."""
        return self._request_clob_private(path="cancel-all", method="DELETE")

    def cancel_orders_from_market(
        self, market: str = "", asset_id: str = ""
    ) -> CancelOrdersResponse:
        """Cancel orders from a specific market or asset.

        Args:
            market: Condition ID of the market.
            asset_id: CLOB token ID (asset) to cancel orders for.
        """
        return self._request_clob_private(
            path="cancel-market-orders",
            method="DELETE",
            data={"market": market, "asset_id": asset_id},
        )

    def send_heartbeat(self) -> dict:
        """Send a heartbeat to keep open orders alive.

        https://docs.polymarket.com/api-reference/clob/post-heartbeat
        """
        return self._request_clob_private(path="heartbeats", method="POST")

    # ── CLOB API: API Keys ───────────────────────────────────────────────

    def _apply_api_creds(self, creds: dict) -> dict:
        """Set L2 credentials on the client from an API key response."""
        self._api_key = creds["apiKey"]
        self._api_secret = creds["secret"]
        self._api_passphrase = creds["passphrase"]
        return creds

    def create_api_key(self, nonce: int = 0) -> ApiCredentials:
        """Create a new API key using an L1 (EIP-712) signature.

        Automatically sets the returned credentials on this client
        so subsequent L2-authenticated calls work immediately.

        Args:
            nonce (int): Nonce value for the signature. Default is 0.

        Returns:
            dict: The created API key credentials (apiKey, secret, passphrase).
        """
        headers = self._build_l1_headers(nonce=nonce)
        response = self._client.post(f"{self.clob_url}auth/api-key", headers=headers)
        response.raise_for_status()
        return self._apply_api_creds(response.json())

    def derive_api_key(self, nonce: int = 0) -> ApiCredentials:
        """Derive an existing API key using an L1 (EIP-712) signature.

        Automatically sets the returned credentials on this client
        so subsequent L2-authenticated calls work immediately.

        Args:
            nonce (int): Nonce value for the signature. Default is 0.

        Returns:
            dict: The derived API key credentials (apiKey, secret, passphrase).
        """
        headers = self._build_l1_headers(nonce=nonce)
        response = self._client.get(f"{self.clob_url}auth/derive-api-key", headers=headers)
        response.raise_for_status()
        return self._apply_api_creds(response.json())

    def get_api_keys(self) -> pd.DataFrame:
        """Get all API keys for the authenticated user (L2 auth)."""
        data = self._request_clob_private(path="auth/api-key")
        return self.response_to_dataframe(data)

    def delete_api_key(self) -> dict:
        """Delete the current API key (L2 auth)."""
        return self._request_clob_private(path="auth/api-key", method="DELETE")
