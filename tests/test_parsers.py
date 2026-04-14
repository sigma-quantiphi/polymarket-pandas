"""Unit tests for polymarket_pandas.parsers — pure DataFrame helpers."""

import pandas as pd

from polymarket_pandas.parsers import (
    classify_event_structure,
    coalesce_end_date_from_title,
    parse_title_bounds,
    parse_title_sports,
    parse_title_threshold,
)

# ── classify_event_structure ─────────────────────────────────────────────────


def _row(*, id: int, cond: str, neg_risk: bool, title: str) -> dict:
    return {
        "id": id,
        "marketsConditionId": cond,
        "marketsNegRisk": neg_risk,
        "marketsGroupItemTitle": title,
    }


def _events_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal events DataFrame with the columns the classifier
    needs."""
    return pd.DataFrame(rows)


def test_classify_single_outcome():
    df = _events_df([_row(id=1, cond="0xa", neg_risk=False, title="")])
    assert classify_event_structure(df).iloc[0] == "Single-Outcome"


def test_classify_neg_risk_multi_outcome():
    df = _events_df(
        [
            _row(id=1, cond="0xa", neg_risk=True, title="Trump"),
            _row(id=1, cond="0xb", neg_risk=True, title="Harris"),
        ]
    )
    assert (classify_event_structure(df) == "negRisk Multi-Outcome").all()


def test_classify_non_neg_risk_multi_outcome():
    df = _events_df(
        [
            _row(id=1, cond="0xa", neg_risk=False, title="March 2"),
            _row(id=1, cond="0xb", neg_risk=False, title="March 6"),
        ]
    )
    assert (classify_event_structure(df) == "Non-negRisk Multi-Outcome").all()


def test_classify_directional():
    df = _events_df(
        [
            _row(id=1, cond="0xa", neg_risk=False, title="↑ 200,000"),
            _row(id=1, cond="0xb", neg_risk=False, title="↓ 100,000"),
        ]
    )
    assert (classify_event_structure(df) == "Directional / Counter-Based").all()


def test_classify_bracketed():
    df = _events_df(
        [
            _row(id=1, cond="0xa", neg_risk=False, title="<20"),
            _row(id=1, cond="0xb", neg_risk=False, title="20-29"),
            _row(id=1, cond="0xc", neg_risk=False, title="580+"),
        ]
    )
    assert (classify_event_structure(df) == "Bracketed").all()


# ── parse_title_bounds ───────────────────────────────────────────────────────


def test_parse_title_bounds_range():
    df = pd.DataFrame({"marketsGroupItemTitle": ["20-29"]})
    out = parse_title_bounds(df)
    assert out.loc[0, "boundLow"] == 20
    assert out.loc[0, "boundHigh"] == 29


def test_parse_title_bounds_less_than():
    df = pd.DataFrame({"marketsGroupItemTitle": ["<20"]})
    out = parse_title_bounds(df)
    assert out.loc[0, "boundLow"] == 0
    assert out.loc[0, "boundHigh"] == 20


def test_parse_title_bounds_plus():
    df = pd.DataFrame({"marketsGroupItemTitle": ["580+"]})
    out = parse_title_bounds(df)
    assert out.loc[0, "boundLow"] == 580
    assert out.loc[0, "boundHigh"] == float("inf")


def test_parse_title_bounds_directional():
    df = pd.DataFrame({"marketsGroupItemTitle": ["↑ 200,000", "↓ 100,000"]})
    out = parse_title_bounds(df)
    assert out.loc[0, "direction"] == "up"
    assert out.loc[0, "threshold"] == 200000
    assert out.loc[1, "direction"] == "down"
    assert out.loc[1, "threshold"] == 100000


def test_parse_title_bounds_directional_currency_prefix():
    # Regression: NFLX weekly titles carry a "$" prefix after the arrow.
    df = pd.DataFrame({"marketsGroupItemTitle": ["↑ $120", "↓ $97.50"]})
    out = parse_title_bounds(df)
    assert out.loc[0, "direction"] == "up"
    assert out.loc[0, "threshold"] == 120
    assert out.loc[1, "direction"] == "down"
    assert out.loc[1, "threshold"] == 97.5


def test_parse_title_bounds_empty():
    df = pd.DataFrame({"marketsGroupItemTitle": ["", None]})
    out = parse_title_bounds(df)
    assert out["boundLow"].isna().all()
    assert out["boundHigh"].isna().all()
    assert out["direction"].isna().all()
    assert out["threshold"].isna().all()


# ── parse_title_sports ───────────────────────────────────────────────────────


def test_parse_title_sports_spread():
    df = pd.DataFrame({"marketsGroupItemTitle": ["Spread -1.5", "Spread +4.5"]})
    out = parse_title_sports(df)
    assert out.loc[0, "spreadLine"] == -1.5
    assert out.loc[1, "spreadLine"] == 4.5


def test_parse_title_sports_ou_compact():
    df = pd.DataFrame({"marketsGroupItemTitle": ["O/U 8.5"]})
    out = parse_title_sports(df)
    assert out.loc[0, "totalLine"] == 8.5
    assert pd.isna(out.loc[0, "side"])


def test_parse_title_sports_over_under_words():
    df = pd.DataFrame({"marketsGroupItemTitle": ["Over 2.5", "Under 2.5"]})
    out = parse_title_sports(df)
    assert out.loc[0, "totalLine"] == 2.5
    assert out.loc[0, "side"] == "over"
    assert out.loc[1, "side"] == "under"


def test_parse_title_sports_no_match():
    df = pd.DataFrame({"marketsGroupItemTitle": ["Both Teams to Score", "76ers"]})
    out = parse_title_sports(df)
    assert out["spreadLine"].isna().all()
    assert out["totalLine"].isna().all()
    assert out["side"].isna().all()


# ── coalesce_end_date_from_title ─────────────────────────────────────────────


def test_coalesce_end_date_fills_nat():
    df = pd.DataFrame(
        {
            "marketsGroupItemTitle": ["April 7"],
            "marketsStartDate": [pd.Timestamp("2026-03-24", tz="UTC")],
            "marketsEndDate": [pd.NaT],
        }
    )
    result = coalesce_end_date_from_title(df)
    assert result.iloc[0] == pd.Timestamp("2026-04-07", tz="UTC")


def test_coalesce_end_date_keeps_existing():
    existing = pd.Timestamp("2026-04-15", tz="UTC")
    df = pd.DataFrame(
        {
            "marketsGroupItemTitle": ["April 7"],
            "marketsStartDate": [pd.Timestamp("2026-03-24", tz="UTC")],
            "marketsEndDate": [existing],
        }
    )
    result = coalesce_end_date_from_title(df)
    assert result.iloc[0] == existing


def test_coalesce_end_date_dec_to_jan_rollover():
    """A start date in late December and a 'January N' title should bump
    the parsed year by one."""
    df = pd.DataFrame(
        {
            "marketsGroupItemTitle": ["January 5"],
            "marketsStartDate": [pd.Timestamp("2025-12-28", tz="UTC")],
            "marketsEndDate": [pd.NaT],
        }
    )
    result = coalesce_end_date_from_title(df)
    assert result.iloc[0] == pd.Timestamp("2026-01-05", tz="UTC")


def test_coalesce_end_date_empty_title():
    df = pd.DataFrame(
        {
            "marketsGroupItemTitle": [""],
            "marketsStartDate": [pd.Timestamp("2026-03-24", tz="UTC")],
            "marketsEndDate": [pd.NaT],
        }
    )
    result = coalesce_end_date_from_title(df)
    assert pd.isna(result.iloc[0])


# ── parse_title_threshold ────────────────────────────────────────────────────


def test_parse_title_threshold_sol_arrow_form():
    df = pd.DataFrame(
        {
            "marketsQuestion": [
                "Will Solana dip to $65 on April 14?",
                "Will Solana reach $110 on April 14?",
            ],
            "marketsGroupItemTitle": ["↓ 65", "↑ 110"],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdPrice"] == 65
    assert out.loc[0, "thresholdDirection"] == "below"
    assert out.loc[1, "thresholdPrice"] == 110
    assert out.loc[1, "thresholdDirection"] == "above"


def test_parse_title_threshold_nflx_currency_arrow():
    df = pd.DataFrame(
        {
            "marketsQuestion": [
                "Will Netflix, Inc. (NFLX) hit (LOW) $97.50 Week of April 13 2026?",
                "Will Netflix, Inc. (NFLX) hit (HIGH) $120 Week of April 13 2026?",
            ],
            "marketsGroupItemTitle": ["↓ $97.50", "↑ $120"],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdPrice"] == 97.5
    assert out.loc[0, "thresholdDirection"] == "below"
    assert out.loc[1, "thresholdPrice"] == 120
    assert out.loc[1, "thresholdDirection"] == "above"


def test_parse_title_threshold_question_only_fallback():
    # group_title_col empty → fall back to question parsing.
    df = pd.DataFrame(
        {
            "marketsQuestion": [
                "Will Solana dip to $65 on April 14?",
                "Will Netflix, Inc. (NFLX) hit (LOW) $97.50 Week of April 13 2026?",
                "Will NFLX reach $1100 by Friday?",
            ],
            "marketsGroupItemTitle": ["", "", ""],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdPrice"] == 65
    assert out.loc[0, "thresholdDirection"] == "below"  # "dip"
    assert out.loc[1, "thresholdPrice"] == 97.5
    assert out.loc[1, "thresholdDirection"] == "below"  # "(LOW)" wins over "hit"
    assert out.loc[2, "thresholdPrice"] == 1100
    assert out.loc[2, "thresholdDirection"] == "above"  # "reach"


def test_parse_title_threshold_low_high_annotation_overrides_keyword():
    # "hit (LOW)" must resolve to below even though "hit" alone would imply above.
    df = pd.DataFrame(
        {
            "marketsQuestion": ["Will NFLX hit (LOW) $95 this week?"],
            "marketsGroupItemTitle": [""],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdDirection"] == "below"


def test_parse_title_threshold_commas_in_threshold():
    df = pd.DataFrame(
        {
            "marketsQuestion": ["Will BTC hit $200,000 by year end?"],
            "marketsGroupItemTitle": [""],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdPrice"] == 200000


def test_parse_title_threshold_no_match_returns_nan():
    df = pd.DataFrame(
        {
            "marketsQuestion": ["Will something qualitative happen?"],
            "marketsGroupItemTitle": [""],
        }
    )
    out = parse_title_threshold(df)
    assert pd.isna(out.loc[0, "thresholdPrice"])
    assert pd.isna(out.loc[0, "thresholdDirection"])


def test_parse_title_threshold_group_title_wins_over_question():
    # Arrow form is cheaper + already-structured; should beat question parsing.
    df = pd.DataFrame(
        {
            # Question says "reach" (→above) but the arrow says ↓ (→below).
            # Arrow wins because it's the structured display Polymarket sets
            # on the grouped market row.
            "marketsQuestion": ["Will SOL reach $65?"],
            "marketsGroupItemTitle": ["↓ 65"],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdDirection"] == "below"
    assert out.loc[0, "thresholdPrice"] == 65


def test_parse_title_threshold_none_group_col_skips_fast_path():
    df = pd.DataFrame({"marketsQuestion": ["Will X dip to $42 on Monday?"]})
    out = parse_title_threshold(df, group_title_col=None)
    assert out.loc[0, "thresholdPrice"] == 42
    assert out.loc[0, "thresholdDirection"] == "below"


def test_parse_title_threshold_mode_touch_vs_close():
    df = pd.DataFrame(
        {
            "marketsQuestion": [
                "Will NFLX hit (HIGH) $120 this week?",       # (HIGH) → touch
                "Will Solana dip to $65 on April 14?",         # dip → touch
                "Will BTC reach $200,000 by year end?",        # reach → touch
                "Will ETH close above $5000 on Friday?",       # close → close
                "Will SPX settle above 6000 at resolution?",   # settle → close
                "Will something qualitative happen?",          # neither → NaN
                "Will SOL be above $100?",                     # bare "above" → NaN
            ],
            "marketsGroupItemTitle": ["", "", "", "", "", "", ""],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdMode"] == "touch"
    assert out.loc[1, "thresholdMode"] == "touch"
    assert out.loc[2, "thresholdMode"] == "touch"
    assert out.loc[3, "thresholdMode"] == "close"
    assert out.loc[4, "thresholdMode"] == "close"
    assert pd.isna(out.loc[5, "thresholdMode"])
    assert pd.isna(out.loc[6, "thresholdMode"])


def test_parse_title_threshold_arrow_only_leaves_mode_nan():
    # Arrow form alone has no resolution-style cue.
    df = pd.DataFrame(
        {
            "marketsQuestion": ["", ""],
            "marketsGroupItemTitle": ["↑ $120", "↓ 65"],
        }
    )
    out = parse_title_threshold(df)
    assert out.loc[0, "thresholdDirection"] == "above"
    assert out.loc[1, "thresholdDirection"] == "below"
    assert pd.isna(out.loc[0, "thresholdMode"])
    assert pd.isna(out.loc[1, "thresholdMode"])


def test_parse_title_threshold_custom_column_names():
    # Raw client.get_markets output uses unprefixed column names.
    df = pd.DataFrame(
        {
            "question": ["Will SOL dip to $50?"],
            "groupItemTitle": ["↓ 50"],
        }
    )
    out = parse_title_threshold(df, title_col="question", group_title_col="groupItemTitle")
    assert out.loc[0, "thresholdPrice"] == 50
    assert out.loc[0, "thresholdDirection"] == "below"
