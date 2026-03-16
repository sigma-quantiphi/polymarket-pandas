"""CLOB public API endpoints mixin (market data, sampling, builder trades, rebates)."""
from __future__ import annotations

import pandas as pd


class ClobPublicMixin:
    # ── CLOB API: Market Data ────────────────────────────────────────────

    def get_server_time(self) -> int:
        """
        Get the current server time.

        Returns:
            int: The server time as a Unix timestamp (seconds).
        """
        return self._request_clob(path="time")

    def get_tick_size(self, token_id: str) -> float:
        """
        Get the minimum tick size for a token.

        Args:
            token_id (str): The CLOB token ID.

        Returns:
            float: The minimum tick size.
        """
        data = self._request_clob(path="tick-size", params={"token_id": token_id})
        return float(self._extract(data, "minimum_tick_size"))

    def get_neg_risk(self, token_id: str) -> bool:
        """
        Check whether a token is neg-risk.

        Args:
            token_id (str): The CLOB token ID.

        Returns:
            bool: True if the token is neg-risk.
        """
        data = self._request_clob(path="neg-risk", params={"token_id": token_id})
        return bool(self._extract(data, "neg_risk"))

    def get_fee_rate(self, token_id: str | None = None) -> int:
        """Get the base fee rate, optionally for a specific token.

        https://docs.polymarket.com/api-reference/clob/fee-rate

        Args:
            token_id: CLOB token ID. If ``None``, returns the global base fee.

        Returns:
            int: The base fee in basis points.
        """
        data = self._request_clob(path="fee-rate", params={"token_id": token_id})
        return int(self._extract(data, "base_fee"))

    def get_orderbook(self, token_id: str) -> pd.DataFrame:
        """Get the L2 orderbook for a token.

        https://docs.polymarket.com/api-reference/clob/get-order-book

        Args:
            token_id: CLOB token ID.

        Returns:
            pd.DataFrame: Orderbook with bid/ask price and size columns.
        """
        data = self._request_clob(path="book", params=dict(token_id=token_id))
        return self.orderbook_to_dataframe(data)

    def get_orderbooks(self, data: pd.DataFrame) -> pd.DataFrame:
        """Get orderbooks for multiple tokens in a single request.

        https://docs.polymarket.com/api-reference/clob/get-order-books

        Args:
            data: DataFrame with a ``tokenId`` column identifying each token.

        Returns:
            pd.DataFrame: Combined orderbook rows for all requested tokens.
        """
        from polymarket_pandas.client import markets_to_dict
        data = self._request_clob(
            path="books", method="POST", data=markets_to_dict(data)
        )
        return self.orderbook_to_dataframe(data)

    def get_market_price(self, token_id: str, side: str) -> float:
        """
        Retrieves the market price for a specific token and side.

        Args:
            token_id (str): The unique identifier for the token.
            side (str): The market side, either "BUY" or "SELL".

        Returns:
            float: The market price.
        """
        data = self._request_clob(
            path="price", params={"token_id": token_id, "side": side}
        )
        return float(self._extract(data, "price"))

    def get_market_prices(self, token_sides: list[dict]) -> pd.DataFrame:
        """
        Retrieve market prices for multiple tokens and sides.
        Args:
            token_sides (list[dict]): A list of dictionaries. Each dictionary contains:
                - token_id (str): The unique identifier for the token.
                - side (str): The side ("BUY" or "SELL").
        Returns:
            pd.DataFrame: A DataFrame containing the market prices for tokens.
        """
        data = self._request_clob(path="prices", method="POST", data=token_sides)
        return self.response_to_dataframe(data)

    def get_multiple_market_prices_by_request(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Retrieves market prices for specified tokens and sides via a POST request.
        """
        from polymarket_pandas.client import markets_to_dict
        data = self._request_clob(
            path="prices", method="POST", data=markets_to_dict(data)
        )
        df = []
        for k, v in data.items():
            for sub_k, sub_v in v.items():
                df.append({"tokenId": k, "side": sub_k, "price": sub_v})
        return self.response_to_dataframe(df)

    def get_midpoint_price(self, token_id: str) -> float:
        """
        Retrieve the midpoint price for a specific token.

        Args:
            token_id (str): The unique identifier for the token.

        Returns:
            float: The midpoint price.
        """
        data = self._request_clob(path="midpoint", params={"token_id": token_id})
        return float(self._extract(data, "mid"))

    def get_midpoints(self, token_ids: list[str]) -> pd.DataFrame:
        """Get midpoint prices for multiple tokens.

        https://docs.polymarket.com/api-reference/clob/get-midpoints

        Args:
            token_ids: List of CLOB token IDs.

        Returns:
            pd.DataFrame: Rows with ``tokenId`` and ``mid`` columns.
        """
        data = self._request_clob(
            path="midpoints", params={"token_ids": ",".join(token_ids)}
        )
        rows = [{"tokenId": k, "mid": v} for k, v in data.items()]
        return self.response_to_dataframe(rows)

    def get_midpoints_by_request(self, data: pd.DataFrame) -> pd.DataFrame:
        """Get midpoint prices for tokens specified in a DataFrame.

        https://docs.polymarket.com/api-reference/clob/get-midpoints

        Args:
            data: DataFrame with a ``tokenId`` column identifying each token.

        Returns:
            pd.DataFrame: Rows with ``tokenId`` and ``mid`` columns.
        """
        from polymarket_pandas.client import markets_to_dict
        result = self._request_clob(
            path="midpoints", method="POST", data=markets_to_dict(data)
        )
        rows = [{"tokenId": k, "mid": v} for k, v in result.items()]
        return self.response_to_dataframe(rows)

    def get_spread(self, token_id: str) -> float:
        """Get the bid-ask spread for a token.

        https://docs.polymarket.com/api-reference/clob/get-spread

        Args:
            token_id: CLOB token ID.

        Returns:
            float: The spread value.
        """
        data = self._request_clob(path="spread", params={"token_id": token_id})
        return float(self._extract(data, "spread"))

    def get_bid_ask_spreads(self, data: pd.DataFrame) -> dict:
        """
        Retrieves bid-ask spreads for multiple tokens via a POST request.
        """
        from polymarket_pandas.client import markets_to_dict
        data = self._request_clob(
            path="spreads", method="POST", data=markets_to_dict(data)
        )
        return {k: float(v) for k, v in data.items()}

    def get_last_trade_price(self, token_id: str) -> dict:
        """Get the last traded price for a token.

        https://docs.polymarket.com/api-reference/clob/get-last-trade-price

        Args:
            token_id: CLOB token ID.

        Returns:
            dict: Response containing the last trade price.
        """
        return self._request_clob(
            path="last-trade-price", params={"token_id": token_id}
        )

    def get_last_trade_prices(self, data: pd.DataFrame) -> pd.DataFrame:
        """Get last traded prices for multiple tokens.

        https://docs.polymarket.com/api-reference/clob/get-last-trades-prices

        Args:
            data: DataFrame with a ``tokenId`` column identifying each token.

        Returns:
            pd.DataFrame: Last trade price rows for each token.
        """
        from polymarket_pandas.client import markets_to_dict
        result = self._request_clob(
            path="last-trades-prices", method="POST", data=markets_to_dict(data)
        )
        return self.response_to_dataframe(result)

    def get_price_history(
        self,
        market: str,
        startTs: int | None = None,
        endTs: int | None = None,
        interval: str | None = None,
        fidelity: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetches historical price data for a specific market token.

        Args:
            market (str): The CLOB token ID for which to fetch price history.
            startTs (int | None): The start time, as a Unix UTC timestamp.
            endTs (int | None): The end time, as a Unix UTC timestamp.
            interval (str | None): A duration string ending at the current time. Options: "1m", "1w", "1d", "6h", "1h", "max".
            fidelity (int | None): The resolution of the data, in minutes.

        Returns:
            pd.DataFrame: A DataFrame containing historical price data.
        """
        data = self._request_clob(
            path="prices-history",
            params={
                "market": market,
                "startTs": startTs,
                "endTs": endTs,
                "interval": interval,
                "fidelity": fidelity,
            },
        )
        return self.response_to_dataframe(data)

    # ── CLOB API: Sampling / Simplified Markets ──────────────────────────

    def get_sampling_markets(self, next_cursor: str | None = None) -> dict:
        """
        Get markets that are currently eligible for liquidity-provider rewards.

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed market rows
            - ``next_cursor`` (str): pass to the next call to page forward;
              ``"LTE="`` means the last page has been reached
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Args:
            next_cursor: Opaque base64 cursor from a previous response.
                         Omit (or pass ``None``) to start from the first page.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob(
            path="sampling-markets", params={"next_cursor": next_cursor}
        )
        raw["data"] = self.preprocess_dataframe(pd.DataFrame(raw.get("data", [])))
        return raw

    def get_simplified_markets(self, next_cursor: str | None = None) -> dict:
        """
        Get a lightweight snapshot of all CLOB markets (condition IDs, token prices,
        reward rates).

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed simplified market rows
            - ``next_cursor`` (str): pass to the next call to page forward
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Args:
            next_cursor: Opaque base64 cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob(
            path="simplified-markets", params={"next_cursor": next_cursor}
        )
        raw["data"] = self.preprocess_dataframe(pd.DataFrame(raw.get("data", [])))
        return raw

    def get_sampling_simplified_markets(self, next_cursor: str | None = None) -> dict:
        """
        Intersection of sampling markets and simplified markets.

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed rows
            - ``next_cursor`` (str): pass to the next call to page forward
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Args:
            next_cursor: Opaque base64 cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob(
            path="sampling-simplified-markets", params={"next_cursor": next_cursor}
        )
        raw["data"] = self.preprocess_dataframe(pd.DataFrame(raw.get("data", [])))
        return raw

    # ── CLOB API: Builder Trades ─────────────────────────────────────────

    def get_builder_trades(
        self,
        id: str | None = None,
        builder: str | None = None,
        market: str | None = None,
        asset_id: str | None = None,
        before: str | None = None,
        after: str | None = None,
        next_cursor: str | None = None,
    ) -> dict:
        """
        Get trades attributed to a builder (requires builder API key credentials).

        Uses cursor-based pagination. Returns a dict with keys:
            - ``data`` (pd.DataFrame): preprocessed trade rows
            - ``next_cursor`` (str): pass to the next call to page forward
            - ``count`` (int): total result count
            - ``limit`` (int): page size

        Requires ``POLYMARKET_BUILDER_API_KEY``, ``POLYMARKET_BUILDER_API_SECRET``,
        and ``POLYMARKET_BUILDER_API_PASSPHRASE`` to be set (env vars or constructor
        kwargs ``_builder_api_key`` / ``_builder_api_secret`` /
        ``_builder_api_passphrase``).

        Args:
            id: Trade ID filter.
            builder: Builder identifier (UUID).
            market: Market condition ID.
            asset_id: Asset / token ID.
            before: Return trades with matchTime < this Unix timestamp string.
            after: Return trades with matchTime > this Unix timestamp string.
            next_cursor: Opaque base64 cursor from a previous response.

        Returns:
            dict with ``data``, ``next_cursor``, ``count``, ``limit`` keys.
        """
        raw = self._request_clob_builder(
            path="builder/trades",
            params={
                "id": id,
                "builder": builder,
                "market": market,
                "asset_id": asset_id,
                "before": before,
                "after": after,
                "next_cursor": next_cursor,
            },
        )
        raw["data"] = self.preprocess_dataframe(pd.DataFrame(raw.get("data", [])))
        return raw

    # ── CLOB API: Rebates ────────────────────────────────────────────────

    def get_rebates(self, date: str, maker_address: str) -> pd.DataFrame:
        """
        Get the current rebated fees for a maker on a given date.

        No authentication required.

        Args:
            date: Date in ``YYYY-MM-DD`` format.
            maker_address: Ethereum address of the maker (``0x``-prefixed).

        Returns:
            pd.DataFrame: Rows with columns ``date``, ``condition_id``,
            ``asset_address``, ``maker_address``, ``rebated_fees_usdc``.
        """
        data = self._request_clob(
            path="rebates/current",
            params={"date": date, "maker_address": maker_address},
        )
        return self.response_to_dataframe(data)
