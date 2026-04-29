"""RFQ (Request-for-Quote) mixin for the Polymarket V2 CLOB API.

Mirrors ``py_clob_client_v2/rfq/rfq_client.py``. All methods use standard
L2 HMAC auth via :meth:`_request_clob_private`.

**Scope (v0.12.1):** all 11 RFQ endpoints implemented. Accept/approve
sign V1 12-field orders (``_build_order_v1`` on the parent client) per
the reference SDK; everything else uses V2 L2 auth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polymarket_pandas.exceptions import PolymarketAPIError

if TYPE_CHECKING:
    pass


_BUY = "BUY"
_SELL = "SELL"
_COLLATERAL_DECIMALS = 6  # USDC / pUSD
_MATCH_TYPES = ("COMPLEMENTARY", "MINT", "MERGE")


def _parse_units(amount_str: str, decimals: int = _COLLATERAL_DECIMALS) -> int:
    """Convert a decimal string to an integer with the given decimal places."""
    from decimal import Decimal

    return int(Decimal(amount_str) * (10**decimals))


class RfqMixin:
    """RFQ flow for V2 CLOB markets.

    Public surface (kwargs-style; mirrors but doesn't replicate
    py-clob-client-v2's dataclass shape):

    * Read: ``get_rfq_requests``, ``get_rfq_requester_quotes``,
      ``get_rfq_quoter_quotes``, ``get_rfq_best_quote``, ``rfq_config``
    * Write: ``create_rfq_request``, ``cancel_rfq_request``,
      ``create_rfq_quote``, ``cancel_rfq_quote``
    * Accept/approve (V1-signed): ``accept_rfq_quote``,
      ``approve_rfq_order`` — sign V1 12-field orders via
      ``_build_order_v1`` per the reference SDK.
    """

    # ── helpers ─────────────────────────────────────────────────────

    def _rfq_user_type(self) -> int:
        """Resolve the ``userType`` int from the client's configured signature_type."""
        sig = self.signature_type if self.signature_type is not None else 0
        return int(sig)

    def _rfq_amounts(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        tick_size: str | None = None,
    ) -> tuple[str, str, str, str]:
        """Return ``(asset_in, asset_out, amount_in, amount_out)`` for a request/quote.

        Mirrors py-clob-client-v2 RFQ rounding: price is rounded to the
        market's tick decimals; size uses round-down. USDC amount is the
        product, rounded to amount-decimals.
        """
        # Local imports to avoid pulling client internals at module load.
        from polymarket_pandas.client import (
            _TICK_SIZES,
            _round_down,
            _round_normal,
        )

        if tick_size is None:
            tick_size = str(self.get_tick_size(token_id))
        if tick_size not in _TICK_SIZES:
            raise ValueError(f"Invalid tick_size={tick_size!r}")
        price_dp, size_dp, amount_dp = _TICK_SIZES[tick_size]

        rounded_price = _round_normal(float(price), price_dp)
        rounded_size = _round_down(float(size), size_dp)
        usdc_amount = round(rounded_size * rounded_price, amount_dp)

        rounded_size_str = f"{rounded_size:.{size_dp}f}"
        usdc_amount_str = f"{usdc_amount:.{amount_dp}f}"

        size_units = str(_parse_units(rounded_size_str))
        usdc_units = str(_parse_units(usdc_amount_str))

        if side.upper() == _BUY:
            # Requester / quoter "BUY" wants tokens in for USDC out
            return token_id, "0", size_units, usdc_units
        return "0", token_id, usdc_units, size_units

    @staticmethod
    def _rfq_query_params(**fields: Any) -> dict[str, Any]:
        """Drop ``None`` values; flatten lists for ``urlencode(doseq=True)``."""
        return {k: v for k, v in fields.items() if v is not None}

    # ── request-side ────────────────────────────────────────────────

    def create_rfq_request(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        *,
        tick_size: str | None = None,
    ) -> dict:
        """V2 RFQ: create an RFQ request (`POST /rfq/request`).

        Args:
            token_id: Outcome token ID (uint256 string).
            price: Price per token, ``0 < price < 1``.
            size: Size in conditional tokens.
            side: ``"BUY"`` or ``"SELL"`` from the requester's perspective.
            tick_size: Optional tick-size override. Auto-fetched from
                the market when omitted.
        """
        asset_in, asset_out, amount_in, amount_out = self._rfq_amounts(
            token_id, price, size, side, tick_size=tick_size
        )
        body = {
            "assetIn": asset_in,
            "assetOut": asset_out,
            "amountIn": amount_in,
            "amountOut": amount_out,
            "userType": self._rfq_user_type(),
        }
        return self._request_clob_private(path="rfq/request", method="POST", data=body)

    def cancel_rfq_request(self, request_id: str) -> dict:
        """V2 RFQ: cancel an RFQ request (`DELETE /rfq/request`)."""
        return self._request_clob_private(
            path="rfq/request",
            method="DELETE",
            data={"requestId": request_id},
        )

    def get_rfq_requests(
        self,
        *,
        request_ids: list[str] | None = None,
        state: str | None = None,
        markets: list[str] | None = None,
        size_min: float | None = None,
        size_max: float | None = None,
        size_usdc_min: float | None = None,
        size_usdc_max: float | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> dict:
        """V2 RFQ: list RFQ requests with optional filters (`GET /rfq/data/requests`)."""
        params = self._rfq_query_params(
            requestIds=request_ids,
            state=state,
            markets=markets,
            sizeMin=size_min,
            sizeMax=size_max,
            sizeUsdcMin=size_usdc_min,
            sizeUsdcMax=size_usdc_max,
            priceMin=price_min,
            priceMax=price_max,
        )
        return self._request_clob_private(path="rfq/data/requests", params=params)

    # ── quote-side ──────────────────────────────────────────────────

    def create_rfq_quote(
        self,
        request_id: str,
        token_id: str,
        price: float,
        size: float,
        side: str,
        *,
        tick_size: str | None = None,
    ) -> dict:
        """V2 RFQ: create a quote in response to a request (`POST /rfq/quote`).

        Args:
            request_id: ID of the RFQ request being quoted.
            token_id: Outcome token ID.
            price: Quoted price per token.
            size: Quoted size in conditional tokens.
            side: Quoter's side, ``"BUY"`` or ``"SELL"``.
            tick_size: Optional tick-size override.
        """
        asset_in, asset_out, amount_in, amount_out = self._rfq_amounts(
            token_id, price, size, side, tick_size=tick_size
        )
        body = {
            "requestId": request_id,
            "assetIn": asset_in,
            "assetOut": asset_out,
            "amountIn": amount_in,
            "amountOut": amount_out,
            "userType": self._rfq_user_type(),
        }
        return self._request_clob_private(path="rfq/quote", method="POST", data=body)

    def cancel_rfq_quote(self, quote_id: str) -> dict:
        """V2 RFQ: cancel a quote (`DELETE /rfq/quote`)."""
        return self._request_clob_private(
            path="rfq/quote",
            method="DELETE",
            data={"quoteId": quote_id},
        )

    def get_rfq_requester_quotes(
        self,
        *,
        request_ids: list[str] | None = None,
        quote_ids: list[str] | None = None,
        state: str | None = None,
    ) -> dict:
        """V2 RFQ: list quotes on requests created by the authenticated user."""
        params = self._rfq_query_params(requestIds=request_ids, quoteIds=quote_ids, state=state)
        return self._request_clob_private(path="rfq/data/requester/quotes", params=params)

    def get_rfq_quoter_quotes(
        self,
        *,
        request_ids: list[str] | None = None,
        quote_ids: list[str] | None = None,
        state: str | None = None,
    ) -> dict:
        """V2 RFQ: list quotes created by the authenticated user."""
        params = self._rfq_query_params(requestIds=request_ids, quoteIds=quote_ids, state=state)
        return self._request_clob_private(path="rfq/data/quoter/quotes", params=params)

    def get_rfq_best_quote(self, request_id: str) -> dict:
        """V2 RFQ: best quote for a given request (`GET /rfq/data/best-quote`)."""
        return self._request_clob_private(
            path="rfq/data/best-quote",
            params={"requestId": request_id},
        )

    # ── accept/approve (V1-signed orders) ───────────────────────────

    @staticmethod
    def _get_request_order_creation_payload(quote: dict) -> dict:
        """Derive ``(token, side, size, price)`` from an accepted quote.

        Mirrors ``py_clob_client_v2/rfq/rfq_client.py`` —
        the requester's order shape depends on the quote's
        ``matchType`` (``COMPLEMENTARY`` / ``MINT`` / ``MERGE``).
        """
        match_type = str(quote.get("matchType") or "COMPLEMENTARY").upper()
        side = (quote.get("side") or _BUY).upper()
        price = quote.get("price")
        if price is None:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail="RFQ quote missing 'price'"
            )

        if match_type == "COMPLEMENTARY":
            token = quote.get("token")
            if not token:
                raise PolymarketAPIError(
                    status_code=0,
                    url="<internal>",
                    detail="RFQ quote missing 'token' for COMPLEMENTARY match",
                )
            # Requester accepts the inverse of the quoter's side.
            new_side = _SELL if side == _BUY else _BUY
            size = quote.get("sizeOut") if new_side == _BUY else quote.get("sizeIn")
            if size is None:
                raise PolymarketAPIError(
                    status_code=0,
                    url="<internal>",
                    detail="RFQ quote missing sizeIn/sizeOut for COMPLEMENTARY match",
                )
            return {"token": token, "side": new_side, "size": size, "price": float(price)}

        if match_type in ("MINT", "MERGE"):
            token = quote.get("complement")
            if not token:
                raise PolymarketAPIError(
                    status_code=0,
                    url="<internal>",
                    detail=f"RFQ quote missing 'complement' for {match_type} match",
                )
            size = quote.get("sizeIn") if side == _BUY else quote.get("sizeOut")
            if size is None:
                raise PolymarketAPIError(
                    status_code=0,
                    url="<internal>",
                    detail=f"RFQ quote missing sizeIn/sizeOut for {match_type} match",
                )
            # Requester price is the inverse of the quote price.
            return {"token": token, "side": side, "size": size, "price": 1 - float(price)}

        raise PolymarketAPIError(
            status_code=0, url="<internal>", detail=f"Invalid RFQ matchType {match_type!r}"
        )

    def accept_rfq_quote(self, request_id: str, quote_id: str, expiration: int) -> dict:
        """V2 RFQ: accept a quote (requester side) (`POST /rfq/request/accept`).

        Fetches the quote, derives the requester's order shape via
        :meth:`_get_request_order_creation_payload`, signs a V1 12-field
        order via :meth:`_build_order_v1`, and submits the acceptance.

        Args:
            request_id: ID of the RFQ request.
            quote_id: ID of the quote being accepted.
            expiration: Unix timestamp for order expiration. ``0`` =
                no expiry.
        """
        resp = self.get_rfq_requester_quotes(quote_ids=[quote_id])
        data = resp.get("data") or []
        if not data:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail=f"RFQ quote {quote_id!r} not found"
            )

        order_payload = self._get_request_order_creation_payload(data[0])
        order = self._build_order_v1(
            token_id=order_payload["token"],
            price=float(order_payload["price"]),
            size=float(order_payload["size"]),
            side=order_payload["side"],
            expiration=int(expiration),
        )
        body = {
            "requestId": request_id,
            "quoteId": quote_id,
            "owner": self._api_key,
            **order,
        }
        return self._request_clob_private(path="rfq/request/accept", method="POST", data=body)

    def approve_rfq_order(self, request_id: str, quote_id: str, expiration: int) -> dict:
        """V2 RFQ: approve an accepted quote (quoter side) (`POST /rfq/quote/approve`).

        Fetches the quote, signs a V1 12-field order at the quote's
        ``token`` / ``price`` / ``side`` (size from ``sizeIn`` for BUY,
        ``sizeOut`` for SELL), and submits the approval.
        """
        resp = self.get_rfq_quoter_quotes(quote_ids=[quote_id])
        data = resp.get("data") or []
        if not data:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail=f"RFQ quote {quote_id!r} not found"
            )
        quote = data[0]

        side = (quote.get("side") or _BUY).upper()
        token = quote.get("token")
        if not token:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail="RFQ quote missing 'token'"
            )
        price = quote.get("price")
        if price is None:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail="RFQ quote missing 'price'"
            )
        size_key = "sizeIn" if side == _BUY else "sizeOut"
        size = quote.get(size_key)
        if size is None:
            raise PolymarketAPIError(
                status_code=0, url="<internal>", detail=f"RFQ quote missing {size_key!r}"
            )

        order = self._build_order_v1(
            token_id=token,
            price=float(price),
            size=float(size),
            side=side,
            expiration=int(expiration),
        )
        body = {
            "requestId": request_id,
            "quoteId": quote_id,
            "owner": self._api_key,
            **order,
        }
        return self._request_clob_private(path="rfq/quote/approve", method="POST", data=body)

    # ── config ──────────────────────────────────────────────────────

    def rfq_config(self) -> dict:
        """V2 RFQ: server configuration (`GET /rfq/config`)."""
        return self._request_clob_private(path="rfq/config")
