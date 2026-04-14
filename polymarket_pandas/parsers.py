"""DataFrame-level enrichers for markets/events DataFrames.

These helpers extract structured fields out of ``marketsGroupItemTitle``,
which Polymarket exposes as a free-text display string ("280-299",
"↑ 200,000", "↑ $120", "Spread -1.5", "O/U 8.5") rather than as typed
columns, and out of ``marketsQuestion`` when the group-title cue is
absent.

The default column names match the shape produced by
``client.get_events(expand_markets=True)`` (event-level rows with
``markets`` -prefixed market columns from
``polymarket_pandas.utils.expand_dataframe``). All column names are
parameters so the same helpers work on raw ``client.get_markets``
output too — pass ``title_col="groupItemTitle"`` etc.

For the multi-call sports discovery helper that used to live here, see
``PolymarketPandas.fetch_sports_event``.
"""

from __future__ import annotations

import pandas as pd


def classify_event_structure(
    data: pd.DataFrame,
    id_col: str = "id",
    condition_id_col: str = "marketsConditionId",
    neg_risk_col: str = "marketsNegRisk",
    title_col: str = "marketsGroupItemTitle",
) -> pd.Series:
    """Per-row label assigning each market to one of Polymarket's five
    event structures.

    Returned values (one per row, aligned to ``data.index``):

    - ``"Single-Outcome"``              — events with one binary market
    - ``"negRisk Multi-Outcome"``       — mutually-exclusive (prices sum→$1)
    - ``"Non-negRisk Multi-Outcome"``   — independent binaries
    - ``"Directional / Counter-Based"`` — thresholds on a counter (↑/↓ titles)
    - ``"Bracketed"``                   — numeric value carved into ranges
      (``20-29``, ``<20``, ``580+``)

    Args:
        data: A DataFrame with one row per (event, market). Typically the
            output of ``client.get_events(expand_markets=True)``. Must
            contain the columns named by ``id_col``, ``condition_id_col``,
            ``neg_risk_col``, and ``title_col``.
        id_col: Event id column. Used to group markets by their parent
            event so the bracket / directional share is computed per-event.
        condition_id_col: Per-market condition id, used as a row-count proxy.
        neg_risk_col: Per-market negRisk flag (bool).
        title_col: Per-market group-item title display string.
    """
    title = data[title_col].fillna("")
    n_markets = data.groupby(id_col)[condition_id_col].transform("count")
    neg_risk = data[neg_risk_col].fillna(False).astype(bool)
    bracket_share = (
        title.str.contains(r"^\s*<|^\s*\d+\s*[-–]\s*\d|\+\s*$", regex=True)
        .groupby(data[id_col])
        .transform("mean")
    )
    directional_share = (
        title.str.contains(r"^\s*[↑↓]", regex=True).groupby(data[id_col]).transform("mean")
    )

    label = pd.Series("Non-negRisk Multi-Outcome", index=data.index)
    label[neg_risk] = "negRisk Multi-Outcome"
    label[directional_share > 0.5] = "Directional / Counter-Based"
    label[bracket_share > 0.5] = "Bracketed"
    label[n_markets == 1] = "Single-Outcome"
    return label


def parse_title_bounds(
    data: pd.DataFrame,
    title_col: str = "marketsGroupItemTitle",
) -> pd.DataFrame:
    """Vectorized extraction of numeric bounds and directional thresholds
    from the title display string.

    Polymarket has no structured field for the bracket bounds or counter
    threshold — they're encoded in the title display string ("280-299",
    "<20", "580+", "↑ 200,000"). This pulls them out into four columns:

    - ``boundLow`` / ``boundHigh`` — float bracket edges. One-sided
      brackets fill the open side with 0 / inf so they sort sensibly.
    - ``direction`` — ``"up"`` / ``"down"`` for ↑/↓ titles, NaN otherwise.
    - ``threshold`` — numeric value following an arrow ("↑ 200,000" → 200000).

    Args:
        data: A DataFrame with one row per market. Must contain ``title_col``.
            Typically used on the output of
            ``client.get_events(expand_markets=True)``.
        title_col: Column holding the title string. Defaults to the
            ``markets`` -prefixed name produced by ``expand_dataframe``;
            pass ``"groupItemTitle"`` for raw ``client.get_markets`` output.

    Returns:
        New DataFrame indexed by ``data.index`` with the four columns above.
        Concatenate via ``pd.concat([data, parse_title_bounds(data)], axis=1)``.
    """
    title = data[title_col].fillna("")
    rng = title.str.extract(r"^\s*([\d.]+)\s*[-–]\s*([\d.]+)").apply(pd.to_numeric, errors="coerce")
    lt = pd.to_numeric(title.str.extract(r"^\s*<\s*([\d.]+)")[0], errors="coerce")
    gt = pd.to_numeric(
        title.str.extract(r"^\s*(?:>|≥|>=)\s*([\d.]+)")[0].fillna(
            title.str.extract(r"^\s*([\d.]+)\s*\+\s*$")[0]
        ),
        errors="coerce",
    )
    # Allow an optional currency prefix so "↑ $120" parses the same as "↑ 200,000".
    arrow = title.str.extract(r"^\s*([↑↓])\s*\$?([\d,.]+)")
    has_bounds = rng[0].notna() | rng[1].notna() | lt.notna() | gt.notna()
    bound_low = (
        rng[0].combine_first(gt).where(~has_bounds, other=rng[0].combine_first(gt).fillna(0))
    )
    bound_high = (
        rng[1]
        .combine_first(lt)
        .where(~has_bounds, other=rng[1].combine_first(lt).fillna(float("inf")))
    )
    return pd.DataFrame(
        {
            "boundLow": bound_low,
            "boundHigh": bound_high,
            "direction": arrow[0].map({"↑": "up", "↓": "down"}),
            "threshold": pd.to_numeric(arrow[1].str.replace(",", "", regex=False), errors="coerce"),
        },
        index=data.index,
    )


