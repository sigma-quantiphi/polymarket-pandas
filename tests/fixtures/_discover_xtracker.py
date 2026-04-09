"""Capture sample responses from every public xtracker endpoint.

Run from the repo root:

    python tests/fixtures/_discover_xtracker.py

Writes one JSON file per endpoint into ``tests/fixtures/xtracker_*.json`` and
prints the field names found inside each response so we can build the
Pandera schemas without guessing.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://xtracker.polymarket.com/api"
FIXTURES = Path(__file__).parent


def fetch(client: httpx.Client, label: str, path: str, params: dict | None = None) -> dict:
    print(f"\nGET {path}  params={params}")
    resp = client.get(f"{BASE}{path}", params=params)
    print(f"  status {resp.status_code}  type {resp.headers.get('content-type')}")
    resp.raise_for_status()
    payload = resp.json()
    out = FIXTURES / f"xtracker_{label}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  wrote {out.relative_to(FIXTURES.parent.parent)}")
    return payload


def show_fields(label: str, payload: dict) -> None:
    print(f"\n--- {label} ---")
    if not isinstance(payload, dict):
        print(f"  not a dict: {type(payload).__name__}")
        return
    print(f"  envelope keys: {list(payload.keys())}")
    data = payload.get("data", payload)
    if isinstance(data, list):
        if data:
            sample = data[0]
            if isinstance(sample, dict):
                print(f"  list of {len(data)} items, sample keys: {list(sample.keys())}")
            else:
                print(f"  list of {len(data)} items, sample: {sample!r}")
        else:
            print("  empty list")
    elif isinstance(data, dict):
        print(f"  dict keys: {list(data.keys())}")
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                print(f"    {k}: list[{len(v)}] sample keys = {list(v[0].keys())}")
            elif isinstance(v, dict):
                print(f"    {k}: dict keys = {list(v.keys())}")
    else:
        print(f"  scalar: {data!r}")


def main() -> None:
    today = datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)
    fortnight_ago = today - timedelta(days=14)

    with httpx.Client(timeout=30.0) as c:
        # 1. /users — list, then pull a handle for downstream calls
        users = fetch(c, "users", "/users", params={"platform": "X"})
        show_fields("users", users)

        users_data = users.get("data", users)
        first_handle = None
        if isinstance(users_data, list) and users_data:
            first = users_data[0]
            if isinstance(first, dict):
                first_handle = first.get("handle") or first.get("username")
        print(f"\n  first_handle = {first_handle!r}")

        if first_handle:
            # 2. /users/{handle}
            user = fetch(c, "user", f"/users/{first_handle}", params={"platform": "X"})
            show_fields("user", user)

            # 3. /users/{handle}/posts
            posts = fetch(
                c,
                "user_posts",
                f"/users/{first_handle}/posts",
                params={
                    "platform": "X",
                    "startDate": week_ago.isoformat(),
                    "endDate": today.isoformat(),
                    "timezone": "EST",
                },
            )
            show_fields("user_posts", posts)

            # 4. /users/{handle}/trackings
            user_trk = fetch(
                c,
                "user_trackings",
                f"/users/{first_handle}/trackings",
                params={"activeOnly": "true"},
            )
            show_fields("user_trackings", user_trk)

        # 5. /trackings — pull an id for the single-tracking call
        trackings = fetch(c, "trackings", "/trackings", params={"activeOnly": "true"})
        show_fields("trackings", trackings)

        trk_data = trackings.get("data", trackings)
        first_tracking_id = None
        first_user_id = None
        if isinstance(trk_data, list) and trk_data:
            first_trk = trk_data[0]
            if isinstance(first_trk, dict):
                first_tracking_id = first_trk.get("id") or first_trk.get("trackingId")
                first_user_id = first_trk.get("userId") or first_trk.get("user_id")
        print(f"\n  first_tracking_id = {first_tracking_id!r}")
        print(f"  first_user_id = {first_user_id!r}")

        if first_tracking_id:
            # 6. /trackings/{id}?includeStats=true — most interesting (daily array)
            tracking = fetch(
                c,
                "tracking",
                f"/trackings/{first_tracking_id}",
                params={"includeStats": "true"},
            )
            show_fields("tracking", tracking)

        if first_user_id:
            # 7. /metrics/{userId}
            metrics = fetch(
                c,
                "metrics",
                f"/metrics/{first_user_id}",
                params={
                    "type": "daily",
                    "startDate": fortnight_ago.isoformat(),
                    "endDate": today.isoformat(),
                },
            )
            show_fields("metrics", metrics)


if __name__ == "__main__":
    main()
