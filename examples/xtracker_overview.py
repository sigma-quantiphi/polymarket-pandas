"""
XTracker Overview — Query all seven xtracker.polymarket.com endpoints

Explores the post-counter tracking service that powers Polymarket's
"# tweets / # posts in window" markets (Elon, Trump, Zelenskyy, etc.).

  1. get_xtracker_users          — all tracked users (with stats)
  2. get_xtracker_user           — single user detail
  3. get_xtracker_user_posts     — posts for a user in a date range
  4. get_xtracker_user_trackings — tracking periods for a user
  5. get_xtracker_trackings      — all tracking periods (active only)
  6. get_xtracker_tracking       — single tracking period with stats
  7. get_xtracker_metrics        — daily post metrics for a user

No authentication required — all endpoints are public.

Usage:
    python examples/xtracker_overview.py
    python examples/xtracker_overview.py elonmusk           # specific handle
    python examples/xtracker_overview.py elonmusk 2026-04-01 2026-04-10
"""

from __future__ import annotations

import sys

import pandas as pd

from polymarket_pandas import PolymarketPandas

pd.set_option("display.max_columns", 12)
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 20)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    client = PolymarketPandas()

    handle = sys.argv[1] if len(sys.argv) > 1 else None
    start_date = pd.Timestamp(sys.argv[2], tz="UTC") if len(sys.argv) > 2 else None
    end_date = pd.Timestamp(sys.argv[3], tz="UTC") if len(sys.argv) > 3 else None

    # ── 1. All tracked users (with aggregate stats) ──────────────────
    section("1. get_xtracker_users(stats=True, expand_count=True)")
    users = client.get_xtracker_users(stats=True, expand_trackings=True, expand_count=True)
    print(users)
    print(users.dtypes.to_string())

    # Pick a handle to drill into if not provided via CLI.
    if handle is None and not users.empty:
        handle = users["handle"].iloc[0]
        print(f"\nAuto-selected handle: {handle!r}")

    if handle is None:
        print("No tracked users found; nothing to drill into.")
        client.close()
        return

    # ── 2. Single user detail ────────────────────────────────────────
    section(f"2. get_xtracker_user(handle={handle!r})")
    user = client.get_xtracker_user(handle)
    for k, v in user.items():
        print(f"  {k}: {v}")

    user_id = user.get("id")

    # ── 3. Posts for the user in a date range ────────────────────────
    # Default: last 7 days as pd.Timestamps (the API accepts them natively).
    today = pd.Timestamp.now(tz="UTC").normalize()
    end_date = end_date or today
    start_date = start_date or today - pd.Timedelta(days=7)
    window = f"start_date={start_date}, end_date={end_date}"

    section(f"3. get_xtracker_user_posts(handle={handle!r}, {window})")
    posts = client.get_xtracker_user_posts(handle=handle, start_date=start_date, end_date=end_date)
    print(f"Posts returned: {len(posts)}")
    print(posts)
    if not posts.empty:
        print(posts.dtypes.to_string())

    # ── 4. Tracking periods for the user ─────────────────────────────
    section(f"4. get_xtracker_user_trackings(handle={handle!r})")
    user_trackings = client.get_xtracker_user_trackings(handle=handle)
    print(user_trackings)
    if not user_trackings.empty:
        print(user_trackings.dtypes.to_string())

    # ── 5. All active tracking periods ───────────────────────────────
    section("5. get_xtracker_trackings(active_only=True, expand_user=True)")
    trackings = client.get_xtracker_trackings(active_only=True, expand_user=True)
    print(trackings)
    if not trackings.empty:
        print(trackings.dtypes.to_string())

    # ── 6. Single tracking period with stats ─────────────────────────
    # Use the first tracking from the user, or fall back to global list.
    tracking_id = None
    if not user_trackings.empty and "id" in user_trackings.columns:
        tracking_id = user_trackings["id"].iloc[0]
    elif not trackings.empty and "id" in trackings.columns:
        tracking_id = trackings["id"].iloc[0]

    section(f"6. get_xtracker_tracking(id={tracking_id!r}, include_stats=True)")
    if tracking_id:
        tracking = client.get_xtracker_tracking(tracking_id, include_stats=True)
        for k, v in tracking.items():
            if k == "stats" and hasattr(v, "attrs"):
                print(f"  stats (scalars): {v.attrs}")
                print(f"  stats (daily):\n{v}")
            else:
                print(f"  {k}: {v}")
    else:
        print("(skipped — no tracking_id available)")

    # ── 7. Daily post metrics for the user ───────────────────────────
    section(
        f"7. get_xtracker_metrics(user_id={user_id!r}, "
        f"start_date={start_date!r}, end_date={end_date!r})"
    )
    if user_id:
        metrics = client.get_xtracker_metrics(
            user_id=user_id, start_date=start_date, end_date=end_date
        )
        print(metrics)
        if not metrics.empty:
            print(metrics.dtypes.to_string())
    else:
        print("(skipped — no user_id available)")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
