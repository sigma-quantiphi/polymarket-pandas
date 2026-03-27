"""Pandera DataFrameModel schemas for DataFrame-returning endpoints.

All schemas use ``strict=False`` (extra columns allowed) and
``coerce=True`` to avoid breaking when the Polymarket API adds new fields.

Column names reflect the **post-preprocessing** camelCase convention used
throughout the library. Field names verified against the official Polymarket
OpenAPI specs at ``docs.polymarket.com/api-spec/clob-openapi.yaml`` and
``docs.polymarket.com/api-spec/data-openapi.yaml``.
"""

from __future__ import annotations

import pandera as pa


class _Lenient(pa.DataFrameModel):
    """Base config: allow extra columns, coerce types."""

    class Config:
        strict = False
        coerce = True


# ═══════════════════════════════════════════════════════════════════════
# Gamma API schemas (camelCase natively)
# ═══════════════════════════════════════════════════════════════════════


class MarketSchema(_Lenient):
    """Schema for ``get_markets`` / ``get_markets_all`` (post-expand, post-explode).

    Source: ``GET gamma-api.polymarket.com/markets``
    """

    id: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    question: str | None = pa.Field(nullable=True)
    questionID: str | None = pa.Field(nullable=True)
    # JSON-parsed lists
    outcomes: object | None = pa.Field(nullable=True)
    outcomePrices: object | None = pa.Field(nullable=True)
    clobTokenIds: str | None = pa.Field(nullable=True)
    # Numeric
    volume: float | None = pa.Field(nullable=True)
    volumeNum: float | None = pa.Field(nullable=True)
    volume24hr: float | None = pa.Field(nullable=True)
    volume1wk: float | None = pa.Field(nullable=True)
    volume1mo: float | None = pa.Field(nullable=True)
    volume1yr: float | None = pa.Field(nullable=True)
    liquidity: float | None = pa.Field(nullable=True)
    liquidityNum: float | None = pa.Field(nullable=True)
    liquidityAmm: float | None = pa.Field(nullable=True)
    lastTradePrice: float | None = pa.Field(nullable=True)
    bestBid: float | None = pa.Field(nullable=True)
    bestAsk: float | None = pa.Field(nullable=True)
    spread: float | None = pa.Field(nullable=True)
    rewardsMinSize: float | None = pa.Field(nullable=True)
    rewardsMaxSpread: float | None = pa.Field(nullable=True)
    oneDayPriceChange: float | None = pa.Field(nullable=True)
    oneWeekPriceChange: float | None = pa.Field(nullable=True)
    oneMonthPriceChange: float | None = pa.Field(nullable=True)
    # Boolean
    active: bool | None = pa.Field(nullable=True)
    closed: bool | None = pa.Field(nullable=True)
    archived: bool | None = pa.Field(nullable=True)
    restricted: bool | None = pa.Field(nullable=True)
    negRiskOther: bool | None = pa.Field(nullable=True)