def parse_title_sports(
    data: pd.DataFrame,
    title_col: str = "marketsGroupItemTitle",
) -> pd.DataFrame:
    """Vectorized extraction of spread / over-under line from sports
    market titles.

    Polymarket has no structured spread/total field on sports markets —
    the value is encoded in the title string ("Spread -1.5", "O/U 8.5",
    "Over 2.5"). Returns:

    - ``spreadLine`` — signed float from "Spread -1.5". Named ``spreadLine``
      (not ``spread``) to avoid colliding with ``MarketSchema.spread``,
      which is an unrelated API field.
    - ``totalLine`` — float from "O/U 8.5", "Over 2.5", "Under 2.5".
    - ``side`` — ``"over"`` / ``"under"`` when the title spells it out,
      NaN for compact "O/U" forms.

    Args:
        data: A DataFrame with one row per market. Must contain ``title_col``.
        title_col: Column holding the title string. Defaults to the
            ``markets`` -prefixed name produced by ``expand_dataframe``;
            pass ``"groupItemTitle"`` for raw ``client.get_markets`` output.

    Returns:
        New DataFrame indexed by ``data.index`` with three columns:
        ``spreadLine``, ``totalLine``, ``side``.
    """
    title = data[title_col].fillna("")
    spread_line = pd.to_numeric(
        title.str.extract(r"(?i)spread\s*([+-]?\d+(?:\.\d+)?)")[0],
        errors="coerce",
    )
    total_line = pd.to_numeric(
        title.str.extract(r"(?i)(?:o/u|over|under|total)\s*([+-]?\d+(?:\.\d+)?)")[0],
        errors="coerce",
    )
    side = title.str.extract(r"(?i)\b(over|under)\b")[0].str.lower()
    return pd.DataFrame(
        {"spreadLine": spread_line, "totalLine": total_line, "side": side},
        index=data.index,
    )


def coalesce_end_date_from_title(
    data: pd.DataFrame,
    title_col: str = "marketsGroupItemTitle",
    start_col: str = "marketsStartDate",
    end_col: str = "marketsEndDate",
) -> pd.Series:
    """Fill NaT entries in ``end_col`` by parsing the ``title_col`` string.

    Polymarket clears ``marketsEndDate`` after a market resolves, but for
    bracketed / directional events the deadline is encoded in the title
    as a "Month Day" label ("April 7", "March 2"). This parses that label
    back into a UTC timestamp, inferring the year from ``start_col`` and
    bumping by one year for Dec→Jan rollovers.

    Args:
        data: A DataFrame with one row per market. Must contain the three
            columns named by ``title_col``, ``start_col``, and ``end_col``.
        title_col: Column holding the title display string.
        start_col: Column holding the order-book start timestamp,
            used to infer the year for the parsed Month/Day.
        end_col: Column holding the existing end-date timestamps. Non-NaT
            values are preserved; NaT values are filled from the title.
            Defaults match the ``markets`` -prefixed shape from
            ``client.get_events(expand_markets=True)``; pass the unprefixed
            equivalents (``"groupItemTitle"``, ``"startDate"``, ``"endDate"``)
            for raw ``client.get_markets`` output.

    Returns:
        A copy of ``data[end_col]`` with NaT entries filled where the
        title could be parsed. Existing non-NaT values are preserved.
    """
    title = data[title_col].fillna("").str.strip()
    start = pd.to_datetime(data[start_col], utc=True, errors="coerce")
    # Parse "<title> <start year>" — masked to NaT where title is empty
    # (otherwise " 2026" would parse to Jan 1 2026).
    parsed = pd.to_datetime(
        title + " " + start.dt.year.astype("Int64").astype(str),
        errors="coerce",
        utc=True,
    ).where(title != "")
    # Vectorized Dec→Jan rollover: if the parsed date lands before start,
    # bump the year by one. NaT rows pass through untouched.
    parsed = parsed.where(
        parsed.isna() | start.isna() | (parsed >= start),
        parsed + pd.DateOffset(years=1),
    )
    return data[end_col].fillna(parsed)


