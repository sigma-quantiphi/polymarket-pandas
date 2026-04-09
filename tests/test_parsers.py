"""Unit tests for polymarket_pandas.parsers — pure DataFrame helpers."""

import pandas as pd

from polymarket_pandas.parsers import (
    classify_event_structure,
    coalesce_end_date_from_title,
    parse_title_bounds,
    parse_title_sports,
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
