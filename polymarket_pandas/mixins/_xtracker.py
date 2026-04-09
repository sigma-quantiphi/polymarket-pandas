"""xtracker API endpoints mixin.

Polymarket runs a separate post-tracking service at
``https://xtracker.polymarket.com/`` that powers the resolution of all the
"# tweets / # posts in window" markets (e.g. Elon, Trump, Zelenskyy). The
service has 7 public endpoints, no auth, and a uniform
``{success, data, message}`` envelope which is unwrapped centrally in
``PolymarketPandas._request_xtracker``.

See: https://xtracker.polymarket.com/docs
"""

from __future__ import annotations

import pandas as pd
from pandera.typing import DataFrame

from polymarket_pandas.schemas import (
    XTrackerMetricSchema,
    XTrackerPostSchema,
    XTrackerTrackingSchema,
    XTrackerUserSchema,
)
from polymarket_pandas.types import XTrackerTracking, XTrackerUser
from polymarket_pandas.utils import _ts_to_iso


def _to_iso_date(value: str | pd.Timestamp | None) -> str | None:
    """Convert a date-ish value to an ISO ``YYYY-MM-DD`` string."""
    if value is None:
        return None
    iso = _ts_to_iso(value)
    return iso[:10] if iso else None


class XTrackerMixin:
    # ── User endpoints ───────────────────────────────────────────────────

    def get_xtracker_users(
        self,
        platform: str | None = None,
        stats: bool | None = None,
        include_inactive: bool | None = None,
    ) -> DataFrame[XTrackerUserSchema]:
        """List tracked users on the xtracker service.

        Args:
            platform: ``"X"`` or ``"TRUTH_SOCIAL"`` (None = all platforms).
            stats: When True, include per-user aggregate stats.
            include_inactive: When True, include users who are no longer
                actively tracked.

        See: https://xtracker.polymarket.com/docs
        """
        data = self._request_xtracker(
            "users",
            params={
                "platform": platform,
                "stats": stats,
                "includeInactive": include_inactive,
            },
        )
        return self.response_to_dataframe(data)

    def get_xtracker_user(self, handle: str, platform: str | None = None) -> XTrackerUser:
        """Fetch a single tracked user by handle.

        Args:
            handle: Platform handle (e.g. ``"elonmusk"``).
            platform: Required if the same handle exists on multiple
                platforms.

        See: https://xtracker.polymarket.com/docs
        """
        return self._request_xtracker(f"users/{handle}", params={"platform": platform})

    def get_xtracker_user_posts(
        self,
        handle: str,
        platform: str | None = None,
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
        timezone: str = "EST",
    ) -> DataFrame[XTrackerPostSchema]:
        """Fetch tracked posts for a user within a date range.

        Args:
            handle: Platform handle.
            platform: Required if the handle exists on multiple platforms.
            start_date: ISO date string, ``pd.Timestamp``, or ``datetime``.
                Interpreted in the ``timezone`` argument's time zone.
            end_date: Inclusive end of the window, same accepted types.
            timezone: Time-zone label used to interpret ``start_date`` and
                ``end_date``. xtracker uses ``"EST"`` by default for the
                Polymarket markets it resolves.

        See: https://xtracker.polymarket.com/docs
        """
        data = self._request_xtracker(
            f"users/{handle}/posts",
            params={
                "platform": platform,
                "startDate": _to_iso_date(start_date),
                "endDate": _to_iso_date(end_date),
                "timezone": timezone,
            },
        )
        return self.response_to_dataframe(data)

    def get_xtracker_user_trackings(
        self,
        handle: str,
        platform: str | None = None,
        active_only: bool | None = None,
    ) -> DataFrame[XTrackerTrackingSchema]:
        """List tracking periods configured for a single user.

        See: https://xtracker.polymarket.com/docs
        """
        data = self._request_xtracker(
            f"users/{handle}/trackings",
            params={"platform": platform, "activeOnly": active_only},
        )
        return self.response_to_dataframe(data)

    # ── Tracking endpoints ───────────────────────────────────────────────

    def get_xtracker_trackings(
        self, active_only: bool | None = None
    ) -> DataFrame[XTrackerTrackingSchema]:
        """List all tracking periods across all users.

        Each row represents one Polymarket counter market — the ``title``
        field matches the parent event title and ``marketLink`` points at
        the polymarket.com page.

        See: https://xtracker.polymarket.com/docs
        """
        data = self._request_xtracker("trackings", params={"activeOnly": active_only})
        return self.response_to_dataframe(data)

    def get_xtracker_tracking(self, id: str, include_stats: bool = False) -> XTrackerTracking:
        """Fetch a single tracking period by id.

        When ``include_stats=True``, the response includes a ``stats``
        object containing both aggregate scalars (``total``, ``cumulative``,
        ``pace``, ``percentComplete``, ``daysElapsed``, ``daysRemaining``,
        ``daysTotal``, ``isComplete``) and a ``daily`` time-series array.
        This method materialises ``stats`` as a ``DataFrame`` of the daily
        buckets and surfaces the scalars on ``stats.attrs`` so they're
        accessible without losing the structured shape.

        See: https://xtracker.polymarket.com/docs
        """
        raw = self._request_xtracker(f"trackings/{id}", params={"includeStats": include_stats})
        if include_stats and isinstance(raw, dict) and isinstance(raw.get("stats"), dict):
            stats = raw["stats"]
            daily = stats.pop("daily", []) or []
            df = self.response_to_dataframe(daily)
            df.attrs.update(stats)
            raw["stats"] = df
        return raw

    # ── Metrics endpoint ─────────────────────────────────────────────────

    def get_xtracker_metrics(
        self,
        user_id: str,
        type: str = "daily",
        start_date: str | pd.Timestamp | None = None,
        end_date: str | pd.Timestamp | None = None,
    ) -> DataFrame[XTrackerMetricSchema]:
        """Fetch a user's per-bucket post metrics over a date range.

        The nested ``data`` object on each metric (``count``, ``cumulative``,
        ``trackingId``) is flattened into prefixed columns (``dataCount``,
        ``dataCumulative``, ``dataTrackingId``).

        Args:
            user_id: xtracker internal user id (UUID), as found on
                ``get_xtracker_users()['id']``.
            type: Bucket granularity. ``"daily"`` is the default and only
                documented value.
            start_date: ISO date string or ``pd.Timestamp``.
            end_date: ISO date string or ``pd.Timestamp``.

        See: https://xtracker.polymarket.com/docs
        """
        data = self._request_xtracker(
            f"metrics/{user_id}",
            params={
                "type": type,
                "startDate": _to_iso_date(start_date),
                "endDate": _to_iso_date(end_date),
            },
        )
        df = pd.json_normalize(data, sep="_") if data else pd.DataFrame()
        return self.preprocess_dataframe(df)