class EventSchema(_Lenient):
    """Schema for ``get_events`` / ``get_events_all`` (post-expand).

    Source: ``GET gamma-api.polymarket.com/events``
    """

    id: str | None = pa.Field(nullable=True)
    ticker: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    title: str | None = pa.Field(nullable=True)
    description: str | None = pa.Field(nullable=True)
    # Boolean
    active: bool | None = pa.Field(nullable=True)
    closed: bool | None = pa.Field(nullable=True)
    archived: bool | None = pa.Field(nullable=True)
    featured: bool | None = pa.Field(nullable=True)
    restricted: bool | None = pa.Field(nullable=True)
    negRisk: bool | None = pa.Field(nullable=True)
    # Numeric
    liquidity: float | None = pa.Field(nullable=True)
    volume: float | None = pa.Field(nullable=True)
    volume24hr: float | None = pa.Field(nullable=True)
    volume1wk: float | None = pa.Field(nullable=True)
    volume1mo: float | None = pa.Field(nullable=True)
    volume1yr: float | None = pa.Field(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
# CLOB API schemas (snake_case → camelCase after preprocess_dataframe)
# ═══════════════════════════════════════════════════════════════════════


class OrderbookSchema(_Lenient):
    """Schema for ``get_orderbook`` / ``get_orderbooks``.

    Source: ``GET clob.polymarket.com/book``
    """

    price: float = pa.Field(ge=0, le=1)
    size: float = pa.Field(ge=0)


class ClobTradeSchema(_Lenient):
    """Schema for ``get_user_trades`` (CLOB ``/data/trades``).

    Source: ``GET clob.polymarket.com/data/trades``
    """

    id: str | None = pa.Field(nullable=True)
    takerOrderId: str | None = pa.Field(nullable=True)
    market: str | None = pa.Field(nullable=True)
    assetId: str | None = pa.Field(nullable=True)
    side: str | None = pa.Field(nullable=True)
    size: float | None = pa.Field(nullable=True)
    price: float | None = pa.Field(nullable=True)
    feeRateBps: float | None = pa.Field(nullable=True)
    status: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    bucketIndex: int | None = pa.Field(nullable=True)
    owner: str | None = pa.Field(nullable=True)
    makerAddress: str | None = pa.Field(nullable=True)
    transactionHash: str | None = pa.Field(nullable=True)
    traderSide: str | None = pa.Field(nullable=True)


class ActiveOrderSchema(_Lenient):
    """Schema for ``get_active_orders`` (CLOB ``/data/orders``).

    Source: ``GET clob.polymarket.com/data/orders``
    """

    id: str | None = pa.Field(nullable=True)
    status: str | None = pa.Field(nullable=True)
    owner: str | None = pa.Field(nullable=True)
    makerAddress: str | None = pa.Field(nullable=True)
    market: str | None = pa.Field(nullable=True)
    assetId: str | None = pa.Field(nullable=True)
    side: str | None = pa.Field(nullable=True)
    originalSize: float | None = pa.Field(nullable=True)
    sizeMatched: float | None = pa.Field(nullable=True)
    price: float | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    orderType: str | None = pa.Field(nullable=True)
    associateTrades: object | None = pa.Field(nullable=True)


class PriceHistorySchema(_Lenient):
    """Schema for ``get_price_history``.

    Source: ``GET clob.polymarket.com/prices-history``
    """

    t: int = pa.Field(description="Unix timestamp")
    p: float = pa.Field(description="Price")


class SendOrderResponseSchema(_Lenient):
    """Schema for ``place_orders`` batch response DataFrame.

    Source: ``POST clob.polymarket.com/orders``
    """

    success: bool | None = pa.Field(nullable=True)
    orderID: str | None = pa.Field(nullable=True)
    status: str | None = pa.Field(nullable=True)
    makingAmount: str | None = pa.Field(nullable=True)
    takingAmount: str | None = pa.Field(nullable=True)
    errorMsg: str | None = pa.Field(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
# Data API schemas (camelCase natively)
# ═══════════════════════════════════════════════════════════════════════


class PositionSchema(_Lenient):
    """Schema for ``get_positions``.

    Source: ``GET data-api.polymarket.com/positions``
    """

    proxyWallet: str | None = pa.Field(nullable=True)
    asset: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    size: float | None = pa.Field(nullable=True)
    avgPrice: float | None = pa.Field(nullable=True)
    initialValue: float | None = pa.Field(nullable=True)
    currentValue: float | None = pa.Field(nullable=True)
    cashPnl: float | None = pa.Field(nullable=True)
    percentPnl: float | None = pa.Field(nullable=True)
    totalBought: float | None = pa.Field(nullable=True)
    realizedPnl: float | None = pa.Field(nullable=True)
    percentRealizedPnl: float | None = pa.Field(nullable=True)
    curPrice: float | None = pa.Field(nullable=True)
    redeemable: bool | None = pa.Field(nullable=True)
    mergeable: bool | None = pa.Field(nullable=True)
    negativeRisk: bool | None = pa.Field(nullable=True)
    title: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    outcomeIndex: int | None = pa.Field(nullable=True)
    oppositeOutcome: str | None = pa.Field(nullable=True)
    oppositeAsset: str | None = pa.Field(nullable=True)


class ClosedPositionSchema(_Lenient):
    """Schema for ``get_closed_positions``.

    Source: ``GET data-api.polymarket.com/closed-positions``
    """

    proxyWallet: str | None = pa.Field(nullable=True)
    asset: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    avgPrice: float | None = pa.Field(nullable=True)
    totalBought: float | None = pa.Field(nullable=True)
    realizedPnl: float | None = pa.Field(nullable=True)
    curPrice: float | None = pa.Field(nullable=True)
    title: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    outcomeIndex: int | None = pa.Field(nullable=True)
    oppositeOutcome: str | None = pa.Field(nullable=True)
    oppositeAsset: str | None = pa.Field(nullable=True)


class DataTradeSchema(_Lenient):
    """Schema for ``get_trades`` (Data API ``/trades``).

    Source: ``GET data-api.polymarket.com/trades``
    """

    proxyWallet: str | None = pa.Field(nullable=True)
    side: str | None = pa.Field(nullable=True)
    asset: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    size: float | None = pa.Field(nullable=True)
    price: float | None = pa.Field(nullable=True)
    title: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    outcomeIndex: int | None = pa.Field(nullable=True)
    name: str | None = pa.Field(nullable=True)
    pseudonym: str | None = pa.Field(nullable=True)
    transactionHash: str | None = pa.Field(nullable=True)


class ActivitySchema(_Lenient):
    """Schema for ``get_user_activity``.

    Source: ``GET data-api.polymarket.com/activity``
    """

    proxyWallet: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    type: str | None = pa.Field(nullable=True)
    size: float | None = pa.Field(nullable=True)
    usdcSize: float | None = pa.Field(nullable=True)
    price: float | None = pa.Field(nullable=True)
    transactionHash: str | None = pa.Field(nullable=True)
    asset: str | None = pa.Field(nullable=True)
    side: str | None = pa.Field(nullable=True)
    outcomeIndex: int | None = pa.Field(nullable=True)
    title: str | None = pa.Field(nullable=True)
    slug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)


class LeaderboardSchema(_Lenient):
    """Schema for ``get_leaderboard``.

    Source: ``GET data-api.polymarket.com/v1/leaderboard``
    """

    rank: str | None = pa.Field(nullable=True)
    proxyWallet: str | None = pa.Field(nullable=True)
    userName: str | None = pa.Field(nullable=True)
    vol: float | None = pa.Field(nullable=True)
    pnl: float | None = pa.Field(nullable=True)
    xUsername: str | None = pa.Field(nullable=True)
    verifiedBadge: bool | None = pa.Field(nullable=True)


class BuilderLeaderboardSchema(_Lenient):
    """Schema for ``get_builder_leaderboard``.

    Source: ``GET data-api.polymarket.com/v1/builders/leaderboard``
    """

    rank: str | None = pa.Field(nullable=True)
    builder: str | None = pa.Field(nullable=True)
    volume: float | None = pa.Field(nullable=True)
    activeUsers: int | None = pa.Field(nullable=True)
    verified: bool | None = pa.Field(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
# Rewards API schemas (snake_case → camelCase after preprocessing)
# ═══════════════════════════════════════════════════════════════════════


class RebateSchema(_Lenient):
    """Schema for ``get_rebates``.

    Source: ``GET clob.polymarket.com/rebates/current``
    """

    date: str | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    assetAddress: str | None = pa.Field(nullable=True)
    makerAddress: str | None = pa.Field(nullable=True)
    rebatedFeesUsdc: float | None = pa.Field(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
# CLOB Sampling / Simplified Market schemas
# ═══════════════════════════════════════════════════════════════════════


class SamplingMarketSchema(_Lenient):
    """Schema for ``get_sampling_markets`` data rows.

    Source: ``GET clob.polymarket.com/sampling-markets``
    """

    enableOrderBook: bool | None = pa.Field(nullable=True)
    active: bool | None = pa.Field(nullable=True)
    closed: bool | None = pa.Field(nullable=True)
    archived: bool | None = pa.Field(nullable=True)
    acceptingOrders: bool | None = pa.Field(nullable=True)
    minimumOrderSize: float | None = pa.Field(nullable=True)
    minimumTickSize: float | None = pa.Field(nullable=True)
    conditionId: str | None = pa.Field(nullable=True)
    questionId: str | None = pa.Field(nullable=True)
    question: str | None = pa.Field(nullable=True)
    description: str | None = pa.Field(nullable=True)
    marketSlug: str | None = pa.Field(nullable=True)
    negRisk: bool | None = pa.Field(nullable=True)
    negRiskMarketId: str | None = pa.Field(nullable=True)
    notificationsEnabled: bool | None = pa.Field(nullable=True)
    is5050Outcome: bool | None = pa.Field(nullable=True)
    rewards: object | None = pa.Field(nullable=True)
    tokens: object | None = pa.Field(nullable=True)
    tags: object | None = pa.Field(nullable=True)


class SimplifiedMarketSchema(_Lenient):
    """Schema for ``get_simplified_markets`` / ``get_sampling_simplified_markets`` data rows.

    Source: ``GET clob.polymarket.com/simplified-markets``
    """

    conditionId: str | None = pa.Field(nullable=True)
    rewards: object | None = pa.Field(nullable=True)
    tokens: object | None = pa.Field(nullable=True)
    active: bool | None = pa.Field(nullable=True)
    closed: bool | None = pa.Field(nullable=True)
    archived: bool | None = pa.Field(nullable=True)
    acceptingOrders: bool | None = pa.Field(nullable=True)


class BuilderTradeSchema(_Lenient):
    """Schema for ``get_builder_trades`` data rows.

    Source: ``GET clob.polymarket.com/builder/trades``
    Note: Builder trades are already camelCase in the API response.
    """

    id: str | None = pa.Field(nullable=True)
    tradeType: str | None = pa.Field(nullable=True)
    takerOrderHash: str | None = pa.Field(nullable=True)
    builder: str | None = pa.Field(nullable=True)
    market: str | None = pa.Field(nullable=True)
    assetId: str | None = pa.Field(nullable=True)
    side: str | None = pa.Field(nullable=True)
    size: float | None = pa.Field(nullable=True)
    sizeUsdc: float | None = pa.Field(nullable=True)
    price: float | None = pa.Field(nullable=True)
    status: str | None = pa.Field(nullable=True)
    outcome: str | None = pa.Field(nullable=True)
    outcomeIndex: int | None = pa.Field(nullable=True)
    owner: str | None = pa.Field(nullable=True)
    maker: str | None = pa.Field(nullable=True)
    transactionHash: str | None = pa.Field(nullable=True)
    bucketIndex: int | None = pa.Field(nullable=True)
    fee: float | None = pa.Field(nullable=True)
    feeUsdc: float | None = pa.Field(nullable=True)


# ═══════════════════════════════════════════════════════════════════════
# Rewards cursor-paginated schemas
# ═══════════════════════════════════════════════════════════════════════


class CurrentRewardSchema(_Lenient):
    """Schema for ``get_rewards_markets_current`` data rows.

    Source: ``GET clob.polymarket.com/rewards/markets/current``
    """

    conditionId: str | None = pa.Field(nullable=True)
    rewardsMaxSpread: float | None = pa.Field(nullable=True)
    rewardsMinSize: float | None = pa.Field(nullable=True)
    rewardsConfig: object | None = pa.Field(nullable=True)
    sponsoredDailyRate: float | None = pa.Field(nullable=True)
    sponsorsCount: int | None = pa.Field(nullable=True)
    nativeDailyRate: float | None = pa.Field(nullable=True)
    totalDailyRate: float | None = pa.Field(nullable=True)


class RewardsMarketMultiSchema(_Lenient):
    """Schema for ``get_rewards_markets_multi`` data rows.

    Source: ``GET clob.polymarket.com/rewards/markets/multi``
    """

    conditionId: str | None = pa.Field(nullable=True)
    eventId: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    marketId: str | None = pa.Field(nullable=True)
    marketSlug: str | None = pa.Field(nullable=True)
    question: str | None = pa.Field(nullable=True)
    rewardsMaxSpread: float | None = pa.Field(nullable=True)
    rewardsMinSize: float | None = pa.Field(nullable=True)
    spread: float | None = pa.Field(nullable=True)
    volume24hr: float | None = pa.Field(nullable=True)
    marketCompetitiveness: float | None = pa.Field(nullable=True)
    oneDayPriceChange: float | None = pa.Field(nullable=True)
    tokens: object | None = pa.Field(nullable=True)
    rewardsConfig: object | None = pa.Field(nullable=True)


class RewardsMarketSchema(_Lenient):
    """Schema for ``get_rewards_market`` data rows.

    Source: ``GET clob.polymarket.com/rewards/markets/{condition_id}``
    """

    conditionId: str | None = pa.Field(nullable=True)
    question: str | None = pa.Field(nullable=True)
    marketSlug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    rewardsMaxSpread: float | None = pa.Field(nullable=True)
    rewardsMinSize: float | None = pa.Field(nullable=True)
    marketCompetitiveness: float | None = pa.Field(nullable=True)
    tokens: object | None = pa.Field(nullable=True)
    rewardsConfig: object | None = pa.Field(nullable=True)


class UserEarningSchema(_Lenient):
    """Schema for ``get_rewards_earnings`` data rows.

    Source: ``GET clob.polymarket.com/rewards/user``
    """

    conditionId: str | None = pa.Field(nullable=True)
    assetAddress: str | None = pa.Field(nullable=True)
    makerAddress: str | None = pa.Field(nullable=True)
    earnings: float | None = pa.Field(nullable=True)
    assetRate: float | None = pa.Field(nullable=True)


class UserRewardsMarketSchema(_Lenient):
    """Schema for ``get_rewards_user_markets`` data rows.

    Source: ``GET clob.polymarket.com/rewards/user/markets``
    """

    conditionId: str | None = pa.Field(nullable=True)
    marketId: str | None = pa.Field(nullable=True)
    eventId: str | None = pa.Field(nullable=True)
    question: str | None = pa.Field(nullable=True)
    marketSlug: str | None = pa.Field(nullable=True)
    eventSlug: str | None = pa.Field(nullable=True)
    rewardsMaxSpread: float | None = pa.Field(nullable=True)
    rewardsMinSize: float | None = pa.Field(nullable=True)
    volume24hr: float | None = pa.Field(nullable=True)
    spread: float | None = pa.Field(nullable=True)
    marketCompetitiveness: float | None = pa.Field(nullable=True)
    tokens: object | None = pa.Field(nullable=True)
    rewardsConfig: object | None = pa.Field(nullable=True)
    makerAddress: str | None = pa.Field(nullable=True)
    earningPercentage: float | None = pa.Field(nullable=True)
    earnings: object | None = pa.Field(nullable=True)


__all__ = [
    "ActiveOrderSchema",
    "ActivitySchema",
    "BuilderLeaderboardSchema",
    "BuilderTradeSchema",
    "ClobTradeSchema",
    "ClosedPositionSchema",
    "CurrentRewardSchema",
    "DataTradeSchema",
    "EventSchema",
    "LeaderboardSchema",
    "MarketSchema",
    "OrderbookSchema",
    "PositionSchema",
    "PriceHistorySchema",
    "RebateSchema",
    "RewardsMarketMultiSchema",
    "RewardsMarketSchema",
    "SamplingMarketSchema",
    "SendOrderResponseSchema",
    "SimplifiedMarketSchema",
    "UserEarningSchema",
    "UserRewardsMarketSchema",
]