def parse_title_threshold(
    data: pd.DataFrame,
    title_col: str = "marketsQuestion",
    group_title_col: str | None = "marketsGroupItemTitle",
) -> pd.DataFrame:
    """Vectorized extraction of a numeric threshold and cross direction
    for threshold-crossing binary markets.

    Targets weekly/daily price-target series such as
    ``will-nflx-hit-week-of-*`` ("Will NFLX hit (HIGH) $120…", group
    title ``↑ $120``) and ``what-price-will-solana-hit-on-*`` ("Will
    Solana dip to $65…", group title ``↓ 65``) — markets where the
    question is "does the underlying end up *above* or *below* a
    numeric threshold by the resolution time?".

    Extraction order per row:

    1. ``group_title_col`` arrow form ``↑ $120`` / ``↓ 65`` — reuses
       :func:`parse_title_bounds`. Cheapest when populated.
    2. ``title_col`` currency form — ``$N`` in the free-text question.
       Direction is inferred from explicit ``(LOW)`` / ``(HIGH)``
       annotations first, then from keywords (``dip`` / ``drop`` /
       ``fall`` / ``below`` / ``under`` → ``"below"``; ``hit`` /
       ``reach`` / ``exceed`` / ``above`` / ``over`` / ``rise`` →
       ``"above"``).

    Args:
        data: A DataFrame with one row per market. Must contain
            ``title_col``; ``group_title_col`` is optional (pass
            ``None`` to skip the arrow fast path).
        title_col: Column holding the free-text question. Defaults to
            the ``markets`` -prefixed name produced by
            ``expand_dataframe``; pass ``"question"`` for raw
            ``client.get_markets`` output.
        group_title_col: Column holding the compact display string.
            Defaults to the ``markets`` -prefixed name produced by
            ``expand_dataframe``.

    Returns:
        New DataFrame indexed by ``data.index`` with two columns:

        - ``thresholdPrice`` — ``float`` numeric level (e.g. ``65.0``,
          ``97.5``, ``200000.0``). NaN when no threshold could be parsed.
        - ``thresholdDirection`` — ``"above"`` or ``"below"`` for
          markets that resolve YES when the underlying ends above /
          below the threshold. NaN when direction could not be inferred.

        Concatenate via
        ``pd.concat([data, parse_title_threshold(data)], axis=1)``.
    """
    # 1. Fast path: the arrow form in group_title_col.
    threshold = pd.Series(pd.NA, index=data.index, dtype="Float64")
    direction = pd.Series(pd.NA, index=data.index, dtype="string")

    if group_title_col is not None and group_title_col in data.columns:
        bounds = parse_title_bounds(data, title_col=group_title_col)
        threshold = pd.to_numeric(bounds["threshold"], errors="coerce")
        direction = bounds["direction"].map({"up": "above", "down": "below"})

    # 2. Fallback: parse the free-text question for unresolved rows.
    question = (
        data[title_col].fillna("") if title_col in data.columns else pd.Series("", index=data.index)
    )

    # Direction from explicit (LOW)/(HIGH) wins over loose keywords because
    # "Will NFLX hit (LOW) $97.50" means the price drops to the low, not rises.
    q_lower = question.str.lower()
    low_hit = q_lower.str.contains(r"\(low\)", regex=True, na=False)
    high_hit = q_lower.str.contains(r"\(high\)", regex=True, na=False)
    dip_hit = q_lower.str.contains(r"\b(?:dip|drop|fall|below|under)\b", regex=True, na=False)
    reach_hit = q_lower.str.contains(
        r"\b(?:hit|reach|exceed|above|over|rise)\b", regex=True, na=False
    )

    inferred_direction = pd.Series(pd.NA, index=data.index, dtype="string")
    inferred_direction = inferred_direction.mask(reach_hit, "above")
    inferred_direction = inferred_direction.mask(dip_hit, "below")
    inferred_direction = inferred_direction.mask(high_hit, "above")
    inferred_direction = inferred_direction.mask(low_hit, "below")
    direction = direction.fillna(inferred_direction)

    # Threshold from first currency token in the question.
    q_amount = question.str.extract(r"\$\s*([\d,]+(?:\.\d+)?)")[0]
    q_amount_num = pd.to_numeric(q_amount.str.replace(",", "", regex=False), errors="coerce")
    threshold = threshold.fillna(q_amount_num)

    return pd.DataFrame(
        {
            "thresholdPrice": pd.to_numeric(threshold, errors="coerce"),
            "thresholdDirection": direction,
        },
        index=data.index,
    )
