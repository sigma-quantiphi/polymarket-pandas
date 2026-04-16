import inspect
import time
from datetime import datetime
from functools import wraps

import orjson
import pandas as pd

__all__ = [
    "DEFAULT_BOOL_COLUMNS",
    "DEFAULT_DICT_COLUMNS",
    "DEFAULT_DROP_COLUMNS",
    "DEFAULT_INT_DATETIME_COLUMNS",
    "DEFAULT_JSON_COLUMNS",
    "DEFAULT_MS_INT_DATETIME_COLUMNS",
    "DEFAULT_NUMERIC_COLUMNS",
    "DEFAULT_STR_DATETIME_COLUMNS",
    "expand_column_lists",
    "expand_dataframe",
    "filter_params",
    "instance_cache",
    "orderbook_meta",
    "preprocess_dataframe",
    "snake_columns_to_camel",
    "snake_to_camel",
    "to_unix_timestamp",
]


def to_unix_timestamp(value: int | float | str | pd.Timestamp | datetime) -> int:
    """Convert a datetime-like value to a Unix timestamp in seconds.

    Accepts:
        int / float: returned as-is (assumed Unix seconds already).
        str: parsed as ISO-8601 datetime, then converted.
        pd.Timestamp / datetime.datetime: converted to Unix seconds.

    Returns:
        int: Unix timestamp in seconds.
    """
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = pd.Timestamp(value, tz="UTC")
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            value = value.tz_localize("UTC")
        return int(value.timestamp())
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=__import__("zoneinfo").ZoneInfo("UTC"))
        return int(value.timestamp())
    raise TypeError(f"Cannot convert {type(value).__name__} to Unix timestamp")


def instance_cache(method=None, *, ttl: float | None = None, maxsize: int = 256):
    """Cache results of an instance method, keyed by arguments.

    Wraps :func:`cachetools.cachedmethod`, storing a per-method cache on the
    instance as ``_cache_{method_name}``.

    Usage::

        @instance_cache            # permanent cache
        def get_neg_risk(self, token_id): ...

        @instance_cache(ttl=300)   # expires after 300 seconds
        def get_tick_size(self, token_id): ...
    """
    from cachetools import Cache, TTLCache, cachedmethod

    def decorator(fn):
        attr = f"_cache_{fn.__name__}"

        def _get_cache(self):
            cache = getattr(self, attr, None)
            if cache is None:
                cache = TTLCache(maxsize=maxsize, ttl=ttl) if ttl else Cache(maxsize=maxsize)
                setattr(self, attr, cache)
            return cache

        return cachedmethod(_get_cache)(fn)

    if method is not None:
        return decorator(method)
    return decorator


# ── Shared column-type defaults ──────────────────────────────────────
# Used by both PolymarketPandas and PolymarketWebSocket as dataclass field defaults.
DEFAULT_NUMERIC_COLUMNS = (
    "bestAsk",
    "bestBid",
    "best_ask",
    "best_bid",
    "fee_rate_bps",
    "full_accuracy_value",
    "lastTradePrice",
    "liquidity",
    "liquidityAmm",
    "liquidityNum",
    "lowerBound",
    "matched_amount",
    "min_order_size",
    "new_tick_size",
    "old_tick_size",
    "oneDayPriceChange",
    "oneHourPriceChange",
    "oneMonthPriceChange",
    "oneWeekPriceChange",
    "oneYearPriceChange",
    "original_size",
    "price",
    "rewardsMaxSpread",
    "rewardsMinSize",
    "size",
    "spread",
    "tick_size",
    "umaBond",
    "umaReward",
    "upperBound",
    "volume",
    "volume1mo",
    "volume1moAmm",
    "volume1moClob",
    "volume1wk",
    "volume1wkAmm",
    "volume1wkClob",
    "volume1yr",
    "volume1yrAmm",
    "volume1yrClob",
    "volume24hr",
    "volumeNum",
)

