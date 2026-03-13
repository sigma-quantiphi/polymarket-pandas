"""Data API endpoints mixin."""
from __future__ import annotations

import io
import zipfile

import pandas as pd


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
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
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
    ) -> pd.DataFrame:
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
            return {
                name.removesuffix(".csv"): pd.read_csv(zf.open(name))
                for name in zf.namelist()
            }

    def get_live_volume(self, id: int) -> dict:
        return self._request_data(path="live-volume", params={"id": id})

    def get_open_interest(self, market: list[str] | None = None) -> dict:
        return self._request_data(path="oi", params={"market": market})

    def get_traded_markets_count(self, user: str) -> dict:
        return self._request_data(path="traded", params={"user": user})

    # ── Data API: Builders ───────────────────────────────────────────────

    def get_builder_leaderboard(
        self,
        timePeriod: str | None = "DAY",
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> pd.DataFrame:
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
        data = self._request_data(
            path="v1/builders/volume",
            params={"timePeriod": timePeriod},
        )
        return self.response_to_dataframe(data)
