"""
Integration tests for PolymarketPandas — hit live APIs, no mocking.

Run with:
    pytest tests/test_integration.py -v
"""

import os
import time as _time

import pandas as pd
import pytest

from polymarket_pandas import PolymarketPandas
from polymarket_pandas.schemas import (
    ActivitySchema,
    BridgeSupportedAssetSchema,
    BuilderLeaderboardSchema,
    BuilderTradeSchema,
    BuilderVolumeSchema,
    ClosedPositionSchema,
    CommentSchema,
    CurrentRewardSchema,
    DataTradeSchema,
    EventSchema,
    LastTradePricesSchema,
    LeaderboardSchema,
    MarketPriceSchema,
    MarketSchema,
    MidpointSchema,
    OrderbookSchema,
    PositionSchema,
    PositionValueSchema,
    PriceHistorySchema,
    RewardsMarketMultiSchema,
    RewardsMarketSchema,
    SamplingMarketSchema,
    SeriesSchema,
    SimplifiedMarketSchema,
    SportsMetadataSchema,
    TagSchema,
    TeamSchema,
    XTrackerDailyStatSchema,
    XTrackerMetricSchema,
    XTrackerPostSchema,
    XTrackerTrackingSchema,
    XTrackerUserSchema,
)

# ---------------------------------------------------------------------------
# Session-scoped fixtures — expensive API calls run once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client() -> PolymarketPandas:
    return PolymarketPandas(use_tqdm=False)


@pytest.fixture(scope="session")
def builder_client() -> PolymarketPandas:
    from dotenv import load_dotenv

    load_dotenv()
    required = (
        "POLYMARKET_BUILDER_API_KEY",
        "POLYMARKET_BUILDER_API_SECRET",
        "POLYMARKET_BUILDER_API_PASSPHRASE",
    )
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        pytest.skip(f"Builder credentials not set: {', '.join(missing)}")
    return PolymarketPandas(use_tqdm=False)


@pytest.fixture(scope="session")
def crypto_slugs(client: PolymarketPandas) -> list[str]:
    series = client.get_series(expand_events=True, expand_event_tags=True)
    assert isinstance(series, pd.DataFrame)
    assert not series.empty

    active = series.loc[
        (series["eventsEndDate"] >= pd.Timestamp.now(tz="UTC")) & ~series["eventsClosed"]
    ].query("active")
    assert not active.empty, "No active crypto series found — check market data"

    crypto = active.loc[active["slug"].str.contains("btc|eth|sol|xrp|doge")]
    slugs = crypto["eventsSlug"].unique().tolist()[:200]
    assert slugs, "No crypto event slugs found"
    return slugs