DEFAULT_STR_DATETIME_COLUMNS = (
    "acceptingOrdersTimestamp",
    "closedTime",
    "createdAt",
    "creationDate",
    "date",
    "deployingTimestamp",
    "importedAt",
    "endDate",
    "endDateIso",
    "eventStartTime",
    "expiration",
    "finishedTimestamp",
    "gameStartTime",
    "matchTime",
    "matchtime",
    "last_update",
    "lastSync",
    "startDate",
    "startDateIso",
    "startTime",
    "umaEndDate",
    "updatedAt",
    "valuationTime",
)
DEFAULT_INT_DATETIME_COLUMNS = ("timestamp",)
DEFAULT_MS_INT_DATETIME_COLUMNS = ("createdTimeMs", "estCheckoutTimeMs")

DEFAULT_BOOL_COLUMNS = (
    "acceptingOrders",
    "active",
    "approved",
    "archived",
    "automaticallyActive",
    "clearBookOnStart",
    "closed",
    "competitive",
    "cyom",
    "deploying",
    "enableOrderBook",
    "ended",
    "featured",
    "feesEnabled",
    "fpmmLive",
    "funded",
    "hasReviewedDates",
    "holdingRewardsEnabled",
    "live",
    "manualActivation",
    "negRisk",
    "negRiskAugmented",
    "negRiskOther",
    "new",
    "notificationsEnabled",
    "pagerDutyNotificationEnabled",
    "pendingDeployment",
    "ready",
    "readyForCron",
    "requiresTranslation",
    "restricted",
    "rfqEnabled",
    "showAllOutcomes",
    "showMarketImages",
    "wideFormat",
)

DEFAULT_DICT_COLUMNS = ("feeSchedule",)
DEFAULT_DROP_COLUMNS = ("icon", "image")
DEFAULT_JSON_COLUMNS = (
    "clobTokenIds",
    "outcomes",
    "outcomePrices",
    "umaResolutionStatuses",
)


def preprocess_dict(
    data: dict,
    *,
    numeric_columns: tuple = DEFAULT_NUMERIC_COLUMNS,
    str_datetime_columns: tuple = DEFAULT_STR_DATETIME_COLUMNS,
    int_datetime_columns: tuple = DEFAULT_INT_DATETIME_COLUMNS,
    ms_int_datetime_columns: tuple = DEFAULT_MS_INT_DATETIME_COLUMNS,
    bool_columns: tuple = DEFAULT_BOOL_COLUMNS,
    drop_columns: tuple = DEFAULT_DROP_COLUMNS,
    json_columns: tuple = DEFAULT_JSON_COLUMNS,
    int_datetime_unit: str = "s",
) -> dict:
    """Apply the same type coercion as ``preprocess_dataframe`` to a single dict.

    Converts numeric strings to ``float``, ISO-8601 timestamps to
    ``pd.Timestamp``, boolean-ish strings to ``bool``, and JSON-encoded
    strings to Python objects. Drops ``icon``/``image`` keys.

    Recursively preprocesses nested dicts and lists of dicts.
    """
    # snake_case → camelCase keys
    data = {snake_to_camel(k): v for k, v in data.items()}

    for key in drop_columns:
        data.pop(key, None)

    for key, val in data.items():
        if not isinstance(val, str):
            continue
        if key in json_columns:
            try:
                data[key] = orjson.loads(val)
            except Exception:
                pass
        elif key in (*numeric_columns, *int_datetime_columns, *ms_int_datetime_columns):
            try:
                data[key] = float(val)
            except (ValueError, TypeError):
                pass
        elif key in str_datetime_columns:
            try:
                data[key] = pd.Timestamp(val, tz="UTC")
            except Exception:
                pass
        elif key in bool_columns:
            data[key] = val.lower() not in ("false", "0", "")

    # Convert int timestamps to pd.Timestamp
    for key in int_datetime_columns:
        val = data.get(key)
        if isinstance(val, (int, float)):
            try:
                data[key] = pd.Timestamp(val, unit=int_datetime_unit, tz="UTC")
            except Exception:
                pass

    # Convert millisecond int timestamps to pd.Timestamp
    for key in ms_int_datetime_columns:
        val = data.get(key)
        if isinstance(val, (int, float)):
            try:
                data[key] = pd.Timestamp(val, unit="ms", tz="UTC")
            except Exception:
                pass

    # Convert remaining bool values (non-string bools pass through above)
    for key in bool_columns:
        val = data.get(key)
        if isinstance(val, str):
            data[key] = val.lower() not in ("false", "0", "")

    # Recurse into nested dicts and lists of dicts
    _kw = dict(
        numeric_columns=numeric_columns,
        str_datetime_columns=str_datetime_columns,
        int_datetime_columns=int_datetime_columns,
        ms_int_datetime_columns=ms_int_datetime_columns,
        bool_columns=bool_columns,
        drop_columns=drop_columns,
        json_columns=json_columns,
        int_datetime_unit=int_datetime_unit,
    )
    for key, val in data.items():
        if isinstance(val, dict):
            data[key] = preprocess_dict(val, **_kw)
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            data[key] = [preprocess_dict(item, **_kw) for item in val]

    return data


