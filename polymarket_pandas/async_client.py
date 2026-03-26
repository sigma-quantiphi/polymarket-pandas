"""Async wrapper for PolymarketPandas.

Wraps the synchronous client via composition, running each method in a
``ThreadPoolExecutor`` for true non-blocking behavior in asyncio contexts.
All public methods from ``PolymarketPandas`` are auto-generated as async
wrappers — new mixin methods are available immediately without changes here.

Usage::

    async with AsyncPolymarketPandas() as client:
        markets = await client.get_markets(closed=False)
        book = await client.get_orderbook(token_id)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Self

from polymarket_pandas.client import PolymarketPandas

# Methods that are properties or internal — do not wrap
_SKIP = frozenset(
    {
        "close",
        "preprocess_dataframe",
        "response_to_dataframe",
        "orderbook_to_dataframe",
    }
)


def _make_async_wrapper(method_name: str):
    """Create an async wrapper that delegates to self._sync.<method_name>."""

    async def wrapper(self, *args, **kwargs):
        loop = asyncio.get_running_loop()
        fn = getattr(self._sync, method_name)
        return await loop.run_in_executor(self._executor, functools.partial(fn, *args, **kwargs))

    wrapper.__name__ = method_name
    wrapper.__qualname__ = f"AsyncPolymarketPandas.{method_name}"
    return wrapper


class AsyncPolymarketPandas:
    """Async version of :class:`~polymarket_pandas.PolymarketPandas`.

    Accepts the same constructor arguments. Internally creates a synchronous
    ``PolymarketPandas`` instance and runs its methods in a thread pool.

    Use as an async context manager::

        async with AsyncPolymarketPandas() as client:
            markets = await client.get_markets(closed=False)
    """

    def __init__(self, *, max_workers: int = 10, **kwargs):
        self._sync = PolymarketPandas(**kwargs)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    # ── Delegate properties to sync client ──────────────────────────

    @property
    def address(self) -> str | None:
        return self._sync.address

    @property
    def private_key(self) -> str | None:
        return self._sync.private_key

    @property
    def clob_url(self) -> str:
        return self._sync.clob_url

    # ── Lifecycle ───────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying HTTP client and thread pool."""
        self._sync.close()
        self._executor.shutdown(wait=False)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"Async{self._sync!r}"


# ── Auto-generate async wrappers for all public methods ─────────────


def _populate_async_methods():
    for name, method in inspect.getmembers(PolymarketPandas, predicate=inspect.isfunction):
        if name.startswith("_") or name in _SKIP:
            continue
        if hasattr(AsyncPolymarketPandas, name):
            continue  # don't overwrite explicitly defined methods
        wrapper = _make_async_wrapper(name)
        # Copy docstring from sync method
        wrapper.__doc__ = method.__doc__
        setattr(AsyncPolymarketPandas, name, wrapper)


_populate_async_methods()