@pytest.fixture(scope="session")
def markets(client: PolymarketPandas, crypto_slugs: list[str]) -> pd.DataFrame:
    _time.sleep(1)
    df = client.get_markets(slug=crypto_slugs, expand_clob_token_ids=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    return df


@pytest.fixture(scope="session")
def events(client: PolymarketPandas, crypto_slugs: list[str]) -> pd.DataFrame:
    _time.sleep(1)
    df = client.get_events(slug=crypto_slugs, expand_markets=True, expand_clob_token_ids=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    return df


@pytest.fixture(scope="session")
def token(markets: pd.DataFrame) -> str:
    return str(markets["clobTokenIds"].iloc[0])


@pytest.fixture(scope="session")
def active_token_ids(events: pd.DataFrame) -> pd.DataFrame:
    active = events.loc[
        (events["marketsStartDate"] <= pd.Timestamp.now(tz="UTC"))
        & ~events["marketsClosed"]
        & events["marketsActive"]
    ]
    return (
        active[["marketsClobTokenIds"]]
        .rename(columns={"marketsClobTokenIds": "token_id"})
        .head(400)
    )


@pytest.fixture(scope="session")
def market_id(markets: pd.DataFrame) -> int:
    """A numeric market ID for by-id lookups."""
    return int(markets["id"].iloc[0])


@pytest.fixture(scope="session")
def market_slug(markets: pd.DataFrame) -> str:
    """A market slug for by-slug lookups."""
    return str(markets["slug"].iloc[0])


@pytest.fixture(scope="session")
def event_id(events: pd.DataFrame) -> int:
    """A numeric event ID for by-id lookups."""
    return int(events["id"].iloc[0])


@pytest.fixture(scope="session")
def event_slug(events: pd.DataFrame) -> str:
    """An event slug for by-slug lookups."""
    return str(events["slug"].iloc[0])


@pytest.fixture(scope="session")
def tags_row(client: PolymarketPandas) -> pd.Series:
    """First tag row — provides both id and slug."""
    tags = client.get_tags(limit=1)
    return tags.iloc[0]


@pytest.fixture(scope="session")
def tag_id(tags_row: pd.Series) -> int:
    """A tag ID for by-id lookups."""
    return int(tags_row["id"])


@pytest.fixture(scope="session")
def tag_slug(tags_row: pd.Series) -> str:
    """A tag slug for by-slug lookups."""
    return str(tags_row["slug"])


@pytest.fixture(scope="session")
def condition_id(markets: pd.DataFrame) -> str:
    """A condition ID for reward/CLOB lookups."""
    return str(markets["conditionId"].iloc[0])


@pytest.fixture(scope="session")
def user_address(client: PolymarketPandas) -> str:
    """A real user address from the leaderboard."""
    lb = client.get_leaderboard(limit=1)
    return str(lb["proxyWallet"].iloc[0])


# ---------------------------------------------------------------------------
# Gamma API tests
# ---------------------------------------------------------------------------


def test_get_teams(client: PolymarketPandas) -> None:
    df = client.get_teams()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    TeamSchema.validate(df)


def test_get_sports_metadata(client: PolymarketPandas) -> None:
    df = client.get_sports_metadata()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    SportsMetadataSchema.validate(df)


def test_get_sports_market_types(client: PolymarketPandas) -> None:
    result = client.get_sports_market_types()
    assert isinstance(result, (dict, list))


def test_get_tags(client: PolymarketPandas) -> None:
    df = client.get_tags()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    TagSchema.validate(df)


def test_get_tag_by_id(client: PolymarketPandas, tag_id: int) -> None:
    result = client.get_tag_by_id(tag_id)
    assert isinstance(result, dict)
    assert int(result.get("id")) == tag_id


def test_get_tag_by_slug(client: PolymarketPandas, tag_slug: str) -> None:
    result = client.get_tag_by_slug(tag_slug)
    assert isinstance(result, dict)
    assert result.get("slug") == tag_slug


def test_get_related_tags_by_tag_id(client: PolymarketPandas, tag_id: int) -> None:
    df = client.get_related_tags_by_tag_id(tag_id)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        TagSchema.validate(df)


def test_get_related_tags_by_tag_slug(client: PolymarketPandas, tag_slug: str) -> None:
    df = client.get_related_tags_by_tag_slug(tag_slug)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        TagSchema.validate(df)


def test_get_series_returns_dataframe(client: PolymarketPandas) -> None:
    df = client.get_series(expand_events=True, expand_event_tags=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    SeriesSchema.validate(df)


def test_get_series_by_id(client: PolymarketPandas) -> None:
    series = client.get_series(limit=1)
    series_id = int(series["id"].iloc[0])
    result = client.get_series_by_id(series_id)
    assert isinstance(result, dict)


def test_get_markets(markets: pd.DataFrame) -> None:
    assert isinstance(markets, pd.DataFrame)
    assert not markets.empty
    assert "clobTokenIds" in markets.columns
    MarketSchema.validate(markets)


def test_get_market_by_id(client: PolymarketPandas, market_id: int) -> None:
    result = client.get_market_by_id(market_id)
    assert isinstance(result, dict)


def test_get_market_by_slug(client: PolymarketPandas, market_slug: str) -> None:
    result = client.get_market_by_slug(market_slug)
    assert isinstance(result, dict)


def test_get_market_tags(client: PolymarketPandas, market_id: int) -> None:
    df = client.get_market_tags(market_id)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        TagSchema.validate(df)


def test_get_events(events: pd.DataFrame) -> None:
    assert isinstance(events, pd.DataFrame)
    assert not events.empty
    assert "marketsClobTokenIds" in events.columns
    EventSchema.validate(events)


def test_get_events_keyset(client: PolymarketPandas) -> None:
    page = client.get_events_keyset(limit=25, closed=False)
    assert isinstance(page, dict)
    df = page["data"]
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    EventSchema.validate(df)


def test_get_event_by_id(client: PolymarketPandas, event_id: int) -> None:
    result = client.get_event_by_id(event_id)
    assert isinstance(result, dict)


def test_get_event_by_slug(client: PolymarketPandas, event_slug: str) -> None:
    result = client.get_event_by_slug(event_slug)
    assert isinstance(result, dict)


def test_get_event_tags(client: PolymarketPandas, event_id: int) -> None:
    df = client.get_event_tags(event_id)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        TagSchema.validate(df)


def test_get_comments(client: PolymarketPandas, event_id: int) -> None:
    df = client.get_comments(limit=5, parent_entity_type="Event", parent_entity_id=event_id)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        CommentSchema.validate(df)


def test_search_markets_events_profiles(client: PolymarketPandas) -> None:
    result = client.search_markets_events_profiles(q="bitcoin")
    assert isinstance(result, dict)


def test_get_profile(client: PolymarketPandas, user_address: str) -> None:
    result = client.get_profile(user_address)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# CLOB API — public market data tests
# ---------------------------------------------------------------------------


def test_get_server_time(client: PolymarketPandas) -> None:
    t = client.get_server_time()
    assert isinstance(t, int)
    assert t > 0


def test_get_tick_size(client: PolymarketPandas, token: str) -> None:
    tick = client.get_tick_size(token)
    assert isinstance(tick, float)
    assert tick > 0


def test_get_neg_risk(client: PolymarketPandas, token: str) -> None:
    result = client.get_neg_risk(token)
    assert isinstance(result, bool)


def test_get_fee_rate(client: PolymarketPandas, token: str) -> None:
    """V2 deprecation shim: get_fee_rate now always returns 0."""
    rate = client.get_fee_rate(token_id=token)
    assert rate == 0


def test_get_clob_market_info(client: PolymarketPandas, condition_id: str) -> None:
    """V2 single-call market info (`/clob-markets/{conditionId}`).

    Confirmed canonical keys (live probe 2026-04-29):
      ``c, t, mts, mos, mbf, tbf, ao, cbos, ibce, aot, fd, r``.
    ``nr`` is only present on neg-risk markets.
    """
    info = client.get_clob_market_info(condition_id)
    assert isinstance(info, dict)
    assert {"c", "t", "mts", "mos", "fd"} <= set(info)
    assert info["c"].lower() == condition_id.lower()
    assert isinstance(info["mts"], (int, float)) and info["mts"] > 0
    assert isinstance(info["t"], list) and len(info["t"]) >= 2
    # Each token entry has tokenID `t` and outcome label `o`.
    assert {"t", "o"} <= set(info["t"][0])
    # Fee details: rate `r` and exponent `e`.
    assert {"r", "e"} <= set(info["fd"])


def test_get_orderbook(client: PolymarketPandas, token: str) -> None:
    df = client.get_orderbook(token_id=token)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "side" in df.columns
    assert set(df["side"].unique()).issubset({"bids", "asks"})
    OrderbookSchema.validate(df)


def test_get_orderbooks(client: PolymarketPandas, active_token_ids: pd.DataFrame) -> None:
    df = client.get_orderbooks(data=active_token_ids)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "side" in df.columns
    OrderbookSchema.validate(df)


def test_get_market_price(client: PolymarketPandas, token: str) -> None:
    price = client.get_market_price(token_id=token, side="BUY")
    assert isinstance(price, float)
    assert 0.0 <= price <= 1.0


def test_get_market_prices(client: PolymarketPandas, token: str) -> None:
    result = client.get_market_prices([{"token_id": token, "side": "BUY"}])
    assert isinstance(result, pd.DataFrame)


def test_get_multiple_market_prices_by_request(
    client: PolymarketPandas, markets: pd.DataFrame
) -> None:
    data = markets[["clobTokenIds"]].rename(columns={"clobTokenIds": "token_id"}).head(20)
    df = client.get_multiple_market_prices_by_request(data=data)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    MarketPriceSchema.validate(df)


def test_get_midpoint_price(client: PolymarketPandas, token: str) -> None:
    mid = client.get_midpoint_price(token_id=token)
    assert isinstance(mid, float)
    assert 0.0 <= mid <= 1.0


@pytest.mark.xfail(reason="CLOB GET /midpoints returns 400 — use get_midpoints_by_request (POST)")
def test_get_midpoints(client: PolymarketPandas, active_token_ids: pd.DataFrame) -> None:
    ids = active_token_ids["token_id"].head(2).tolist()
    df = client.get_midpoints(ids)
    assert isinstance(df, pd.DataFrame)
    MidpointSchema.validate(df)


def test_get_midpoints_by_request(client: PolymarketPandas, active_token_ids: pd.DataFrame) -> None:
    df = client.get_midpoints_by_request(active_token_ids.head(5))
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    MidpointSchema.validate(df)


def test_get_spread(client: PolymarketPandas, token: str) -> None:
    spread = client.get_spread(token)
    assert isinstance(spread, float)


def test_get_bid_ask_spreads(client: PolymarketPandas, markets: pd.DataFrame) -> None:
    data = markets[["clobTokenIds"]].rename(columns={"clobTokenIds": "token_id"}).head(20)
    result = client.get_bid_ask_spreads(data=data)
    assert isinstance(result, dict)
    assert len(result) > 0
    for v in result.values():
        assert isinstance(v, float)


def test_get_last_trade_price(client: PolymarketPandas, token: str) -> None:
    result = client.get_last_trade_price(token)
    assert isinstance(result, dict)
    assert "price" in result


def test_get_last_trade_prices(client: PolymarketPandas, active_token_ids: pd.DataFrame) -> None:
    df = client.get_last_trade_prices(active_token_ids.head(5))
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        LastTradePricesSchema.validate(df)


def test_get_price_history(client: PolymarketPandas, token: str) -> None:
    end = int(_time.time())
    start = end - 7 * 86400
    df = client.get_price_history(market=token, startTs=start, endTs=end, fidelity=60)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    PriceHistorySchema.validate(df)
    assert pd.api.types.is_datetime64_any_dtype(df["t"])


def test_get_sampling_markets(client: PolymarketPandas) -> None:
    result = client.get_sampling_markets()
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        SamplingMarketSchema.validate(result["data"])


def test_get_simplified_markets(client: PolymarketPandas) -> None:
    result = client.get_simplified_markets()
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        SimplifiedMarketSchema.validate(result["data"])


def test_get_sampling_simplified_markets(client: PolymarketPandas) -> None:
    result = client.get_sampling_simplified_markets()
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        SimplifiedMarketSchema.validate(result["data"])


# ---------------------------------------------------------------------------
# Data API tests
# ---------------------------------------------------------------------------


def test_get_trades(client: PolymarketPandas) -> None:
    df = client.get_trades(limit=10)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    DataTradeSchema.validate(df)


def test_get_positions(client: PolymarketPandas, user_address: str) -> None:
    df = client.get_positions(user=user_address, limit=5)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        PositionSchema.validate(df)


def test_get_closed_positions(client: PolymarketPandas, user_address: str) -> None:
    df = client.get_closed_positions(user=user_address, limit=5)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        ClosedPositionSchema.validate(df)


def test_get_market_positions(client: PolymarketPandas, token: str) -> None:
    df = client.get_market_positions(market=token, limit=5)
    assert isinstance(df, pd.DataFrame)


def test_get_top_holders(client: PolymarketPandas, condition_id: str) -> None:
    df = client.get_top_holders(market=[condition_id], limit=5)
    assert isinstance(df, pd.DataFrame)


def test_get_positions_value(client: PolymarketPandas, user_address: str) -> None:
    df = client.get_positions_value(user=user_address)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        PositionValueSchema.validate(df)


def test_get_leaderboard(client: PolymarketPandas) -> None:
    df = client.get_leaderboard(limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    LeaderboardSchema.validate(df)


def test_get_user_activity(client: PolymarketPandas, user_address: str) -> None:
    df = client.get_user_activity(user=user_address, limit=5)
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        ActivitySchema.validate(df)


def test_get_live_volume(client: PolymarketPandas, event_id: int) -> None:
    result = client.get_live_volume(id=event_id)
    assert isinstance(result, (dict, list))


def test_get_open_interest(client: PolymarketPandas) -> None:
    result = client.get_open_interest()
    assert isinstance(result, (dict, list))


def test_get_traded_markets_count(client: PolymarketPandas, user_address: str) -> None:
    result = client.get_traded_markets_count(user=user_address)
    assert isinstance(result, dict)


def test_get_builder_leaderboard(client: PolymarketPandas) -> None:
    df = client.get_builder_leaderboard(limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    BuilderLeaderboardSchema.validate(df)


def test_get_builder_volume(client: PolymarketPandas) -> None:
    df = client.get_builder_volume()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    BuilderVolumeSchema.validate(df)


def test_get_builder_trades(builder_client: PolymarketPandas) -> None:
    result = builder_client.get_builder_trades(builder="betmoar")
    assert isinstance(result, dict)
    assert set(result.keys()) >= {"data", "next_cursor", "count", "limit"}
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        BuilderTradeSchema.validate(result["data"])


# ---------------------------------------------------------------------------
# Rewards API tests (public — no auth)
# ---------------------------------------------------------------------------


def test_get_rewards_markets_current(client: PolymarketPandas) -> None:
    result = client.get_rewards_markets_current()
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        CurrentRewardSchema.validate(result["data"])


def test_get_rewards_markets_multi(client: PolymarketPandas) -> None:
    result = client.get_rewards_markets_multi()
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        RewardsMarketMultiSchema.validate(result["data"])


def test_get_rewards_market(client: PolymarketPandas, condition_id: str) -> None:
    result = client.get_rewards_market(condition_id=condition_id)
    assert isinstance(result, dict)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    if not result["data"].empty:
        RewardsMarketSchema.validate(result["data"])


# ---------------------------------------------------------------------------
# Bridge API tests (public)
# ---------------------------------------------------------------------------


def test_get_bridge_supported_assets(client: PolymarketPandas) -> None:
    df = client.get_bridge_supported_assets()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    BridgeSupportedAssetSchema.validate(df)


# ---------------------------------------------------------------------------
# xtracker API tests (public)
# ---------------------------------------------------------------------------


def test_get_xtracker_users(client: PolymarketPandas) -> None:
    df = client.get_xtracker_users(platform="X")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    XTrackerUserSchema.validate(df)


def test_get_xtracker_user(client: PolymarketPandas) -> None:
    user = client.get_xtracker_user("elonmusk", platform="X")
    assert isinstance(user, dict)
    assert user.get("handle") == "elonmusk"
    assert user.get("platform") == "X"


def test_get_xtracker_user_posts(client: PolymarketPandas) -> None:
    end = pd.Timestamp.now(tz="UTC").normalize()
    df = client.get_xtracker_user_posts(
        "elonmusk",
        platform="X",
        start_date=end - pd.Timedelta(days=2),
        end_date=end,
    )
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        XTrackerPostSchema.validate(df)


def test_get_xtracker_trackings(client: PolymarketPandas) -> None:
    df = client.get_xtracker_trackings(active_only=True)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    XTrackerTrackingSchema.validate(df)


def test_get_xtracker_tracking_with_stats(client: PolymarketPandas) -> None:
    trks = client.get_xtracker_trackings(active_only=True)
    tracking_id = trks["id"].iloc[0]
    res = client.get_xtracker_tracking(tracking_id, include_stats=True)
    assert isinstance(res, dict)
    assert res["id"] == tracking_id
    stats = res["stats"]
    assert isinstance(stats, pd.DataFrame)
    # Aggregate scalars surfaced via .attrs
    assert "total" in stats.attrs
    assert "pace" in stats.attrs
    if not stats.empty:
        XTrackerDailyStatSchema.validate(stats)


def test_get_xtracker_metrics(client: PolymarketPandas) -> None:
    users = client.get_xtracker_users(platform="X")
    user_id = users["id"].iloc[0]
    end = pd.Timestamp.now(tz="UTC").normalize()
    df = client.get_xtracker_metrics(
        user_id,
        type="daily",
        start_date=end - pd.Timedelta(days=14),
        end_date=end,
    )
    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        assert {"dataCount", "dataCumulative"} <= set(df.columns)
        XTrackerMetricSchema.validate(df)
