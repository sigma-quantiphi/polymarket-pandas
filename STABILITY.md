# Stability & Deprecation Policy

`polymarket-pandas` follows [Semantic Versioning](https://semver.org/).

## What counts as a breaking change

Anything that can break working user code:

- Removing or renaming a public class, method, function, or parameter.
- Changing the return type of a public method (including DataFrame column names / dtypes enforced by pandera schemas).
- Tightening a pandera schema in a way that rejects previously-accepted input.
- Removing a re-export from the top-level package.

Anything prefixed with `_` is private and may change at any time.

## Deprecation window

Deprecations are announced at least **one minor release** before removal:

1. The symbol is marked with `@typing_extensions.deprecated(...)`, which raises `DeprecationWarning` at call time and is surfaced by IDEs.
2. `CHANGELOG.md` lists it under "Deprecated" with the target removal version.
3. The docstring and mkdocs site mark it deprecated.

Example:

```python
from typing_extensions import deprecated

@deprecated("Use `get_markets(active=True)` instead. Removed in 0.8.0.")
def get_active_markets(self): ...
```

## Upstream Polymarket API drift

Polymarket may evolve its REST / WebSocket surface independently of this package. A schema-level change upstream does not automatically bump the package major version; only package-level API changes (method signatures, DataFrame columns, exported symbols) do. When an upstream break lands, a minor release adapts the affected mixin and notes the drift in `CHANGELOG.md`.
