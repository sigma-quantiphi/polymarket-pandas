import inspect
from functools import wraps

import orjson
import pandas as pd
import time


__all__ = [
    "expand_column_lists",
    "expand_dataframe",
    "filter_params",
    "orderbook_meta",
    "preprocess_dataframe",
    "snake_columns_to_camel",
    "snake_to_camel",
]


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
    bool_columns: list,
    drop_columns: list,
    json_columns: list,
) -> pd.DataFrame:
    df = snake_columns_to_camel(df)
    df = df.drop(columns=drop_columns, errors="ignore")
    columns = df.columns
    numeric_to_convert = [
        x for x in columns if x in numeric_columns + int_datetime_columns
    ]
    int_datetime_to_convert = [x for x in columns if x in int_datetime_columns]
    str_datetime_to_convert = [x for x in columns if x in str_datetime_columns]
    bool_to_convert = [x for x in columns if x in bool_columns]
    json_to_convert = [x for x in columns if x in json_columns]
    if numeric_to_convert:
        df[numeric_to_convert] = df[numeric_to_convert].apply(
            pd.to_numeric, errors="coerce"
        )
    if int_datetime_to_convert:
        df[int_datetime_to_convert] = df[int_datetime_to_convert].apply(
            pd.to_datetime, utc=True, unit="ms", errors="coerce"
        )
    if str_datetime_to_convert:
        df[str_datetime_to_convert] = df[str_datetime_to_convert].apply(
            pd.to_datetime, utc=True, errors="coerce"
        )
    if bool_to_convert:
        df[bool_to_convert] = df[bool_to_convert].astype(bool)
    for column in json_to_convert:
        df[column] = df[column].apply(
            lambda x: orjson.loads(x) if pd.notnull(x) else x
        )
    return df


def filter_params(params: dict | None) -> dict:
    if params is None:
        return {}
    new_params = {}
    for key, value in params.items():
        if isinstance(value, list):
            if len(value) > 0:
                new_params[key] = value
        elif pd.notnull(value):
            if key in [
                "start_date_min",
                "start_date_max",
                "end_date_min",
                "end_date_max",
            ] and isinstance(value, pd.Timestamp):
                value = value.isoformat() + "Z"
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
    meta = [x for x in data.columns if x != field]
    data = pd.json_normalize(
        data=data.to_dict("records"),
        record_path=field,
        meta=meta,
        record_prefix=f"{column}_",
    )
    data = snake_columns_to_camel(data)
    return data.loc[:, ~data.columns.duplicated(keep="last")]


_EXPAND_PREFIXES = ("events", "eventsTags", "markets", "eventsSeries")


def expand_column_lists(base: tuple, prefixes: tuple = _EXPAND_PREFIXES) -> list:
    """Return base columns plus prefixed camelCase variants for nested expand fields."""
    result = list(base)
    for prefix in prefixes:
        result += [snake_to_camel(f"{prefix}_{x}") for x in base]
    return result


def autopage(param_limit: str = "limit", param_offset: str = "offset"):
    def _decorator(func):
        sig = inspect.signature(func)
        default_limit = (
            sig.parameters[param_limit].default
            if param_limit in sig.parameters
            else 500
        )
        default_offset = (
            sig.parameters[param_offset].default
            if param_offset in sig.parameters
            else 0
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
