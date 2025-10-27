import inspect
from functools import wraps
import pandas as pd
import time


def _parse_params(params: dict) -> dict:
    """Parse parameters for API requests."""
    if params:
        new_params = {}
        for key, value in params.items():
            if value:
                if key in ["before", "after", "startTs", "endTs"] and isinstance(
                    value, pd.Timestamp
                ):
                    value = value.isoformat() + "Z"
                new_params[key] = value
        return new_params
    else:
        return params


def filter_params(params: dict) -> dict:
    new_params = {}
    for key, value in params.items():
        if value:
            if isinstance(value, list):
                new_params[key] = value
            elif pd.notnull(value):
                new_params[key] = value
    return new_params


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