orderbook_meta = [
    "market",
    "asset_id",
    "timestamp",
    "hash",
    "min_order_size",
    "tick_size",
    "neg_risk",
]


def preprocess_dataframe(
    df: pd.DataFrame,
    *,
    numeric_columns: list,
    str_datetime_columns: list,
    int_datetime_columns: list,
    ms_int_datetime_columns: list,
    bool_columns: list,
    drop_columns: list,
    json_columns: list,
    dict_columns: tuple | list = (),
    int_datetime_unit: str = "s",
) -> pd.DataFrame:
    """Apply column renaming and type coercion to a raw API DataFrame."""
    df = snake_columns_to_camel(df)
    df = df.drop(columns=drop_columns, errors="ignore")
    columns = df.columns
    numeric_to_convert = [
        x for x in columns if x in numeric_columns + int_datetime_columns + ms_int_datetime_columns
    ]
    int_datetime_to_convert = [x for x in columns if x in int_datetime_columns]
    ms_int_datetime_to_convert = [x for x in columns if x in ms_int_datetime_columns]
    str_datetime_to_convert = [x for x in columns if x in str_datetime_columns]
    bool_to_convert = [x for x in columns if x in bool_columns]
    json_to_convert = [x for x in columns if x in json_columns]
    dict_to_flatten = [x for x in columns if x in dict_columns]
    if numeric_to_convert:
        df[numeric_to_convert] = df[numeric_to_convert].apply(pd.to_numeric, errors="coerce")
    if int_datetime_to_convert:
        df[int_datetime_to_convert] = df[int_datetime_to_convert].apply(
            pd.to_datetime, utc=True, unit=int_datetime_unit, errors="coerce"
        )
    if ms_int_datetime_to_convert:
        df[ms_int_datetime_to_convert] = df[ms_int_datetime_to_convert].apply(
            pd.to_datetime, utc=True, unit="ms", errors="coerce"
        )
    for col in str_datetime_to_convert:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.dropna().empty:
            # All non-null values failed numeric conversion → ISO strings
            df[col] = pd.to_datetime(series, utc=True, errors="coerce")
        elif numeric.dropna().gt(1e9).all():
            # Looks like Unix timestamps in seconds
            df[col] = pd.to_datetime(numeric, utc=True, unit="s", errors="coerce")
        else:
            # Mixed or ISO strings — default path
            df[col] = pd.to_datetime(series, utc=True, errors="coerce")
    _bool_map = {
        "true": True,
        "True": True,
        "1": True,
        True: True,
        "false": False,
        "False": False,
        "0": False,
        "": False,
        False: False,
    }
    for col in bool_to_convert:
        df[col] = df[col].map(_bool_map).astype("boolean")
    for column in json_to_convert:
        df[column] = df[column].apply(lambda x: orjson.loads(x) if pd.notnull(x) else x)
    for column in dict_to_flatten:
        expanded = pd.json_normalize(df[column].apply(lambda x: x if isinstance(x, dict) else {}))
        expanded.columns = [
            column + snake_to_camel(c)[:1].upper() + snake_to_camel(c)[1:] for c in expanded.columns
        ]
        expanded.index = df.index
        df = pd.concat([df.drop(columns=[column]), expanded], axis=1)
    return df


