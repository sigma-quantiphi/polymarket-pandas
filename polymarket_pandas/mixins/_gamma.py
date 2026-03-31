"""Gamma API endpoints mixin."""

from __future__ import annotations

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import EventSchema, MarketSchema
from polymarket_pandas.utils import _ts_to_iso, expand_dataframe


def _coerce_outcome_prices(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Convert string values inside outcomePrices lists to float."""
    if col in df.columns:
        df[col] = df[col].apply(lambda x: [float(v) for v in x] if isinstance(x, list) else x)
    return df


def _expand_outcomes(
    df: pd.DataFrame,
    outcomes_col: str,
    prices_col: str,
    tokens_col: str,
) -> pd.DataFrame:
    """Explode parallel outcome/price/token lists into one row per outcome."""
    explode_cols = [c for c in (outcomes_col, prices_col, tokens_col) if c in df.columns]
    if explode_cols:
        df = df.explode(explode_cols, ignore_index=True)
    if prices_col in df.columns:
        df[prices_col] = pd.to_numeric(df[prices_col], errors="coerce")
    if tokens_col in df.columns:
        df[tokens_col] = df[tokens_col].astype(str)
    return df


class GammaMixin:
    # ── Gamma API: Markets ──────────────────────────────────────────────

    def get_markets(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        id: list[int] | None = None,
        slug: list[str] | None = None,
        clob_token_ids: list[str] | None = None,
        condition_ids: list[str] | None = None,
        market_maker_address: list[str] | None = None,
        liquidity_num_min: float | None = None,
        liquidity_num_max: float | None = None,
        volume_num_min: float | None = None,
        volume_num_max: float | None = None,
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
        tag_id: int | None = None,
        related_tags: bool | None = None,
        cyom: bool | None = None,
        uma_resolution_status: str | None = None,
        game_id: str | None = None,
        sports_market_types: list[str] | None = None,
        rewards_min_size: float | None = None,
        question_ids: list[str] | None = None,
        include_tag: bool | None = None,
        closed: bool | None = None,
        expand_clob_token_ids: bool = True,
        expand_events: bool = True,
        expand_series: bool = True,
        expand_outcomes: bool = False,
    ) -> DataFrame[MarketSchema]:
        """Fetch markets with optional filtering, pagination, and nested expansion.

        Returns one row per CLOB token when ``expand_clob_token_ids`` is True.
        Returns one row per outcome when ``expand_outcomes`` is True.

        See: https://docs.polymarket.com/api-reference/gamma/get-markets
        """
        data = self._request_gamma(
            path="markets",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "clob_token_ids": clob_token_ids,
                "condition_ids": condition_ids,
                "market_maker_address": market_maker_address,
                "liquidity_num_min": liquidity_num_min,
                "liquidity_num_max": liquidity_num_max,
                "volume_num_min": volume_num_min,
                "volume_num_max": volume_num_max,
                "start_date_min": _ts_to_iso(start_date_min),
                "start_date_max": _ts_to_iso(start_date_max),
                "end_date_min": _ts_to_iso(end_date_min),
                "end_date_max": _ts_to_iso(end_date_max),
                "tag_id": tag_id,
                "related_tags": related_tags,
                "cyom": cyom,
                "uma_resolution_status": uma_resolution_status,
                "game_id": game_id,
                "sports_market_types": sports_market_types,
                "rewards_min_size": rewards_min_size,
                "question_ids": question_ids,
                "include_tag": include_tag,
                "closed": closed,
            },
        )
        raw_count = len(data)
        data = pd.DataFrame(data)
        if not data.empty:
            if expand_events or expand_series:
                data = expand_dataframe(data, field="events", column="events")
                if expand_series and "eventsSeries" in data.columns:
                    data = expand_dataframe(data, field="eventsSeries", column="eventsSeries")
        data = self.preprocess_dataframe(data)
        data = _coerce_outcome_prices(data, "outcomePrices")
        if expand_outcomes and not data.empty:
            data = _expand_outcomes(data, "outcomes", "outcomePrices", "clobTokenIds")
        elif expand_clob_token_ids and not data.empty:
            data = data.explode("clobTokenIds", ignore_index=True)
            data["clobTokenIds"] = data["clobTokenIds"].astype(str)
        data = data.reset_index(drop=True)
        data.attrs["_raw_count"] = raw_count
        return data

    def get_market_by_id(self, id: int, include_tag: bool | None = None) -> dict:
        """Fetch a single market by its numeric ID.

        JSON-string fields (``clobTokenIds``, ``outcomes``, ``outcomePrices``)
        are automatically parsed into Python lists.

        See: https://docs.polymarket.com/api-reference/gamma/get-markets
        """
        data = self._request_gamma(path=f"markets/{id}", params={"include_tag": include_tag})
        return self.preprocess_dict(data)

    def get_market_by_slug(self, slug: str, include_tag: bool | None = None) -> dict:
        """Fetch a single market by its URL slug.

        JSON-string fields (``clobTokenIds``, ``outcomes``, ``outcomePrices``)
        are automatically parsed into Python lists.

        See: https://docs.polymarket.com/api-reference/gamma/get-markets
        """
        data = self._request_gamma(path=f"markets/slug/{slug}", params={"include_tag": include_tag})
        return self.preprocess_dict(data)

    def get_market_tags(self, id: int) -> pd.DataFrame:
        """Fetch tags associated with a market by its numeric ID.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        data = self._request_gamma(path=f"markets/{id}/tags")
        return self.response_to_dataframe(data)

    # ── Gamma API: Events ───────────────────────────────────────────────

    def get_events(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        id: list[int] | None = None,
        slug: list[str] | None = None,
        tag_id: int | None = None,
        exclude_tag_id: list[int] | None = None,
        related_tags: bool | None = None,
        featured: bool | None = None,
        cyom: bool | None = None,
        include_chat: bool | None = None,
        include_template: bool | None = None,
        recurrence: str | None = None,
        closed: bool | None = None,
        start_date_min: str | pd.Timestamp | None = None,
        start_date_max: str | pd.Timestamp | None = None,
        end_date_min: str | pd.Timestamp | None = None,
        end_date_max: str | pd.Timestamp | None = None,
        expand_markets: bool | None = True,
        expand_clob_token_ids: bool | None = True,
        expand_outcomes: bool = False,
    ) -> DataFrame[EventSchema]:
        """Fetch events with optional filtering, pagination, and nested market expansion.

        Returns one row per CLOB token when ``expand_clob_token_ids`` is True.
        Returns one row per outcome when ``expand_outcomes`` is True.

        See: https://docs.polymarket.com/api-reference/gamma/get-events
        """
        data = self._request_gamma(
            path="events",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "id": id,
                "slug": slug,
                "tag_id": tag_id,
                "exclude_tag_id": exclude_tag_id,
                "related_tags": related_tags,
                "featured": featured,
                "cyom": cyom,
                "include_chat": include_chat,
                "include_template": include_template,
                "recurrence": recurrence,
                "closed": closed,
                "start_date_min": _ts_to_iso(start_date_min),
                "start_date_max": _ts_to_iso(start_date_max),
                "end_date_min": _ts_to_iso(end_date_min),
                "end_date_max": _ts_to_iso(end_date_max),
            },
        )
        raw_count = len(data)
        data = pd.DataFrame(data)
        if expand_markets or expand_clob_token_ids:
            data = expand_dataframe(data, field="markets", column="markets")
        data = self.preprocess_dataframe(data)
        data = _coerce_outcome_prices(data, "marketsOutcomePrices")
        if expand_outcomes and not data.empty:
            data = _expand_outcomes(
                data, "marketsOutcomes", "marketsOutcomePrices", "marketsClobTokenIds"
            )
        elif expand_clob_token_ids and not data.empty:
            data = data.explode("marketsClobTokenIds", ignore_index=True)
            data["marketsClobTokenIds"] = data["marketsClobTokenIds"].astype(str)
        data.attrs["_raw_count"] = raw_count
        return data

    def get_event_by_id(
        self,
        id: int,
        include_chat: bool | None = None,
        include_template: bool | None = None,
    ) -> dict:
        """Fetch a single event by its numeric ID.

        See: https://docs.polymarket.com/api-reference/gamma/get-events
        """
        return self._request_gamma(
            path=f"events/{id}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )

    def get_event_by_slug(
        self,
        slug: str,
        include_chat: bool | None = None,
        include_template: bool | None = None,
    ) -> dict:
        """
        Retrieve an event by its slug.
        Args:
            slug (str): The slug of the event.
            include_chat (bool | None): Whether to include chat information.
            include_template (bool | None): Whether to include the template data.
        Returns:
            dict: The event information.
        """
        return self._request_gamma(
            path=f"events/slug/{slug}",
            params={
                "include_chat": include_chat,
                "include_template": include_template,
            },
        )

    def get_event_tags(self, id: int) -> pd.DataFrame:
        """
        Retrieve tags associated with an event by its ID.
        Args:
            id (int): The unique identifier for the event.
        Returns:
            pd.DataFrame: A DataFrame containing the event tags.
        """
        data = self._request_gamma(path=f"events/{id}/tags")
        return self.response_to_dataframe(data)

    # ── Gamma API: Tags ─────────────────────────────────────────────────

    def get_tags(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        include_template: bool | None = None,
        is_carousel: bool | None = None,
    ) -> pd.DataFrame:
        """Fetch tags with optional filtering and pagination.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        data = self._request_gamma(
            path="tags",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "include_template": include_template,
                "is_carousel": is_carousel,
            },
        )
        return self.response_to_dataframe(data)

    def get_tag_by_id(self, id: int, include_template: bool | None = None) -> dict:
        """Fetch a single tag by its numeric ID.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        return self._request_gamma(path=f"tags/{id}", params={"include_template": include_template})

    def get_tag_by_slug(self, slug: str, include_template: bool | None = None) -> dict:
        """Fetch a single tag by its URL slug.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        return self._request_gamma(
            path=f"tags/slug/{slug}", params={"include_template": include_template}
        )

    def get_related_tags_by_tag_id(
        self, id: int, omit_empty: bool | None = None, status: str | None = None
    ) -> pd.DataFrame:
        """Fetch related tags for a tag by its numeric ID.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        data = self._request_gamma(
            path=f"tags/{id}/related-tags/tags",
            params={"omit_empty": omit_empty, "status": status},
        )
        return self.response_to_dataframe(data)

    def get_related_tags_by_tag_slug(
        self, slug: str, omit_empty: bool | None = None, status: str | None = None
    ) -> pd.DataFrame:
        """Fetch related tags for a tag by its URL slug.

        See: https://docs.polymarket.com/api-reference/gamma/get-tags
        """
        data = self._request_gamma(
            path=f"tags/slug/{slug}/related-tags/tags",
            params={"omit_empty": omit_empty, "status": status},
        )
        return self.response_to_dataframe(data)

    # ── Gamma API: Series & Sports ──────────────────────────────────────

    def get_series(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        slug: list[str] | None = None,
        categories_ids: list[int] | None = None,
        categories_labels: list[str] | None = None,
        closed: bool | None = None,
        include_chat: bool | None = None,
        recurrence: str | None = None,
        expand_events: bool = False,
        expand_event_tags: bool = False,
    ) -> pd.DataFrame:
        """Fetch series with optional filtering, pagination, and nested event expansion.

        See: https://docs.polymarket.com/api-reference/gamma/get-series
        """
        data = self._request_gamma(
            path="series",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "slug": slug,
                "categories_ids": categories_ids,
                "categories_labels": categories_labels,
                "closed": closed,
                "include_chat": include_chat,
                "recurrence": recurrence,
            },
        )
        raw_count = len(data)
        if expand_events or expand_event_tags:
            data = pd.DataFrame(data)
            data = expand_dataframe(data, field="events", column="events")
            if expand_event_tags:
                data = expand_dataframe(data, field="eventsTags", column="eventsTags")
        else:
            data = pd.DataFrame(data)
        data = self.preprocess_dataframe(data)
        data.attrs["_raw_count"] = raw_count
        return data

    def get_series_by_id(self, id: int, include_chat: bool | None = None) -> dict:
        """Fetch a single series by its numeric ID.

        See: https://docs.polymarket.com/api-reference/gamma/get-series
        """
        return self._request_gamma(
            path=f"series/{id}",
            params={"include_chat": include_chat},
        )

    def get_sports_metadata(
        self,
        sport: str | None = None,
        image: str | None = None,
        resolution: str | None = None,
        ordering: str | None = None,
        tags: str | None = None,
        series: str | None = None,
    ) -> pd.DataFrame:
        """Fetch sports metadata (leagues, resolution sources, ordering, etc.)."""
        data = self._request_gamma(
            path="sports",
            params={
                "sport": sport,
                "image": image,
                "resolution": resolution,
                "ordering": ordering,
                "tags": tags,
                "series": series,
            },
        )
        return self.response_to_dataframe(data)

    def get_sports_market_types(self) -> dict:
        """Fetch the list of supported sports market types."""
        return self._request_gamma(path="sports/market-types")

    def get_teams(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: list[str] | None = None,
        ascending: bool | None = None,
        league: list[str] | None = None,
        name: list[str] | None = None,
        abbreviation: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch sports teams with optional filtering by league, name, or abbreviation."""
        data = self._request_gamma(
            path="teams",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "league": league,
                "name": name,
                "abbreviation": abbreviation,
            },
        )
        return self.response_to_dataframe(data)

    # ── Gamma API: Comments ─────────────────────────────────────────────

    def get_comments(
        self,
        limit: int | None = 300,
        offset: int | None = None,
        order: str | None = None,
        ascending: bool | None = None,
        parent_entity_type: str | None = None,
        parent_entity_id: int | None = None,
        get_positions: bool | None = None,
        holders_only: bool | None = None,
    ) -> pd.DataFrame:
        """Fetch comments with optional filtering and pagination."""
        data = self._request_gamma(
            path="comments",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
                "parent_entity_type": parent_entity_type,
                "parent_entity_id": parent_entity_id,
                "get_positions": get_positions,
                "holders_only": holders_only,
            },
        )
        return self.response_to_dataframe(data)

    def get_comments_by_user_address(
        self,
        user_address: str,
        limit: int | None = 300,
        offset: int | None = None,
        order: str | None = None,
        ascending: bool | None = None,
    ) -> pd.DataFrame:
        """Fetch comments posted by a specific user address."""
        data = self._request_gamma(
            path=f"comments/user_address/{user_address}",
            params={
                "limit": limit,
                "offset": offset,
                "order": order,
                "ascending": ascending,
            },
        )
        return self.response_to_dataframe(data)

    def get_comment_by_id(self, id: int, get_positions: bool | None = None) -> dict:
        """Fetch a single comment by its numeric ID."""
        return self._request_gamma(
            path=f"comments/{id}",
            params={"get_positions": get_positions},
        )

    # ── Gamma API: Search ────────────────────────────────────────────────

    def search_markets_events_profiles(
        self,
        q: str,
        cache: bool | None = None,
        events_status: str | None = None,
        limit_per_type: int | None = None,
        page: int | None = None,
        events_tag: list[str] | None = None,
        keep_closed_markets: int | None = None,
        sort: str | None = None,
        ascending: bool | None = None,
        search_tags: bool | None = None,
        search_profiles: bool | None = None,
        recurrence: str | None = None,
        exclude_tag_id: list[int] | None = None,
        optimized: bool | None = None,
    ) -> dict:
        """Search across markets, events, and profiles by query string.

        Returns a dict with separate keys for each result type.

        See: https://docs.polymarket.com/api-reference/gamma/search
        """
        return self._request_gamma(
            path="public-search",
            params={
                "q": q,
                "cache": cache,
                "events_status": events_status,
                "limit_per_type": limit_per_type,
                "page": page,
                "events_tag": events_tag,
                "keep_closed_markets": keep_closed_markets,
                "sort": sort,
                "ascending": ascending,
                "search_tags": search_tags,
                "search_profiles": search_profiles,
                "recurrence": recurrence,
                "exclude_tag_id": exclude_tag_id,
                "optimized": optimized,
            },
        )

    # ── Gamma API: Profiles ──────────────────────────────────────────────

    def get_profile(self, address: str) -> dict:
        """
        Get the public profile for a wallet address.

        Args:
            address (str): Wallet address (proxy wallet or user address), 0x-prefixed.

        Returns:
            dict: Public profile data (name, pseudonym, bio, xUsername, verifiedBadge, etc.).
        """
        return self._request_gamma(path="public-profile", params={"address": address})
