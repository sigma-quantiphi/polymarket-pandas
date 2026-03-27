"""CLOB rewards API endpoints mixin."""

from __future__ import annotations

import pandas as pd

from polymarket_pandas.types import CursorPage


class RewardsMixin:
    # ── CLOB API: Rewards (Public) ────────────────────────────────────────

    def get_rewards_markets_current(
        self,
        sponsored: bool | None = None,
        next_cursor: str | None = None,
    ) -> CursorPage:
        """Get all currently active reward configurations, organized by market.

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): reward config rows
            - ``next_cursor`` (str): pass to the next call to page forward;
              ``"LTE="`` means the last page has been reached
            - ``count`` (int): items in current response
            - ``limit`` (int): page size

        Args:
            sponsored: If True, returns sponsored reward configurations
                instead of standard ones.
            next_cursor: Opaque cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.

        See https://docs.polymarket.com/api-reference/rewards/get-current-active-rewards-configurations
        """
        raw = self._request_clob(
            path="rewards/markets/current",
            params={"sponsored": sponsored, "next_cursor": next_cursor},
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

    def get_rewards_markets_multi(
        self,
        q: str | None = None,
        tag_slug: str | None = None,
        event_id: str | None = None,
        event_title: str | None = None,
        order_by: str | None = None,
        position: str | None = None,
        min_volume_24hr: float | None = None,
        max_volume_24hr: float | None = None,
        min_spread: float | None = None,
        max_spread: float | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page_size: int | None = None,
        next_cursor: str | None = None,
    ) -> CursorPage:
        """Get active markets with their reward configurations.

        Supports text search, tag filtering, numeric filters, and sorting.
        Uses cursor-based pagination.

        Args:
            q: Text search on market question/description.
            tag_slug: Filter by tag slug.
            event_id: Filter by event ID.
            event_title: Case-insensitive event title search.
            order_by: Sort field (e.g. ``"rate_per_day"``, ``"volume_24hr"``,
                ``"spread"``, ``"competitiveness"``).
            position: Sort direction: ``"ASC"`` or ``"DESC"``.
            min_volume_24hr: Minimum 24h volume filter.
            max_volume_24hr: Maximum 24h volume filter.
            min_spread: Minimum spread filter.
            max_spread: Maximum spread filter.
            min_price: Minimum first-token price filter.
            max_price: Maximum first-token price filter.
            page_size: Items per page (max 500, default 100).
            next_cursor: Opaque cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.

        See https://docs.polymarket.com/api-reference/rewards/get-multiple-markets-with-rewards
        """
        raw = self._request_clob(
            path="rewards/markets/multi",
            params={
                "q": q,
                "tag_slug": tag_slug,
                "event_id": event_id,
                "event_title": event_title,
                "order_by": order_by,
                "position": position,
                "min_volume_24hr": min_volume_24hr,
                "max_volume_24hr": max_volume_24hr,
                "min_spread": min_spread,
                "max_spread": max_spread,
                "min_price": min_price,
                "max_price": max_price,
                "page_size": page_size,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

    def get_rewards_market(
        self,
        condition_id: str,
        sponsored: bool | None = None,
        next_cursor: str | None = None,
    ) -> CursorPage:
        """Get reward configurations for a specific market.

        Uses cursor-based pagination.

        Args:
            condition_id: The condition ID of the market.
            sponsored: If True, folds sponsored daily rates into each
                config's rate_per_day.
            next_cursor: Opaque cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.

        See https://docs.polymarket.com/api-reference/rewards/get-raw-rewards-for-a-specific-market
        """
        raw = self._request_clob(
            path=f"rewards/markets/{condition_id}",
            params={"sponsored": sponsored, "next_cursor": next_cursor},
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

    # ── CLOB API: Rewards (Private — L2 auth) ────────────────────────────

    def get_rewards_earnings(
        self,
        date: str,
        signature_type: int | None = None,
        maker_address: str | None = None,
        sponsored: bool | None = None,
        next_cursor: str | None = None,
    ) -> CursorPage:
        """Get per-market user earnings for a specific day.

        Requires L2 authentication. Uses cursor-based pagination.

        Args:
            date: Target date in ``YYYY-MM-DD`` format.
            signature_type: Address derivation type (0=EOA, 1=POLY_PROXY,
                2=POLY_GNOSIS_SAFE).
            maker_address: Ethereum address to query.
            sponsored: If True, filter to sponsored earnings only.
            next_cursor: Opaque cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.

        See https://docs.polymarket.com/api-reference/rewards/get-earnings-for-a-market-maker
        """
        raw = self._request_clob_private(
            path="rewards/user",
            params={
                "date": date,
                "signature_type": signature_type,
                "maker_address": maker_address,
                "sponsored": sponsored,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw

    def get_rewards_earnings_total(
        self,
        date: str,
        signature_type: int | None = None,
        maker_address: str | None = None,
        sponsored: bool | None = None,
    ) -> pd.DataFrame:
        """Get total earnings for a user on a given day, grouped by asset.

        Requires L2 authentication.

        Args:
            date: Target date in ``YYYY-MM-DD`` format.
            signature_type: Address derivation type (0=EOA, 1=POLY_PROXY,
                2=POLY_GNOSIS_SAFE).
            maker_address: Ethereum address to query.
            sponsored: If True, aggregates both native and sponsored earnings.

        Returns:
            DataFrame with ``date``, ``assetAddress``, ``makerAddress``,
            ``earnings``, ``assetRate`` columns.

        See https://docs.polymarket.com/api-reference/rewards/get-total-earnings-for-user-by-date
        """
        data = self._request_clob_private(
            path="rewards/user/total",
            params={
                "date": date,
                "signature_type": signature_type,
                "maker_address": maker_address,
                "sponsored": sponsored,
            },
        )
        return self.response_to_dataframe(data)

    def get_rewards_percentages(
        self,
        signature_type: int | None = None,
        maker_address: str | None = None,
    ) -> dict:
        """Get real-time reward percentages per market for a user.

        Requires L2 authentication.

        Args:
            signature_type: Address derivation type (0=EOA, 1=POLY_PROXY,
                2=POLY_GNOSIS_SAFE).
            maker_address: Ethereum address to query.

        Returns:
            dict mapping condition_id → percentage (float).

        See https://docs.polymarket.com/api-reference/rewards/get-market-maker-rewards-percentiles
        """
        return self._request_clob_private(
            path="rewards/user/percentages",
            params={
                "signature_type": signature_type,
                "maker_address": maker_address,
            },
        )

    def get_rewards_user_markets(
        self,
        date: str | None = None,
        signature_type: int | None = None,
        maker_address: str | None = None,
        sponsored: bool | None = None,
        q: str | None = None,
        tag_slug: str | None = None,
        favorite_markets: bool | None = None,
        no_competition: bool | None = None,
        only_mergeable: bool | None = None,
        only_open_orders: bool | None = None,
        only_open_positions: bool | None = None,
        order_by: str | None = None,
        position: str | None = None,
        page_size: int | None = None,
        next_cursor: str | None = None,
    ) -> CursorPage:
        """Get user earnings combined with full market configurations.

        Requires L2 authentication. Supports search, filtering, and sorting.
        Uses cursor-based pagination.

        Args:
            date: Target date in ``YYYY-MM-DD`` format (defaults to today).
            signature_type: Address derivation type (0=EOA, 1=POLY_PROXY,
                2=POLY_GNOSIS_SAFE).
            maker_address: Ethereum address to query.
            sponsored: If True, return sponsored reward earnings.
            q: Text search on market question/description.
            tag_slug: Filter by tag slug.
            favorite_markets: Filter to user-favorited markets only.
            no_competition: Filter for markets with no competition.
            only_mergeable: Filter for mergeable markets.
            only_open_orders: Filter for markets with user's open orders.
            only_open_positions: Filter for markets with user's open positions.
            order_by: Sort field (e.g. ``"earnings"``, ``"rate_per_day"``,
                ``"earning_percentage"``).
            position: Sort direction: ``"ASC"`` or ``"DESC"``.
            page_size: Items per page (max 500, default 100).
            next_cursor: Opaque cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.

        See https://docs.polymarket.com/api-reference/rewards/get-user-earnings-and-markets-configuration
        """
        raw = self._request_clob_private(
            path="rewards/user/markets",
            params={
                "date": date,
                "signature_type": signature_type,
                "maker_address": maker_address,
                "sponsored": sponsored,
                "q": q,
                "tag_slug": tag_slug,
                "favorite_markets": favorite_markets,
                "no_competition": no_competition,
                "only_mergeable": only_mergeable,
                "only_open_orders": only_open_orders,
                "only_open_positions": only_open_positions,
                "order_by": order_by,
                "position": position,
                "page_size": page_size,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.response_to_dataframe(raw.get("data", []))
        return raw