def _ts_to_iso(value):
    """Convert a Timestamp or datetime to an ISO-8601 UTC string. Pass through str/None."""
    if isinstance(value, pd.Timestamp):
        return value.tz_convert("UTC").isoformat() if value.tzinfo else value.isoformat() + "Z"
    if isinstance(value, datetime):
        return value.astimezone(tz=None).isoformat() if value.tzinfo else value.isoformat() + "Z"
    return value


def filter_params(params: dict | None) -> dict:
    """Remove None values and empty lists; convert Timestamps to Unix seconds."""
    if params is None:
        return {}
    new_params = {}
    for key, value in params.items():
        if isinstance(value, list):
            if len(value) > 0:
                new_params[key] = value
        elif pd.notnull(value):
            if isinstance(value, (pd.Timestamp, datetime)):
                value = int(value.timestamp())
            new_params[key] = value
    return new_params


def snake_to_camel(value: str) -> str:
    """Convert snake_case or kebab-case to lowerCamelCase."""
    if "_" in value:
        parts = value.split("_")
        value = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:] if p)
    return value


def snake_columns_to_camel(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with camelCase column names."""
    data = data.copy()
    data.columns = [snake_to_camel(col) for col in data.columns]
    return data


def expand_dataframe(
    data: pd.DataFrame, field: str = "events", column: str = "event"
) -> pd.DataFrame:
    """Flatten a nested list column into rows with prefixed columns."""
    meta_cols = [c for c in data.columns if c != field]
    rows = []
    for rec in data.to_dict("records"):
        meta = {c: rec[c] for c in meta_cols}
        children = rec.get(field)
        if not isinstance(children, list):
            children = []
        for child in children:
            row = {f"{column}_{k}": v for k, v in child.items()}
            row.update(meta)
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    result = snake_columns_to_camel(pd.DataFrame(rows))
    return result.loc[:, ~result.columns.duplicated(keep="last")]


_EXPAND_PREFIXES = (
    "events",
    "eventsTags",
    "markets",
    "eventsSeries",
    "rewardsConfig",
    "tokens",
    "earnings",
    "user",
    "trackings",
    "count",
)


def expand_column_lists(base: tuple, prefixes: tuple = _EXPAND_PREFIXES) -> list:
    """Return base columns plus prefixed camelCase variants for nested expand fields."""
    result = [snake_to_camel(x) for x in base]
    for prefix in prefixes:
        result += [snake_to_camel(f"{prefix}_{x}") for x in base]
    return result


def autopage(param_limit: str = "limit", param_offset: str = "offset"):
    """Decorator that adds an ``_all`` autopaging wrapper using offset-based pagination."""

    def _decorator(func):
        sig = inspect.signature(func)
        default_limit = (
            sig.parameters[param_limit].default if param_limit in sig.parameters else 500
        )
        default_offset = (
            sig.parameters[param_offset].default if param_offset in sig.parameters else 0
        )

        @wraps(func)
        def _all(self, *args, **kwargs) -> pd.DataFrame:
            limit = kwargs.get(param_limit, default_limit)
            offset = kwargs.get(param_offset, default_offset)
            max_pages = kwargs.pop("max_pages", None)
            sleep_s = kwargs.pop("sleep_s", 0.0)

            pages = []
            pages_done = 0
            while True:
                kwargs[param_limit] = limit
                kwargs[param_offset] = offset
                df = func(self, *args, **kwargs)
                if not isinstance(df, pd.DataFrame) or df.empty:
                    break
                pages.append(df)
                if len(df) < limit:
                    break
                pages_done += 1
                if max_pages and pages_done >= max_pages:
                    break
                offset += limit
                if sleep_s:
                    time.sleep(sleep_s)

            return pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()

        return _all

    return _decorator
