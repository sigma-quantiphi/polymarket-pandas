"""
Market Structures — Polymarket's event shapes, classified and parsed.

Hierarchy: Series → Events → Markets → Tokens. Every event uses one of:

  1. Single-Outcome              — one binary market
  2. negRisk Multi-Outcome       — mutually-exclusive, prices sum→$1
  3. Non-negRisk Multi-Outcome   — independent binaries
  4. Directional / Counter-Based — thresholds on a counter (↑/↓ titles)
  5. Bracketed                   — numeric value carved into ranges

Plus five hand-picked extras that don't surface in top-volume listings:
  6. BTC Up/Down (hourly directional, btc-up-or-down-daily series)
  7-10. Sports — Moneyline / Spreads / Totals / Both Teams to Score

Most of the work (classification, regex parsing of `marketsGroupItemTitle`,
sports event discovery) lives in `polymarket_pandas.parsers` — see that
module for the helpers. This example just orchestrates the discovery and
prints one representative event per structure bucket.

Window dates ARE exposed by the API but split across four columns:

  startTime              event-level counted-window start (e.g. Elon: Apr 3)
  marketsGameStartTime   same value, mirrored per market
  marketsStartDate       order-book open time — NOT the counted window
  marketsEndDate         window end / resolution deadline — CLEARED on resolve
  marketsClosedTime      actual close timestamp, set only after resolution

For resolved markets, `marketsEndDate` is NaT. Use
`coalesce_end_date_from_title` to recover the deadline from the
"Month Day" title string when present.
"""

from __future__ import annotations

import sys

import pandas as pd

from polymarket_pandas import PolymarketPandas
from polymarket_pandas.parsers import (
    classify_event_structure,
    coalesce_end_date_from_title,
    parse_title_bounds,
    parse_title_sports,
)

# Windows consoles default to cp1252, which can't encode ↑ / ↓ / – used in
# Polymarket market titles. Switch stdout to UTF-8 so the script doesn't
# crash mid-loop when it hits a directional/bracketed event.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 240)
pd.set_option("display.max_rows", 40)


SHOW_COLS = [
    "marketsGroupItemTitle",
    "marketsQuestion",
    "marketsOutcomes",
    "marketsOutcomePrices",
    "boundLow",
    "boundHigh",
    "direction",
    "threshold",
    "spreadLine",
    "totalLine",
    "side",
    "startTime",
    "marketsGameStartTime",
    "marketsEndDate",
    "marketsClosedTime",
]

# Zero-padded so labels sort lexically in natural order ("10" after "09").
EXTRAS = [
    ("06. BTC Up/Down (hourly directional)", "btc"),
    ("07. Sports — Moneyline", "moneyline"),
    ("08. Sports — Spreads", "spreads"),
    ("09. Sports — Totals (Over/Under)", "totals"),
    ("10. Sports — Both Teams to Score", "both_teams_to_score"),
]

CORE_LABELS = {
    "Single-Outcome": "01. Single-Outcome",
    "negRisk Multi-Outcome": "02. negRisk Multi-Outcome",
    "Non-negRisk Multi-Outcome": "03. Non-negRisk Multi-Outcome",
    "Directional / Counter-Based": "04. Directional / Counter-Based",
    "Bracketed": "05. Bracketed",
}


def load_events(client: PolymarketPandas) -> pd.DataFrame:
    """Top-volume open events plus the hand-picked extras, tagged with an
    `_override` column so the example loop can label them independently of
    `classify_event_structure`. The override is needed for sports events
    where spreads + totals + BTTS often share the same 'More Markets'
    parent event id."""
    top = client.get_events(
        closed=False,
        limit=300,
        order=["volume"],
        ascending=False,
        expand_markets=True,
        expand_clob_token_ids=False,
    )

    series = client.get_series(slug=["btc-up-or-down-daily"], expand_events=True)
    btc_slug = series["eventsSlug"].dropna().iloc[0]
    btc = client.get_events(slug=[btc_slug], expand_markets=True, expand_clob_token_ids=False)

    parts = [top]
    for label, key in EXTRAS:
        if key == "btc":
            extra = btc
        else:
            extra = client.fetch_sports_event(key)
        if not extra.empty:
            extra["_override"] = label
            parts.append(extra)
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    client = PolymarketPandas()
    df = load_events(client)
    df = pd.concat([df, parse_title_bounds(df), parse_title_sports(df)], axis=1)
    df["structure"] = classify_event_structure(df).map(CORE_LABELS)
    if "_override" in df.columns:
        mask = df["_override"].notna()
        df.loc[mask, "structure"] = df.loc[mask, "_override"]
    df["marketsEndDate"] = coalesce_end_date_from_title(df)

    # First (highest-volume) event in each structure bucket. Filter by
    # (id, structure) together so sports spreads vs totals don't contaminate
    # each other when they share a 'More Markets' parent event.
    examples = df.drop_duplicates(subset="structure").sort_values("structure")[["structure", "id"]]
    for label, ev_id in examples.itertuples(index=False):
        ev = df[(df["id"] == ev_id) & (df["structure"] == label)]
        head = ev.iloc[0]
        print(f"\n{'=' * 78}\n{label}\n{'=' * 78}")
        print(f"event   : {head['title']} ({head['slug']})")
        print(f"markets : {len(ev)}   negRisk: {bool(head['marketsNegRisk'])}")
        displayed = (
            ev.reindex(columns=SHOW_COLS)
            .dropna(how="all", axis=1)
            .dropna(subset=["marketsOutcomePrices"])
        )
        sort_cols = [
            c
            for c in ("threshold", "boundLow", "marketsEndDate", "marketsClosedTime")
            if c in displayed.columns
        ]
        if sort_cols:
            displayed = displayed.sort_values(sort_cols)
        print(displayed.to_string(index=False))

    client.close()


if __name__ == "__main__":
    main()
