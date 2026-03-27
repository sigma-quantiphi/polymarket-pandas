"""Data API endpoints mixin."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import (
    ActivitySchema,
    BuilderLeaderboardSchema,
    ClosedPositionSchema,
    DataTradeSchema,
    LeaderboardSchema,
    PositionSchema,
)


class DataMixin:
    # ── Data API: Core ───────────────────────────────────────────────────

    def get_positions(
        self,
        user: str,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        sizeThreshold: float | None = 1,
        redeemable: bool | None = False,
        mergeable: bool | None = False,
        limit: int | None = 100,
        offset: int | None = 0,
        sortBy: str | None = "TOKENS",
        sortDirection: str | None = "DESC",
        title: str | None = None,
    ) -> DataFrame[PositionSchema]:
        """Fetch open positions for a user.

        Args:
            user: Wallet address.
            market: Filter by token ID(s).
            eventId: Filter by event ID(s).
            sizeThreshold: Minimum position size to include.
            redeemable: Only show redeemable positions.
            mergeable: Only show mergeable positions.
            limit: Max rows per page.
            offset: Pagination offset.
            sortBy: Column to sort by (e.g. ``"TOKENS"``).
            sortDirection: ``"ASC"`` or ``"DESC"``.
            title: Filter by market title substring.

        Returns:
            DataFrame of open positions.

        See https://docs.polymarket.com/api-reference/data/get-positions
        """
        data = self._request_data(
            path="positions",
            params={
                "user": user,
                "market": market,
                "eventId": eventId,
                "sizeThreshold": sizeThreshold,
                "redeemable": redeemable,
                "mergeable": mergeable,
                "limit": limit,
                "offset": offset,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "title": title,
            },
        )
        return self.response_to_dataframe(data)

    def get_closed_positions(
        self,
        user: str,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        title: str | None = None,
        limit: int | None = 10,
        offset: int | None = 0,
        sortBy: str | None = "REALIZEDPNL",
        sortDirection: str | None = "DESC",
    ) -> DataFrame[ClosedPositionSchema]:
        """Fetch closed (resolved) positions for a user.

        Args:
            user: Wallet address.
            market: Filter by token ID(s).
            eventId: Filter by event ID(s).
            title: Filter by market title substring.
            limit: Max rows per page.
            offset: Pagination offset.
            sortBy: Column to sort by (e.g. ``"REALIZEDPNL"``).
            sortDirection: ``"ASC"`` or ``"DESC"``.

        Returns:
            DataFrame of closed positions.

        See https://docs.polymarket.com/api-reference/data/get-closed-positions
        """
        data = self._request_data(
            path="closed-positions",
            params={
                "user": user,
                "market": market,
                "eventId": eventId,
                "title": title,
                "limit": limit,
                "offset": offset,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
            },
        )
        return self.response_to_dataframe(data)

    def get_market_positions(
        self,
        market: str,
        user: str | None = None,
        status: str | None = "ALL",
        sortBy: str | None = "TOTAL_PNL",
        sortDirection: str | None = "DESC",
        limit: int | None = 50,
        offset: int | None = 0,
    ) -> pd.DataFrame:
        """Fetch all user positions for a specific market.

        Args:
            market: Token ID of the market.
            user: Filter to a single wallet address.
            status: Position status filter (``"ALL"``, ``"OPEN"``, ``"CLOSED"``).
            sortBy: Column to sort by (e.g. ``"TOTAL_PNL"``).
            sortDirection: ``"ASC"`` or ``"DESC"``.
            limit: Max rows per page.
            offset: Pagination offset.

        Returns:
            DataFrame of positions in the given market.

        See https://docs.polymarket.com/api-reference/data/get-market-positions
        """
        data = self._request_data(
            path="v1/market-positions",
            params={
                "market": market,
                "user": user,
                "status": status,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.response_to_dataframe(data)

    def get_top_holders(
        self,
        market: list[str],
        limit: int | None = 100,
        minBalance: int | None = 1,
    ) -> pd.DataFrame:
        """Fetch the top token holders for one or more markets.

        Args:
            market: Token ID(s) to query.
            limit: Max number of holders to return.
            minBalance: Minimum token balance threshold.

        Returns:
            DataFrame of top holders.

        See https://docs.polymarket.com/api-reference/data/get-holders
        """
        data = self._request_data(
            path="holders",
            params={
                "market": market,
                "limit": limit,
                "minBalance": minBalance,
            },
        )
        return self.response_to_dataframe(data)

    def get_positions_value(
        self,
        user: str,
        market: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch the current USD value of a user's positions.

        Args:
            user: Wallet address.
            market: Filter by token ID(s).

        Returns:
            DataFrame with position values.

        See https://docs.polymarket.com/api-reference/data/get-value
        """
        data = self._request_data(
            path="value",
            params={"user": user, "market": market},
        )
        return self.response_to_dataframe(data)

    def get_leaderboard(
        self,
        category: str | None = "OVERALL",
        timePeriod: str | None = "DAY",
        orderBy: str | None = "PNL",
        limit: int | None = 25,
        offset: int | None = 0,
        user: str | None = None,
        userName: str | None = None,
    ) -> DataFrame[LeaderboardSchema]:
        """Fetch the trader leaderboard.

        Args:
            category: Leaderboard category (e.g. ``"OVERALL"``).
            timePeriod: Time window (``"DAY"``, ``"WEEK"``, ``"MONTH"``, ``"ALL"``).
            orderBy: Ranking metric (e.g. ``"PNL"``, ``"VOLUME"``).
            limit: Max rows per page.
            offset: Pagination offset.
            user: Filter to a specific wallet address.
            userName: Filter by username substring.

        Returns:
            DataFrame of leaderboard entries.

        See https://docs.polymarket.com/api-reference/data/get-leaderboard
        """
        data = self._request_data(
            path="v1/leaderboard",
            params={
                "category": category,
                "timePeriod": timePeriod,
                "orderBy": orderBy,
                "limit": limit,
                "offset": offset,
                "user": user,
                "userName": userName,
            },
        )
        return self.response_to_dataframe(data)

    def get_trades(
        self,
        limit: int | None = 100,
        offset: int | None = 0,
        takerOnly: bool | None = True,
        filterType: str | None = None,
        filterAmount: float | None = None,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        user: str | None = None,
        side: str | None = None,
    ) -> DataFrame[DataTradeSchema]:
        """Fetch recent trades.

        Args:
            limit: Max rows per page.
            offset: Pagination offset.
            takerOnly: If True, return only taker-side trades.
            filterType: Amount filter comparator (e.g. ``"ABOVE"``, ``"BELOW"``).
            filterAmount: Threshold for the amount filter.
            market: Filter by token ID(s).
            eventId: Filter by event ID(s).
            user: Filter to a specific wallet address.
            side: Filter by trade side (``"BUY"`` or ``"SELL"``).

        Returns:
            DataFrame of trades.

        See https://docs.polymarket.com/api-reference/data/get-trades
        """
        data = self._request_data(
            path="trades",
            params={
                "limit": limit,
                "offset": offset,
                "takerOnly": takerOnly,
                "filterType": filterType,
                "filterAmount": filterAmount,
                "market": market,
                "eventId": eventId,
                "user": user,
                "side": side,
            },
        )
        return self.response_to_dataframe(data)

    def get_user_activity(
        self,
        user: str,
        limit: int | None = 100,
        offset: int | None = 0,
        market: list[str] | None = None,
        eventId: list[int] | None = None,
        type: list[str] | None = None,
        start: int | None = None,
        end: int | None = None,
        sortBy: str | None = "TIMESTAMP",
        sortDirection: str | None = "DESC",
        side: str | None = None,
    ) -> DataFrame[ActivitySchema]:
        """Fetch activity history (trades, redemptions, merges) for a user.

        Args:
            user: Wallet address.
            limit: Max rows per page.
            offset: Pagination offset.
            market: Filter by token ID(s).
            eventId: Filter by event ID(s).
            type: Activity types to include (e.g. ``["TRADE", "REDEEM"]``).
            start: Start timestamp (Unix seconds).
            end: End timestamp (Unix seconds).
            sortBy: Column to sort by (e.g. ``"TIMESTAMP"``).
            sortDirection: ``"ASC"`` or ``"DESC"``.
            side: Filter by side (``"BUY"`` or ``"SELL"``).

        Returns:
            DataFrame of activity records.

        See https://docs.polymarket.com/api-reference/data/get-activity
        """
        data = self._request_data(
            path="activity",
            params={
                "user": user,
                "limit": limit,
                "offset": offset,
                "market": market,
                "eventId": eventId,
                "type": type,
                "start": start,
                "end": end,
                "sortBy": sortBy,
                "sortDirection": sortDirection,
                "side": side,
            },
        )
        return self.response_to_dataframe(data)

    # ── Data API: Miscellaneous ──────────────────────────────────────────

    def get_accounting_snapshot(self, user: str) -> dict[str, pd.DataFrame]:
        """
        Download and parse the accounting snapshot ZIP for a user.

        Args:
            user (str): User address (0x-prefixed, 40 hex chars).

        Returns:
            dict[str, pd.DataFrame]: Keys are CSV filenames without extension
                ("positions", "equity"), values are parsed DataFrames.
        """
        response = self._client.get(
            f"{self.data_url}v1/accounting/snapshot",
            params={"user": user},
        )
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            return {name.removesuffix(".csv"): pd.read_csv(zf.open(name)) for name in zf.namelist()}

    def get_live_volume(self, id: int) -> dict:
        """Fetch live trading volume for an event.

        Args:
            id: Event ID.

        Returns:
            Dict with volume data.

        See https://docs.polymarket.com/api-reference/data/get-live-volume
        """
        return self._request_data(path="live-volume", params={"id": id})

    def get_open_interest(self, market: list[str] | None = None) -> dict:
        """Fetch open interest for one or more markets.

        Args:
            market: Token ID(s). If None, returns aggregate open interest.

        Returns:
            Dict with open interest data.

        See https://docs.polymarket.com/api-reference/data/get-oi
        """
        return self._request_data(path="oi", params={"market": market})

    def get_traded_markets_count(self, user: str) -> dict:
        """Fetch the number of distinct markets a user has traded.

        Args:
            user: Wallet address.

        Returns:
            Dict with the traded markets count.

        See https://docs.polymarket.com/api-reference/data/get-traded
        """
        return self._request_data(path="traded", params={"user": user})

    # ── Data API: Builders ───────────────────────────────────────────────

    def get_builder_leaderboard(
        self,
        timePeriod: str | None = "DAY",
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> DataFrame[BuilderLeaderboardSchema]:
        """Fetch the builder (liquidity provider) leaderboard.

        Args:
            timePeriod: Time window (``"DAY"``, ``"WEEK"``, ``"MONTH"``, ``"ALL"``).
            limit: Max rows per page.
            offset: Pagination offset.

        Returns:
            DataFrame of builder leaderboard entries.

        See https://docs.polymarket.com/api-reference/data/get-builders-leaderboard
        """
        data = self._request_data(
            path="v1/builders/leaderboard",
            params={
                "timePeriod": timePeriod,
                "limit": limit,
                "offset": offset,
            },
        )
        return self.response_to_dataframe(data)

    def get_builder_volume(self, timePeriod: str | None = "DAY") -> pd.DataFrame:
        """Fetch builder volume breakdown by time period.

        Args:
            timePeriod: Time window (``"DAY"``, ``"WEEK"``, ``"MONTH"``, ``"ALL"``).

        Returns:
            DataFrame of builder volume entries.

        See https://docs.polymarket.com/api-reference/data/get-builders-volume
        """
        data = self._request_data(
            path="v1/builders/volume",
            params={"timePeriod": timePeriod},
        )
        return self.response_to_dataframe(data)
